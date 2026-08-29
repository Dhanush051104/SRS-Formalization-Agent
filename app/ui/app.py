import os
import sys
import sqlite3
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

app = Flask(__name__)
app.secret_key = "srs_formalization_secret_key"
UPLOAD_FOLDER = "data"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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
    return render_template("index.html", documents=documents)


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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
