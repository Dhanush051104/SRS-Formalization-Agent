"""Persistent cache of completed pipeline results, so Full View can show an existing result
without re-running the LLM pipeline.

Identity: results are keyed by canonical requirement ID (the SQLite primary key).
Persistence: a single JSON file under data/ (never inside the SRS-Knowledge vault), loaded lazily
and written through atomically on every save, so results survive server restarts.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from app.pipeline import PipelineResult

logger = logging.getLogger(__name__)

STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "result_cache.json"

_lock = threading.Lock()
_entries: Optional[Dict[str, dict]] = None


def _load() -> Dict[str, dict]:
    """Load entries from disk once; callers must hold _lock."""
    global _entries
    if _entries is not None:
        return _entries
    _entries = {}
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _entries
    except (OSError, ValueError) as exc:
        logger.error("Result cache %s is unreadable (%s); starting empty and keeping a .corrupt copy.", STORE_PATH, exc)
        try:
            os.replace(STORE_PATH, STORE_PATH.with_suffix(".corrupt.json"))
        except OSError:
            logger.exception("Could not preserve unreadable result cache %s", STORE_PATH)
        return _entries
    if isinstance(raw, dict):
        _entries = {
            str(key): value for key, value in raw.items()
            if isinstance(value, dict) and isinstance(value.get("result"), dict)
        }
    else:
        logger.error("Result cache %s has an unexpected top-level type; ignoring it.", STORE_PATH)
    return _entries


def _write(entries: Dict[str, dict]) -> None:
    """Atomically persist entries; a failure is logged but never breaks the request."""
    try:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = STORE_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(entries, default=str), encoding="utf-8")
        os.replace(tmp_path, STORE_PATH)
    except OSError:
        logger.exception("Could not persist result cache to %s; results remain available until restart.", STORE_PATH)


def save(result: PipelineResult) -> bool:
    """Store a result. A failed run never replaces a stored successful result.

    Returns True if the result was stored.
    """
    key = str(result.requirement_id)
    with _lock:
        entries = _load()
        existing = entries.get(key)
        if not result.success and existing and existing["result"].get("success"):
            return False
        entries[key] = {
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "result": result.to_dict(),
        }
        _write(entries)
    return True


def get(requirement_id: int) -> Optional[PipelineResult]:
    with _lock:
        entry = _load().get(str(requirement_id))
    if not entry:
        try:
            from app.ui.history_store import get_latest_result_for_requirement
            hist = get_latest_result_for_requirement(requirement_id)
            if hist and hist.get("error_stage") not in {"OLLAMA_CONFIGURATION", "SQLITE_RETRIEVAL"}:
                return PipelineResult.from_dict(hist)
        except Exception as exc:
            logger.debug("Could not fallback to history store for req %s: %s", requirement_id, exc)
        return None
    try:
        return PipelineResult.from_dict(entry["result"])
    except (TypeError, ValueError):
        logger.exception("Stored result for requirement %s does not match the current schema; ignoring it.", requirement_id)
        return None


def get_saved_at(requirement_id: int) -> Optional[str]:
    """UTC ISO timestamp of when the stored result was produced, or None."""
    with _lock:
        entry = _load().get(str(requirement_id))
    if entry:
        return entry.get("saved_at")
    try:
        from app.ui.history_store import get_latest_result_for_requirement
        hist = get_latest_result_for_requirement(requirement_id)
        if hist:
            return hist.get("_origin_run_time")
    except Exception:
        pass
    return None
