"""Persistent ledger of formalization runs and historical results.

Allows users to review previous single and batch formalization runs without
re-running expensive LLM inference.

Persistence: a single JSON file under data/history_store.json (never inside the
SRS-Knowledge vault), loaded lazily and written atomically on every update.
On initialization, if no history store exists, it automatically recovers
any existing results found in data/result_cache.json into a historical batch run.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.pipeline import PipelineResult

logger = logging.getLogger(__name__)

HISTORY_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "history_store.json"
RESULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "result_cache.json"

_lock = threading.Lock()
_history_entries: Optional[Dict[str, Any]] = None


def _classify_result_dict(res: Dict[str, Any]) -> Dict[str, str]:
    """Helper to classify a result dictionary for status counts and badges."""
    success = res.get("success", True)
    val_valid = res.get("validation_valid")
    status = str(res.get("status", "")).upper()
    clarifications = res.get("clarifications") or []

    if not success:
        return {"label": "FAILED", "css": "danger"}
    if val_valid is False:
        return {"label": "INVALID FORMULA", "css": "danger"}
    if status == "BLOCKED":
        return {"label": "BLOCKED", "css": "danger"}
    if status == "PASS":
        has_open = any(
            (q.get("status") if isinstance(q, dict) else getattr(q, "status", "OPEN")) == "OPEN"
            for q in clarifications
        )
        if has_open:
            return {"label": "PASS (NEEDS CLARIFICATION)", "css": "warning"}
        return {"label": "PASS", "css": "success"}
    return {"label": status.replace("_", " "), "css": "warning"}


def _recover_from_result_cache() -> List[Dict[str, Any]]:
    """Inspects data/result_cache.json and recovers any existing runs into a historical batch run."""
    if not RESULT_CACHE_PATH.exists():
        return []

    try:
        raw_cache = json.loads(RESULT_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read result cache for recovery: %s", exc)
        return []

    if not isinstance(raw_cache, dict) or not raw_cache:
        return []

    # Sort entries by saved_at or requirement ID
    items: List[Dict[str, Any]] = []
    req_ids: List[int] = []
    latest_time = None

    # Sort numerically by requirement id
    sorted_keys = sorted(raw_cache.keys(), key=lambda k: int(k) if k.isdigit() else k)

    for k in sorted_keys:
        entry = raw_cache.get(k)
        if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
            continue
        res_dict = dict(entry["result"])
        items.append(res_dict)
        try:
            req_ids.append(int(res_dict.get("requirement_id", k)))
        except (ValueError, TypeError):
            pass
        saved_at = entry.get("saved_at")
        if saved_at:
            if latest_time is None or saved_at > latest_time:
                latest_time = saved_at

    if not items:
        return []

    # Compute status summary
    status_summary: Dict[str, int] = {}
    for item in items:
        info = _classify_result_dict(item)
        status_summary[info["label"]] = status_summary.get(info["label"], 0) + 1

    created_at = latest_time or datetime.now(timezone.utc).isoformat(timespec="seconds")
    recovered_run = {
        "run_id": "run_recovered_batch_initial",
        "run_type": "batch" if len(items) > 1 else "single",
        "created_at": created_at,
        "requirement_ids": req_ids,
        "max_revisions": items[0].get("max_revisions", 2) if items else 2,
        "group_id": None,
        "model_config": {
            "analyst": "llama3:latest",
            "reasoning": "llama3:latest",
            "critic": "llama3:latest",
        },
        "status_summary": status_summary,
        "requirement_count": len(items),
        "items": items,
        "is_recovered": True,
    }

    logger.info("Successfully recovered %d historical requirement results into run_recovered_batch_initial.", len(items))
    return [recovered_run]


def _load() -> Dict[str, Any]:
    """Loads history entries from disk; callers must hold _lock."""
    global _history_entries
    if _history_entries is not None:
        return _history_entries

    _history_entries = {"runs": []}

    try:
        if HISTORY_STORE_PATH.exists():
            raw = json.loads(HISTORY_STORE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("runs"), list):
                _history_entries = raw
            elif isinstance(raw, list):
                _history_entries = {"runs": raw}
    except (OSError, ValueError) as exc:
        logger.error("History store %s is unreadable (%s); starting fresh and keeping .corrupt file.", HISTORY_STORE_PATH, exc)
        try:
            os.replace(HISTORY_STORE_PATH, HISTORY_STORE_PATH.with_suffix(".corrupt.json"))
        except OSError:
            pass

    # If runs is empty, attempt recovery from result_cache.json
    if not _history_entries.get("runs"):
        recovered = _recover_from_result_cache()
        if recovered:
            _history_entries["runs"] = recovered
            _write(_history_entries)

    return _history_entries


def _write(entries: Dict[str, Any]) -> None:
    """Atomically persists history entries; callers must hold _lock."""
    try:
        HISTORY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = HISTORY_STORE_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(entries, default=str, indent=2), encoding="utf-8")
        os.replace(tmp_path, HISTORY_STORE_PATH)
    except OSError:
        logger.exception("Could not persist history store to %s.", HISTORY_STORE_PATH)


def record_run(
    run_type: str,
    requirement_ids: List[int],
    results: List[Union[PipelineResult, Dict[str, Any]]],
    max_revisions: int = 2,
    group_id: Optional[int] = None,
    model_config: Optional[Dict[str, str]] = None,
    created_at: Optional[str] = None,
) -> str:
    """Records a completed formalization run (single or batch) into history.

    Args:
        run_type: 'single' or 'batch'.
        requirement_ids: List of canonical integer requirement IDs.
        results: List of PipelineResult instances or result dictionaries.
        max_revisions: Bound on revision passes used.
        group_id: Optional target group ID associated with the run.
        model_config: Active model selections at execution time.
        created_at: Optional ISO timestamp override (defaults to current UTC).

    Returns:
        The generated unique run_id string.
    """
    now_utc = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{ts_compact}_{len(requirement_ids)}reqs"

    items: List[Dict[str, Any]] = []
    status_summary: Dict[str, int] = {}

    for res in results:
        res_dict = res.to_dict() if hasattr(res, "to_dict") else dict(res)
        items.append(res_dict)
        info = _classify_result_dict(res_dict)
        status_summary[info["label"]] = status_summary.get(info["label"], 0) + 1

    run_entry: Dict[str, Any] = {
        "run_id": run_id,
        "run_type": run_type,
        "created_at": now_utc,
        "requirement_ids": list(requirement_ids),
        "max_revisions": max_revisions,
        "group_id": group_id,
        "model_config": dict(model_config or {}),
        "status_summary": status_summary,
        "requirement_count": len(items),
        "items": items,
        "is_recovered": False,
    }

    with _lock:
        entries = _load()
        # Avoid duplicate run_id collision
        existing_ids = {r.get("run_id") for r in entries["runs"]}
        counter = 1
        orig_id = run_id
        while run_id in existing_ids:
            run_id = f"{orig_id}_{counter}"
            counter += 1
        run_entry["run_id"] = run_id

        # Insert at front for reverse chronological order
        entries["runs"].insert(0, run_entry)
        _write(entries)

    logger.info("Recorded %s run %s with %d requirement(s).", run_type, run_id, len(items))
    return run_id


def get_runs(
    run_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns runs in reverse chronological order with optional filtering."""
    with _lock:
        runs = list(_load().get("runs", []))

    filtered: List[Dict[str, Any]] = []
    norm_query = search_query.strip().lower() if search_query else None
    norm_status = status_filter.strip().upper() if status_filter and status_filter.upper() != "ALL" else None
    norm_type = run_type.strip().lower() if run_type and run_type.lower() != "all" else None

    for run in runs:
        # Filter by run type
        if norm_type and run.get("run_type", "").lower() != norm_type:
            continue

        # Filter by status present in run
        if norm_status:
            summary = run.get("status_summary", {})
            # Check exact match or partial match in summary keys
            match_status = any(norm_status == k.upper() for k, count in summary.items() if count > 0)
            if not match_status:
                continue

        # Filter by search query (run_id, requirement ID, srs_id, text)
        if norm_query:
            run_id_match = norm_query in str(run.get("run_id", "")).lower()
            req_ids_match = any(norm_query in str(rid) for rid in run.get("requirement_ids", []))
            item_match = False
            for itm in run.get("items", []):
                srs_id = str(itm.get("srs_id", "")).lower()
                raw_text = str(itm.get("raw_text", "")).lower()
                formula = str(itm.get("formalization", "")).lower()
                if norm_query in srs_id or norm_query in raw_text or norm_query in formula:
                    item_match = True
                    break
            if not (run_id_match or req_ids_match or item_match):
                continue

        filtered.append(run)

    return filtered


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single run record by its unique run_id."""
    with _lock:
        runs = _load().get("runs", [])
        for r in runs:
            if r.get("run_id") == run_id:
                return dict(r)
    return None


def get_overview_stats() -> Dict[str, Any]:
    """Computes comprehensive metrics across all recorded formalization runs.

    Counting Rules:
    - total_runs: Total number of formalization runs executed (single + batch).
    - total_evaluations: Total requirement evaluations conducted across all runs (includes repeated runs).
    - unique_requirements_count: Number of distinct canonical requirements formalized.
    - unique_status_counts: Breakdown of the latest result for each unique requirement.
    - all_status_counts: Cumulative breakdown across every requirement evaluation.
    """
    with _lock:
        runs = list(_load().get("runs", []))

    total_runs = len(runs)
    total_evaluations = 0
    unique_latest_by_req: Dict[int, Dict[str, Any]] = {}
    all_status_counts: Dict[str, int] = {
        "PASS": 0,
        "PASS (NEEDS CLARIFICATION)": 0,
        "MAX_ITERATIONS": 0,
        "BLOCKED": 0,
        "INVALID FORMULA": 0,
        "FAILED": 0,
        "OTHER": 0,
    }

    # Iterate runs in chronological order (reverse of runs list) so latest run overwrites
    for run in reversed(runs):
        items = run.get("items", [])
        total_evaluations += len(items)
        for item in items:
            req_id = item.get("requirement_id")
            if req_id is not None:
                unique_latest_by_req[req_id] = item

            info = _classify_result_dict(item)
            lbl = info["label"]
            if lbl in all_status_counts:
                all_status_counts[lbl] += 1
            else:
                all_status_counts["OTHER"] += 1

    unique_status_counts: Dict[str, int] = {
        "PASS": 0,
        "PASS (NEEDS CLARIFICATION)": 0,
        "MAX_ITERATIONS": 0,
        "BLOCKED": 0,
        "INVALID FORMULA": 0,
        "FAILED": 0,
        "OTHER": 0,
    }

    for req_id, item in unique_latest_by_req.items():
        info = _classify_result_dict(item)
        lbl = info["label"]
        if lbl in unique_status_counts:
            unique_status_counts[lbl] += 1
        else:
            unique_status_counts["OTHER"] += 1

    return {
        "total_runs": total_runs,
        "total_evaluations": total_evaluations,
        "unique_requirements_count": len(unique_latest_by_req),
        "unique_status_counts": unique_status_counts,
        "all_status_counts": all_status_counts,
    }


def get_all_unique_results(
    search_query: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns the latest result for each unique requirement with search and status filtering."""
    with _lock:
        runs = list(_load().get("runs", []))

    latest_by_req: Dict[int, Dict[str, Any]] = {}
    # Iterate in chronological order so newer runs override older runs
    for run in reversed(runs):
        run_id = run.get("run_id")
        created_at = run.get("created_at")
        for item in run.get("items", []):
            req_id = item.get("requirement_id")
            if req_id is not None:
                enriched = dict(item)
                enriched["_origin_run_id"] = run_id
                enriched["_origin_run_time"] = created_at
                latest_by_req[req_id] = enriched

    results = list(latest_by_req.values())

    norm_query = search_query.strip().lower() if search_query else None
    norm_status = status_filter.strip().upper() if status_filter and status_filter.upper() != "ALL" else None

    filtered: List[Dict[str, Any]] = []
    for r in results:
        info = _classify_result_dict(r)
        if norm_status and info["label"].upper() != norm_status:
            continue

        if norm_query:
            req_id_str = str(r.get("requirement_id", ""))
            srs_id = str(r.get("srs_id", "")).lower()
            text = str(r.get("raw_text", "")).lower()
            formula = str(r.get("formalization", "")).lower()
            if not (norm_query in req_id_str or norm_query in srs_id or norm_query in text or norm_query in formula):
                continue

        filtered.append(r)

    # Sort numerically by requirement_id
    filtered.sort(key=lambda x: int(x.get("requirement_id", 0)))
    return filtered


def get_latest_result_for_requirement(requirement_id: int) -> Optional[Dict[str, Any]]:
    """Returns the latest recorded result for a requirement ID from history."""
    with _lock:
        runs = _load().get("runs", [])
        for run in runs:  # newest first
            for item in run.get("items", []):
                if item.get("requirement_id") == requirement_id:
                    return dict(item)
    return None


def update_clarification_in_history(
    requirement_id: int,
    question_id: str,
    answer: str,
    answered_at: str,
) -> bool:
    """Updates a clarification question's answer in all matching historical records."""
    updated = False
    with _lock:
        entries = _load()
        for run in entries.get("runs", []):
            for item in run.get("items", []):
                if item.get("requirement_id") == requirement_id:
                    for cq in item.get("clarifications", []):
                        if cq.get("question_id") == question_id:
                            cq["status"] = "ANSWERED"
                            cq["answer"] = answer
                            cq["answered_at"] = answered_at
                            updated = True
            # Recompute run's status summary
            summary: Dict[str, int] = {}
            for item in run.get("items", []):
                info = _classify_result_dict(item)
                summary[info["label"]] = summary.get(info["label"], 0) + 1
            run["status_summary"] = summary

        if updated:
            _write(entries)

    return updated
