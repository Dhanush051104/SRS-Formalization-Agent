import os
import sys
import sqlite3
import json
import logging
from http.client import HTTPException
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash

# Add project root to sys.path so we can import from app
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from app.parser.document_parser import parse_document
from app.structurer.requirement_segmenter import RequirementSegmenter
from app.structurer.document_cleaner import DocumentCleaner
from app.structurer.document_structurer import DocumentStructurer
from app.db.canonical_store import store_srs, get_db_connection, DEFAULT_DB_PATH
from app.db.target_service import (
    create_target_group,
    get_target_group,
    add_requirement_to_group,
    remove_requirement_from_group,
    cancel_target_group
)
from app.ui.model_config import load_model_config, save_model_config
from app.ui.result_store import get as get_saved_result, get_saved_at, save as save_result
from app.ui import history_store

logger = logging.getLogger(__name__)

OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
MIN_REVISIONS = 1
MAX_REVISIONS_LIMIT = 5
# Local Ollama must never be reached through a system proxy.
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))

app = Flask(__name__)
app.secret_key = "srs_formalization_secret_key"
UPLOAD_FOLDER = "data"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _open_local(url, timeout=2):
    """Open a local URL without proxies (patched in tests so no network call is made)."""
    return _NO_PROXY_OPENER.open(url, timeout=timeout)


def get_installed_ollama_models():
    """Return (installed model names, None) or ([], user-safe error message)."""
    try:
        with _open_local(OLLAMA_TAGS_URL, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise ValueError("unexpected /api/tags response shape")
        names = sorted({item["name"] for item in models if isinstance(item, dict) and item.get("name")})
        return names, None
    except (URLError, OSError, HTTPException, ValueError, AttributeError, TypeError) as exc:
        logger.warning("Could not read installed Ollama models from %s: %s", OLLAMA_TAGS_URL, exc)
        return [], f"Ollama is unavailable or returned invalid installed-model data: {exc}"


def build_configured_pipeline():
    models = load_model_config()
    installed, error = get_installed_ollama_models()
    if error:
        raise RuntimeError(error)
    missing = sorted({name for name in models.values() if name not in installed})
    if missing:
        raise RuntimeError(
            f"Configured Ollama model(s) are not installed: {', '.join(missing)}. "
            "Choose installed models on the Model settings page."
        )
    from app.pipeline import FormalizationPipeline
    from app.analyst.ollama_analyst import OllamaAnalyst
    from app.reasoning.ollama_reasoning import OllamaReasoning
    from app.critic.ollama_critic import OllamaCritic
    return FormalizationPipeline(
        analyst_model=OllamaAnalyst(model=models["analyst"]),
        reasoning_model=OllamaReasoning(model=models["reasoning"]),
        critic_model=OllamaCritic(model=models["critic"]),
    )


def parse_max_revisions(raw, default=2):
    """Parse a revision bound from user input, clamped to [MIN_REVISIONS, MAX_REVISIONS_LIMIT]."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(MIN_REVISIONS, min(MAX_REVISIONS_LIMIT, value))


def _failed_result(requirement_id, stage, message):
    from app.pipeline import PipelineResult
    return PipelineResult(
        requirement_id=requirement_id, global_number=0, srs_id="", section_number="",
        section_title="", raw_text="", status="FAILED", success=False,
        error_stage=stage, error_message=message,
    )


def _build_pipeline_or_error():
    """Return (pipeline, None), or (None, message) when the configured Ollama models cannot be used."""
    try:
        return build_configured_pipeline(), None
    except RuntimeError as exc:
        logger.warning("Pipeline not started: %s", exc)
        return None, str(exc)


def _run_one(pipeline, requirement_id, max_revisions, clarifications=None):
    """Run one requirement independently; any crash becomes an explicit FAILED result."""
    try:
        return pipeline.run(
            requirement_id=requirement_id,
            max_revisions=max_revisions,
            clarifications=clarifications,
        )
    except Exception as exc:
        logger.exception("Pipeline crashed for requirement %s", requirement_id)
        return _failed_result(requirement_id, "PIPELINE", f"Unexpected pipeline exception: {exc}")


# Failures that say nothing about a real requirement's formalization are never stored as its result.
_UNSTORED_ERROR_STAGES = {"OLLAMA_CONFIGURATION", "SQLITE_RETRIEVAL"}


def _store_result(result):
    if result.error_stage not in _UNSTORED_ERROR_STAGES:
        save_result(result)


def classify_result(result):
    """Distinguish failed / invalid / blocked / needs-clarification / pass for display."""
    if isinstance(result, dict):
        success = result.get("success", True)
        val_valid = result.get("validation_valid")
        status = str(result.get("status", "")).upper()
        clarifications = result.get("clarifications") or []
    else:
        success = getattr(result, "success", True)
        val_valid = getattr(result, "validation_valid", None)
        status = str(getattr(result, "status", "")).upper()
        clarifications = getattr(result, "clarifications", []) or []

    if not success:
        return {"label": "FAILED", "css": "danger", "icon": "bi-x-circle-fill"}
    if val_valid is False:
        return {"label": "INVALID FORMULA", "css": "danger", "icon": "bi-slash-circle-fill"}
    if status == "BLOCKED":
        return {"label": "BLOCKED", "css": "danger", "icon": "bi-x-octagon-fill"}
    if status == "PASS":
        has_open = any(
            (q.get("status") if isinstance(q, dict) else getattr(q, "status", "OPEN")) == "OPEN"
            for q in clarifications
        )
        if has_open:
            return {"label": "PASS (NEEDS CLARIFICATION)", "css": "warning", "icon": "bi-question-circle-fill"}
        return {"label": "PASS", "css": "success", "icon": "bi-check-circle-fill"}
    return {"label": status.replace("_", " "), "css": "warning", "icon": "bi-exclamation-triangle-fill"}


app.jinja_env.globals["classify_result"] = classify_result


@app.route("/settings/models", methods=["GET", "POST"])
def model_settings():
    installed, error = get_installed_ollama_models()
    config = load_model_config()
    if request.method == "POST":
        selected = {stage: request.form.get(stage, "") for stage in config}
        invalid = [model for model in selected.values() if model not in installed]
        if error or invalid:
            flash(error or "Selected model is not currently installed.", "danger")
        else:
            save_model_config(selected)
            flash("Model selections saved.", "success")
            return redirect(url_for("model_settings"))
        config = selected
    unavailable = [] if error else sorted({name for name in config.values() if name not in installed})
    return render_template("model_settings.html", models=installed, config=config,
                           ollama_error=error, unavailable=unavailable)


def get_recommendation_for_doc(conn, doc_id):
    """
    Get the deterministic recommended starting section for a document.
    Preference:
      1. Section 3.2.1 (System Initialization) if it exists.
      2. Otherwise, the section under Section 3 with the maximum requirements count.
    """
    cursor = conn.cursor()
    # Check if 3.2.1 exists and get its count
    cursor.execute(
        """
        SELECT s.number, s.title, COUNT(r.id) as req_count 
        FROM sections s 
        LEFT JOIN requirements r ON s.id = r.section_id 
        WHERE s.document_id = ? AND s.number = '3.2.1'
        GROUP BY s.id;
        """,
        (doc_id,)
    )
    res_321 = cursor.fetchone()
    if res_321:
        return {
            "number": res_321["number"],
            "title": res_321["title"],
            "req_count": res_321["req_count"]
        }

    # Otherwise, find the section with max requirements under Section 3
    cursor.execute(
        """
        SELECT s.number, s.title, COUNT(r.id) as req_count 
        FROM sections s 
        INNER JOIN requirements r ON s.id = r.section_id 
        WHERE s.document_id = ? AND s.number LIKE '3.%'
        GROUP BY s.id
        ORDER BY req_count DESC 
        LIMIT 1;
        """,
        (doc_id,)
    )
    res_max = cursor.fetchone()
    if res_max:
        return {
            "number": res_max["number"],
            "title": res_max["title"],
            "req_count": res_max["req_count"]
        }

    # Fallback to Section 3 itself
    cursor.execute(
        """
        SELECT s.number, s.title, COUNT(r.id) as req_count 
        FROM sections s 
        LEFT JOIN requirements r ON s.id = r.section_id 
        WHERE s.document_id = ? AND s.number = '3'
        GROUP BY s.id;
        """,
        (doc_id,)
    )
    res_3 = cursor.fetchone()
    if res_3:
        return {
            "number": res_3["number"],
            "title": res_3["title"],
            "req_count": res_3["req_count"]
        }

    return None


@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY id DESC;")
    documents_raw = cursor.fetchall()
    
    documents = []
    for doc in documents_raw:
        doc_data = dict(doc)
        rec = get_recommendation_for_doc(conn, doc_data["id"])
        if rec:
            doc_data["recommended_section"] = rec["number"]
            doc_data["recommended_title"] = rec["title"]
            doc_data["recommended_req_count"] = rec["req_count"]
        else:
            doc_data["recommended_section"] = None
        documents.append(doc_data)

    conn.close()
    history_stats = history_store.get_overview_stats()
    return render_template("index.html", documents=documents, history_stats=history_stats)


@app.route("/upload", methods=["POST"])
def upload():
    if "srs_file" not in request.files:
        flash("No file part in the request", "danger")
        return redirect(url_for("index"))

    file = request.files["srs_file"]
    if file.filename == "":
        flash("No selected file", "danger")
        return redirect(url_for("index"))

    if file and (file.filename.endswith(".pdf") or file.filename.endswith(".docx")):
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        try:
            # Parse, segment, structure and store in SQLite
            elements = parse_document(filepath)
            
            segmenter = RequirementSegmenter()
            raw_requirements = segmenter.segment(elements)
            
            cleaner = DocumentCleaner()
            requirements = [cleaner.clean_requirement(r) for r in raw_requirements]
            
            structurer = DocumentStructurer(elements)
            structured_doc = structurer.build()
            structured_doc = structurer.add_requirements(structured_doc, requirements)

            doc_id = store_srs(
                DEFAULT_DB_PATH,
                filename=file.filename,
                filepath=filepath,
                parsed_elements=elements,
                structured_doc=structured_doc,
                segmented_requirements=requirements
            )
            flash(f"Successfully uploaded and structured '{file.filename}'!", "success")
            return redirect(url_for("document", doc_id=doc_id))
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "danger")
            return redirect(url_for("index"))
    else:
        flash("Unsupported file format. Only PDF and DOCX are supported.", "danger")
        return redirect(url_for("index"))


@app.route("/document/<int:doc_id>")
def document(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Document Metadata
    cursor.execute("SELECT * FROM documents WHERE id = ?;", (doc_id,))
    doc_row = cursor.fetchone()
    if not doc_row:
        conn.close()
        flash("Document not found.", "danger")
        return redirect(url_for("index"))
    doc = dict(doc_row)

    # 2. Fetch all sections and requirement counts
    cursor.execute(
        """
        SELECT s.id, s.number, s.title, s.page_number, s.parent_number, s.element_index,
               (SELECT COUNT(*) FROM requirements r WHERE r.section_id = s.id) as req_count
        FROM sections s
        WHERE s.document_id = ?;
        """,
        (doc_id,)
    )
    sections_raw = cursor.fetchall()
    sections_list = [dict(s) for s in sections_raw]

    if not sections_list:
        conn.close()
        return render_template("document.html", document=doc, section_tree=[], selected_section=None, elements=[], section_requirements=[])

    # Compute recommended section
    recommendation = get_recommendation_for_doc(conn, doc_id)

    # Get selected section number (default to recommendation, or fallback to first section)
    selected_num = request.args.get("section")
    if not selected_num:
        if recommendation:
            selected_num = recommendation["number"]
        else:
            # Sort sections naturally and get first one
            def natural_sort_key(s):
                return [int(x) if x.isdigit() else x for x in s["number"].split('.')]
            sorted_secs = sorted(sections_list, key=natural_sort_key)
            selected_num = sorted_secs[0]["number"]

    # 3. Fetch selected section data
    cursor.execute("SELECT * FROM sections WHERE document_id = ? AND number = ?;", (doc_id, selected_num))
    selected_section_row = cursor.fetchone()
    if not selected_section_row:
        # Fallback if not found
        selected_section_row = sections_list[0]
        selected_num = selected_section_row["number"]
    selected_section = dict(selected_section_row)

    # 4. Reconstruct section content from elements table
    start_index = selected_section["element_index"]
    
    # Find next section index (terminating at the next sibling/ancestor section index)
    selected_prefix = selected_num + "."
    next_sibling_index = None

    for sec in sections_list:
        sec_num = sec["number"]
        sec_idx = sec["element_index"]
        if sec_idx > start_index:
            # Sibling/ancestor means not a descendant (does not start with selected_num + ".")
            if not sec_num.startswith(selected_prefix):
                if next_sibling_index is None or sec_idx < next_sibling_index:
                    next_sibling_index = sec_idx

    if next_sibling_index is not None:
        end_index = next_sibling_index
    else:
        # Reconstruct to the end of the document
        cursor.execute("SELECT COUNT(*) FROM elements WHERE document_id = ?;", (doc_id,))
        end_index = cursor.fetchone()[0]

    # Query elements
    cursor.execute(
        "SELECT * FROM elements WHERE document_id = ? AND element_index >= ? AND element_index < ? ORDER BY element_index;",
        (doc_id, start_index, end_index)
    )
    elements_raw = cursor.fetchall()
    elements = [dict(el) for el in elements_raw]

    # Fetch requirements in this index range (selected section and its sub-hierarchy)
    cursor.execute(
        "SELECT * FROM requirements WHERE document_id = ? AND element_index >= ? AND element_index < ? ORDER BY element_index;",
        (doc_id, start_index, end_index)
    )
    reqs_raw = cursor.fetchall()
    section_requirements = [dict(r) for r in reqs_raw]

    # Mark starts and continuations of requirements to avoid duplicate rendering in UI
    reqs_by_idx = {r["element_index"]: r for r in section_requirements}
    sorted_reqs = sorted(section_requirements, key=lambda r: r["element_index"])
    
    continuation_indices = set()
    for i, req in enumerate(sorted_reqs):
        s_idx = req["element_index"]
        if i + 1 < len(sorted_reqs):
            n_start_idx = sorted_reqs[i+1]["element_index"]
        else:
            n_start_idx = end_index
        for idx in range(s_idx + 1, n_start_idx):
            continuation_indices.add(idx)

    for el in elements:
        idx = el["element_index"]
        if idx in reqs_by_idx:
            el["classification"] = "requirement"
            el["requirement_info"] = reqs_by_idx[idx]
            el["is_continuation"] = False
        elif idx in continuation_indices:
            el["is_continuation"] = True
        else:
            el["is_continuation"] = False

    # 5. Build section tree structure for left pane
    section_tree = build_section_tree(sections_list)

    conn.close()
    return render_template(
        "document.html",
        document=doc,
        section_tree=section_tree,
        selected_section=selected_section,
        elements=elements,
        section_requirements=section_requirements,
        recommendation=recommendation
    )


def build_section_tree(sections_list):
    """
    Builds a nested tree structure of sections, resolving missing parents to their nearest ancestor.
    Adds a 'depth' key to each node for indentation.
    """
    def sort_key(s):
        parts = []
        for x in s["number"].split('.'):
            if x.isdigit():
                parts.append(int(x))
            else:
                parts.append(x)
        return parts

    sorted_sections = sorted(sections_list, key=sort_key)
    sections_by_num = {s["number"]: {**s, "nested_children": [], "depth": 0} for s in sorted_sections}
    root_sections = []
    
    for sec in sorted_sections:
        num = sec["number"]
        parent_num = sec["parent_number"]
        node = sections_by_num[num]
        
        # Find nearest existing parent
        existing_parent = None
        ancestor = parent_num
        while ancestor is not None:
            if ancestor in sections_by_num:
                existing_parent = ancestor
                break
            parts = ancestor.split(".")
            if len(parts) <= 1:
                ancestor = None
            else:
                ancestor = ".".join(parts[:-1])
                
        if existing_parent:
            parent_node = sections_by_num[existing_parent]
            node["depth"] = parent_node["depth"] + 1
            parent_node["nested_children"].append(node)
        else:
            node["depth"] = 0
            root_sections.append(node)
            
    return root_sections


@app.route("/document/<int:doc_id>/create_group", methods=["POST"])
def create_group(doc_id):
    req_ids_raw = request.form.getlist("requirement_ids")
    section_number = request.form.get("section_number")
    
    if not req_ids_raw:
        flash("No requirements selected.", "danger")
        return redirect(url_for("document", doc_id=doc_id, section=section_number))
        
    try:
        req_ids = [int(rid) for rid in req_ids_raw]
        group_id = create_target_group(DEFAULT_DB_PATH, doc_id, section_number, req_ids)
        flash("Target group created successfully.", "success")
        return redirect(url_for("target_group_summary", group_id=group_id))
    except ValueError as ve:
        flash(f"Validation Error: {str(ve)}", "danger")
        return redirect(url_for("document", doc_id=doc_id, section=section_number))
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "danger")
        return redirect(url_for("document", doc_id=doc_id, section=section_number))


@app.route("/target_group/<int:group_id>")
def target_group_summary(group_id):
    group = get_target_group(DEFAULT_DB_PATH, group_id)
    if not group:
        flash("Target Group not found.", "danger")
        return redirect(url_for("index"))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?;", (group["document_id"],))
    doc_row = cursor.fetchone()
    
    # Fetch section details to get section title
    cursor.execute(
        "SELECT title FROM sections WHERE document_id = ? AND number = ?;",
        (group["document_id"], group["section_number"])
    )
    sec_row = cursor.fetchone()
    section_title = sec_row["title"] if sec_row else ""
    
    conn.close()
    
    return render_template(
        "target_group.html",
        document=dict(doc_row) if doc_row else None,
        target_group=group,
        section_title=section_title
    )


@app.route("/target_group/<int:group_id>/remove/<int:req_id>", methods=["POST"])
def remove_requirement(group_id, req_id):
    group = get_target_group(DEFAULT_DB_PATH, group_id)
    if not group:
        flash("Target Group not found.", "danger")
        return redirect(url_for("index"))
        
    doc_id = group["document_id"]
    sec_num = group["section_number"]
    
    try:
        remove_requirement_from_group(DEFAULT_DB_PATH, group_id, req_id)
        # Check if group still exists
        remaining_group = get_target_group(DEFAULT_DB_PATH, group_id)
        if not remaining_group:
            flash("Target group deleted because it has no requirements remaining.", "info")
            return redirect(url_for("document", doc_id=doc_id, section=sec_num))
        flash("Requirement removed from group.", "success")
        return redirect(url_for("target_group_summary", group_id=group_id))
    except Exception as e:
        flash(f"Error removing requirement: {str(e)}", "danger")
        return redirect(url_for("target_group_summary", group_id=group_id))


@app.route("/target_group/<int:group_id>/cancel", methods=["POST"])
def cancel_group(group_id):
    group = get_target_group(DEFAULT_DB_PATH, group_id)
    if not group:
        flash("Target Group not found.", "danger")
        return redirect(url_for("index"))
        
    doc_id = group["document_id"]
    sec_num = group["section_number"]
    
    try:
        cancel_target_group(DEFAULT_DB_PATH, group_id)
        flash("Target group cancelled.", "info")
    except Exception as e:
        flash(f"Error cancelling group: {str(e)}", "danger")
        
    return redirect(url_for("document", doc_id=doc_id, section=sec_num))


@app.route("/formalize/<int:req_id>", methods=["GET", "POST"])
def formalize_requirement(req_id):
    """
    Renders the end-to-end formalization dashboard for a requirement.
    Executes SQLite -> Analyst -> ContextBuilder -> Reasoning -> Critic -> Revision -> Clarification.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.*, s.title as section_title, s.number as section_number, r.document_id
        FROM requirements r
        JOIN sections s ON r.section_id = s.id
        WHERE r.id = ?
        """,
        (req_id,)
    )
    req_row = cursor.fetchone()
    conn.close()

    if not req_row:
        flash(f"Requirement ID {req_id} not found in database.", "danger")
        return redirect(url_for("index"))

    result = get_saved_result(req_id)
    ran_now = False
    if request.method == "POST" or request.args.get("run") == "1":
        ran_now = True
        max_revisions = parse_max_revisions(request.form.get("max_revisions"))
        pipeline, config_error = _build_pipeline_or_error()
        if pipeline is None:
            result = _failed_result(req_id, "OLLAMA_CONFIGURATION", config_error)
        else:
            clarifs = result.clarifications if result else None
            result = _run_one(pipeline, req_id, max_revisions, clarifications=clarifs)
        _store_result(result)
        if getattr(result, "error_stage", None) not in _UNSTORED_ERROR_STAGES:
            history_store.record_run(
                run_type="single",
                requirement_ids=[req_id],
                results=[result],
                max_revisions=max_revisions,
                model_config=load_model_config(),
            )

    # Opening Full View (GET) only reads the stored result; it never re-runs the pipeline.
    return render_template("formalize.html", req=req_row, result=result,
                           from_cache=not ran_now, saved_at=get_saved_at(req_id))


@app.route("/clarify/<int:req_id>", methods=["POST"])
def answer_clarification(req_id):
    """
    Records stakeholder answer for an open clarification question and persists it.
    Optionally triggers a re-run of the formalization pipeline incorporating the answer.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM requirements WHERE id = ?;", (req_id,))
    req_row = cursor.fetchone()
    conn.close()

    if not req_row:
        flash(f"Requirement ID {req_id} not found in database.", "danger")
        return redirect(url_for("index"))

    stored = get_saved_result(req_id)
    if not stored:
        flash(f"No existing formalization found for requirement ID {req_id}.", "warning")
        return redirect(url_for("formalize_requirement", req_id=req_id))

    question_id = request.form.get("question_id", "").strip()
    selected_answer = request.form.get("answer", "").strip()
    custom_answer = request.form.get("custom_answer", "").strip()

    if selected_answer == "__custom__" or (not selected_answer and custom_answer):
        chosen_answer = custom_answer
    else:
        chosen_answer = selected_answer

    if not chosen_answer:
        flash("Please select an option or provide a custom answer for the clarification question.", "warning")
        return redirect(url_for("formalize_requirement", req_id=req_id))

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    found = False
    for q in stored.clarifications:
        if q.get("question_id") == question_id:
            q["status"] = "ANSWERED"
            q["answer"] = chosen_answer
            q["answered_at"] = now_iso
            found = True
            break

    if not found:
        flash(f"Clarification question {question_id} not found in saved results.", "danger")
        return redirect(url_for("formalize_requirement", req_id=req_id))

    save_result(stored)
    history_store.update_clarification_in_history(
        requirement_id=req_id,
        question_id=question_id,
        answer=chosen_answer,
        answered_at=now_iso,
    )

    rerun = request.form.get("rerun") == "1"
    if rerun:
        pipeline, config_error = _build_pipeline_or_error()
        if pipeline is None:
            flash(f"Clarification answer recorded, but pipeline could not be started: {config_error}", "warning")
        else:
            max_revisions = parse_max_revisions(request.form.get("max_revisions", 2))
            new_res = _run_one(pipeline, req_id, max_revisions, clarifications=stored.clarifications)
            if new_res.success:
                _store_result(new_res)
                history_store.record_run(
                    run_type="single",
                    requirement_ids=[req_id],
                    results=[new_res],
                    max_revisions=max_revisions,
                    model_config=load_model_config(),
                )
                flash("Clarification answer recorded and formalization successfully re-run.", "success")
            else:
                flash("Clarification answer recorded, but re-run failed. Preserving previous result.", "warning")
    else:
        flash("Clarification answer recorded successfully.", "success")

    return redirect(url_for("formalize_requirement", req_id=req_id))


@app.route("/formalize/batch", methods=["GET", "POST"])
def batch_formalize():
    """
    Processes a batch of requirement IDs through the real configured pipeline sequentially.
    Each requirement is run independently; a failure on one never stops or alters the others.

    POST params:
        requirement_ids  — one or more integer requirement IDs (repeated field)
        max_revisions    — integer, clamped to 1..5 (default 2)
        group_id         — optional integer, used only for breadcrumb / re-run form
    """
    # Support both GET (re-run link from group page) and POST (form submission)
    if request.method == "GET":
        req_ids_raw = request.args.getlist("requirement_ids")
        max_revisions = parse_max_revisions(request.args.get("max_revisions"))
        group_id = request.args.get("group_id", type=int)
    else:
        req_ids_raw = request.form.getlist("requirement_ids")
        max_revisions = parse_max_revisions(request.form.get("max_revisions"))
        group_id = request.form.get("group_id", type=int)

    if not req_ids_raw:
        flash("No requirement IDs provided for batch formalization.", "danger")
        return redirect(url_for("index"))

    # Parse and deduplicate, preserving order
    seen = set()
    req_ids = []
    skipped_invalid = []
    duplicates_removed = 0
    for raw in req_ids_raw:
        try:
            rid = int(raw)
        except (ValueError, TypeError):
            skipped_invalid.append(raw)
            continue
        if rid in seen:
            duplicates_removed += 1
            continue
        seen.add(rid)
        req_ids.append(rid)

    if not req_ids:
        ignored = ", ".join(repr(raw) for raw in skipped_invalid)
        flash(f"No valid integer requirement IDs provided (ignored: {ignored}).", "danger")
        return redirect(url_for("index"))

    pipeline, config_error = _build_pipeline_or_error()

    results = []
    for rid in req_ids:
        if pipeline is None:
            res = _failed_result(rid, "OLLAMA_CONFIGURATION", config_error)
        else:
            stored = get_saved_result(rid)
            clarifs = stored.clarifications if stored else None
            res = _run_one(pipeline, rid, max_revisions, clarifications=clarifs)
        results.append(res)
        _store_result(res)

    # Record completed batch run in persistent history store
    if any(getattr(r, "error_stage", None) not in _UNSTORED_ERROR_STAGES for r in results):
        history_store.record_run(
            run_type="batch",
            requirement_ids=req_ids,
            results=results,
            max_revisions=max_revisions,
            group_id=group_id,
            model_config=load_model_config(),
        )

    summary = {}
    for res in results:
        info = classify_result(res)
        entry = summary.setdefault(info["label"], {"count": 0, "css": info["css"]})
        entry["count"] += 1

    return render_template(
        "batch_formalize.html",
        results=results,
        req_ids=req_ids,
        max_revisions=max_revisions,
        group_id=group_id,
        summary=summary,
        skipped_invalid=skipped_invalid,
        duplicates_removed=duplicates_removed,
    )


@app.route("/history")
def history_dashboard():
    """
    Displays the persistent formalization history dashboard.
    Includes overview statistics, reverse-chronological run ledger, and searchable results explorer.
    """
    stats = history_store.get_overview_stats()
    run_type_filter = request.args.get("type", "").strip()
    status_filter = request.args.get("status", "").strip()
    search_query = request.args.get("q", "").strip()

    runs = history_store.get_runs(
        run_type=run_type_filter if run_type_filter else None,
        status_filter=status_filter if status_filter else None,
        search_query=search_query if search_query else None,
    )

    unique_results = history_store.get_all_unique_results(
        search_query=search_query if search_query else None,
        status_filter=status_filter if status_filter else None,
    )

    return render_template(
        "history.html",
        stats=stats,
        runs=runs,
        unique_results=unique_results,
        run_type_filter=run_type_filter,
        status_filter=status_filter,
        search_query=search_query,
    )


@app.route("/history/run/<run_id>")
def history_run_detail(run_id):
    """
    Inspects an individual historical formalization run (single or batch) without re-running models.
    """
    run = history_store.get_run(run_id)
    if not run:
        flash(f"Run ID '{run_id}' not found in history store.", "warning")
        return redirect(url_for("history_dashboard"))

    return render_template(
        "history_run_detail.html",
        run=run,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
