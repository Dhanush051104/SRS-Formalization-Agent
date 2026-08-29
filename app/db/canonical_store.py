import sqlite3
import os
from datetime import datetime

DEFAULT_DB_PATH = "srs_canonical.db"


def get_db_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DEFAULT_DB_PATH):
    """Initialize the SQLite database with the canonical schema."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Documents
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        uploaded_at TEXT NOT NULL
    );
    """)

    # 2. Pages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        page_number INTEGER NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    # 3. Elements (represent every raw parser line/element losslessly)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS elements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        page_number INTEGER NOT NULL,
        element_index INTEGER NOT NULL,
        parser_type TEXT NOT NULL,
        parser_style TEXT,
        classification TEXT NOT NULL,  -- 'regular_content', 'section_heading', 'requirement'
        raw_text TEXT NOT NULL,
        normalized_text TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    # 4. Sections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        number TEXT NOT NULL,
        title TEXT NOT NULL,
        page_number INTEGER,
        parent_number TEXT,
        element_index INTEGER NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    # 5. Requirements (SRS requirements)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        section_id INTEGER NOT NULL,
        section_number TEXT NOT NULL,
        srs_id TEXT NOT NULL,
        global_number INTEGER NOT NULL,
        source_number INTEGER NOT NULL,
        raw_text TEXT NOT NULL,
        normalized_text TEXT NOT NULL,
        page_number INTEGER,
        element_index INTEGER NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
    );
    """)

    # 6. Target Groups
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS target_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        section_number TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Ready for Analysis',
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """)

    # 7. Target Group Members
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS target_group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_group_id INTEGER NOT NULL,
        requirement_id INTEGER NOT NULL,
        selection_order INTEGER NOT NULL,
        FOREIGN KEY(target_group_id) REFERENCES target_groups(id) ON DELETE CASCADE,
        FOREIGN KEY(requirement_id) REFERENCES requirements(id) ON DELETE CASCADE,
        UNIQUE(target_group_id, requirement_id)
    );
    """)

    conn.commit()
    conn.close()


def store_srs(db_path, filename, filepath, parsed_elements, structured_doc, segmented_requirements):
    """
    Store the parsed, structured, and segmented document in the SQLite database.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # 1. Insert Document
        uploaded_at = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO documents (filename, filepath, uploaded_at) VALUES (?, ?, ?);",
            (filename, filepath, uploaded_at)
        )
        doc_id = cursor.lastrowid

        # 2. Insert Pages
        unique_pages = sorted(list(set(el.get("page") for el in parsed_elements if el.get("page") is not None)))
        for page_num in unique_pages:
            cursor.execute(
                "INSERT INTO pages (document_id, page_number) VALUES (?, ?);",
                (doc_id, page_num)
            )

        # 3. Insert Sections
        section_num_to_id = {}
        # We need to insert sections. However, structured_doc is a dictionary mapping section number -> section metadata.
        # The section metadata might not contain parent_number but it has "parent".
        # Let's sort sections by number length and value to make sure parent insertion is robust or just insert as they are.
        for number, sec_data in structured_doc.items():
            cursor.execute(
                """
                INSERT INTO sections (document_id, number, title, page_number, parent_number, element_index)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    sec_data["number"],
                    sec_data["title"],
                    sec_data["page"],
                    sec_data["parent"],
                    sec_data["_element_index"] if "_element_index" in sec_data else 0
                )
            )
            section_num_to_id[number] = cursor.lastrowid

        # 4. Insert Requirements (with sequential global_number)
        ordered_requirements = sorted(segmented_requirements, key=lambda r: r.get("_element_index", 0))
        
        req_mapping_by_index = {}
        
        for g_idx, req in enumerate(ordered_requirements, start=1):
            elem_idx = req.get("_element_index", 0)
            
            # Find the section this requirement belongs to
            # First, check if requirement has a section_number associated (the segmenter/cleaner might not add it)
            owning_section_num = req.get("section_number")
            if not owning_section_num:
                # Find the most recent section heading before this element index
                best_sec = None
                best_idx = -1
                for sec_num, sec_data in structured_doc.items():
                    sec_idx = sec_data.get("_element_index", 0)
                    if sec_idx <= elem_idx and sec_idx > best_idx:
                        best_idx = sec_idx
                        best_sec = sec_num
                owning_section_num = best_sec

            section_id = section_num_to_id.get(owning_section_num)
            if not section_id:
                section_id = section_num_to_id.get("3")
                owning_section_num = "3"

            # Extract source number
            source_num = req.get("local_number")
            if source_num is None:
                # Try to extract it
                import re
                match = re.match(r"^\s*(\d+)\.\s+", req["text"])
                if match:
                    source_num = int(match.group(1))
                else:
                    source_num = 0

            cursor.execute(
                """
                INSERT INTO requirements (document_id, section_id, section_number, srs_id, global_number, source_number, raw_text, normalized_text, page_number, element_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    section_id,
                    owning_section_num,
                    req["srs_id"],
                    g_idx,
                    source_num,
                    req.get("raw_text") or req["text"],
                    req["text"],
                    req.get("page"),
                    elem_idx
                )
            )
            req_mapping_by_index[elem_idx] = req

        # 5. Insert Elements with Classifications
        section_indices = {sec_data["_element_index"]: num for num, sec_data in structured_doc.items() if "_element_index" in sec_data}
        
        for idx, el in enumerate(parsed_elements):
            page_num = el.get("page") or 0
            raw_text = el.get("text", "")
            parser_type = el.get("type", "text")
            parser_style = el.get("style")
            
            # Classification
            if idx in section_indices:
                classification = "section_heading"
            elif idx in req_mapping_by_index:
                classification = "requirement"
            else:
                classification = "regular_content"

            cursor.execute(
                """
                INSERT INTO elements (document_id, page_number, element_index, parser_type, parser_style, classification, raw_text, normalized_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    doc_id,
                    page_num,
                    idx,
                    parser_type,
                    parser_style,
                    classification,
                    raw_text,
                    raw_text.strip()
                )
            )

        conn.commit()
        conn.close()
        return doc_id
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e


def check_and_rebuild_stale_db(db_path=DEFAULT_DB_PATH):
    """
    Check if the database contains sections with stale (0) element_index,
    and if so, clear the tables and re-ingest the document.
    """
    if not os.path.exists(db_path):
        return

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if sections table exists and has rows
    try:
        cursor.execute("SELECT COUNT(*) FROM sections;")
        has_sections = cursor.fetchone()[0] > 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        conn.close()
        return

    is_stale = False
    if has_sections:
        # Check if 3.2.1 has element_index = 0
        cursor.execute("SELECT element_index FROM sections WHERE number = '3.2.1';")
        row = cursor.fetchone()
        if row and row[0] == 0:
            is_stale = True

        # Check if Section 1 is missing (regression check for Milestone 1 section updates)
        cursor.execute("SELECT COUNT(*) FROM sections WHERE number = '1';")
        sec1_count = cursor.fetchone()[0]
        if sec1_count == 0:
            is_stale = True

    if is_stale:
        print("[WARNING] Stale database detected (sections have element_index=0). Rebuilding...")
        # Get list of documents in the database
        cursor.execute("SELECT filename, filepath FROM documents;")
        docs_to_reingest = [dict(r) for r in cursor.fetchall()]
        
        # Clear tables
        cursor.execute("DROP TABLE IF EXISTS requirements;")
        cursor.execute("DROP TABLE IF EXISTS sections;")
        cursor.execute("DROP TABLE IF EXISTS elements;")
        cursor.execute("DROP TABLE IF EXISTS pages;")
        cursor.execute("DROP TABLE IF EXISTS documents;")
        conn.commit()
        conn.close()
        
        # Initialize tables again
        init_db(db_path)
        
        # Re-ingest
        from app.parser.document_parser import parse_document
        from app.structurer.requirement_segmenter import RequirementSegmenter
        from app.structurer.document_cleaner import DocumentCleaner
        from app.structurer.document_structurer import DocumentStructurer
        
        for doc in docs_to_reingest:
            filename = doc["filename"]
            filepath = doc["filepath"]
            if os.path.exists(filepath):
                print(f"Re-ingesting '{filename}'...")
                try:
                    elements = parse_document(filepath)
                    segmenter = RequirementSegmenter()
                    raw_requirements = segmenter.segment(elements)
                    cleaner = DocumentCleaner()
                    requirements = [cleaner.clean_requirement(r) for r in raw_requirements]
                    structurer = DocumentStructurer(elements)
                    structured_doc = structurer.build()
                    structured_doc = structurer.add_requirements(structured_doc, requirements)
                    
                    store_srs(db_path, filename, filepath, elements, structured_doc, requirements)
                    print(f"Successfully re-ingested '{filename}'!")
                except Exception as ex:
                    print(f"Failed to re-ingest '{filename}': {ex}")
            else:
                print(f"Cannot re-ingest '{filename}', file not found at '{filepath}'")
    else:
        conn.close()
