import sqlite3
import os
from datetime import datetime
from app.db.canonical_store import get_db_connection

def create_target_group(db_path, document_id, section_number, requirement_ids):
    """
    Create a new target group and associate it with the given canonical requirements.
    Performs rigorous validations as requested:
    - Document exists
    - Section exists in that document
    - Every requirement ID exists
    - Every requirement belongs to that document
    - Every requirement belongs to the specified section
    - No requirement ID is duplicated in the selection
    """
    if not requirement_ids:
        raise ValueError("At least one requirement must be selected to create a target group.")

    # 1. Check for duplicates in input
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Duplicate requirement IDs are not allowed in a target group.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # 2. Check document exists
        cursor.execute("SELECT id FROM documents WHERE id = ?;", (document_id,))
        if not cursor.fetchone():
            raise ValueError(f"Document with ID {document_id} does not exist.")

        # 3. Check section exists in that document
        cursor.execute(
            "SELECT id FROM sections WHERE document_id = ? AND number = ?;",
            (document_id, section_number)
        )
        if not cursor.fetchone():
            raise ValueError(f"Section '{section_number}' does not exist in document {document_id}.")

        # 4. Check each requirement
        for r_id in requirement_ids:
            cursor.execute(
                "SELECT id, document_id, section_number FROM requirements WHERE id = ?;",
                (r_id,)
            )
            req = cursor.fetchone()
            if not req:
                raise ValueError(f"Requirement with ID {r_id} does not exist.")
            
            if req["document_id"] != document_id:
                raise ValueError(f"Requirement {r_id} does not belong to document {document_id}.")
                
            if req["section_number"] != section_number:
                raise ValueError(f"Requirement {r_id} belongs to section '{req['section_number']}', expected '{section_number}'.")

        # 5. Insert Target Group
        created_at = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO target_groups (document_id, section_number, created_at, status)
            VALUES (?, ?, ?, ?);
            """,
            (document_id, section_number, created_at, 'Ready for Analysis')
        )
        group_id = cursor.lastrowid

        # 6. Insert Members
        for order, r_id in enumerate(requirement_ids, start=1):
            cursor.execute(
                """
                INSERT INTO target_group_members (target_group_id, requirement_id, selection_order)
                VALUES (?, ?, ?);
                """,
                (group_id, r_id, order)
            )

        conn.commit()
        return group_id
    except sqlite3.IntegrityError as ie:
        conn.rollback()
        raise ValueError(f"Database integrity violation while creating target group: {ie}")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_target_group(db_path, target_group_id):
    """
    Retrieve target group metadata and its member requirements in selection order.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    try:
        # Fetch group metadata
        cursor.execute("SELECT * FROM target_groups WHERE id = ?;", (target_group_id,))
        group_row = cursor.fetchone()
        if not group_row:
            return None
            
        group = dict(group_row)
        
        # Fetch group members joined with requirements to get full details
        cursor.execute(
            """
            SELECT r.*, m.selection_order 
            FROM target_group_members m
            JOIN requirements r ON m.requirement_id = r.id
            WHERE m.target_group_id = ?
            ORDER BY m.selection_order ASC;
            """,
            (target_group_id,)
        )
        members = [dict(row) for row in cursor.fetchall()]
        group["requirements"] = members
        return group
    finally:
        conn.close()


def add_requirement_to_group(db_path, target_group_id, requirement_id):
    """
    Add a requirement to an existing target group.
    Validates:
    - Group exists
    - Requirement exists
    - Requirement belongs to the group's document and section
    - Requirement is not already in the group (UNIQUE)
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # 1. Fetch group
        cursor.execute("SELECT document_id, section_number FROM target_groups WHERE id = ?;", (target_group_id,))
        group = cursor.fetchone()
        if not group:
            raise ValueError(f"Target Group {target_group_id} does not exist.")
            
        doc_id = group["document_id"]
        sec_num = group["section_number"]

        # 2. Fetch requirement
        cursor.execute("SELECT id, document_id, section_number FROM requirements WHERE id = ?;", (requirement_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError(f"Requirement {requirement_id} does not exist.")
            
        if req["document_id"] != doc_id:
            raise ValueError(f"Requirement {requirement_id} does not belong to group document {doc_id}.")
            
        if req["section_number"] != sec_num:
            raise ValueError(f"Requirement {requirement_id} belongs to section '{req['section_number']}', expected '{sec_num}'.")

        # 3. Check for duplicates in group members
        cursor.execute(
            "SELECT id FROM target_group_members WHERE target_group_id = ? AND requirement_id = ?;",
            (target_group_id, requirement_id)
        )
        if cursor.fetchone():
            raise ValueError(f"Requirement {requirement_id} is already in target group {target_group_id}.")

        # 4. Get current max order
        cursor.execute(
            "SELECT MAX(selection_order) FROM target_group_members WHERE target_group_id = ?;",
            (target_group_id,)
        )
        max_order_row = cursor.fetchone()
        max_order = max_order_row[0] if max_order_row[0] is not None else 0

        # 5. Insert
        cursor.execute(
            """
            INSERT INTO target_group_members (target_group_id, requirement_id, selection_order)
            VALUES (?, ?, ?);
            """,
            (target_group_id, requirement_id, max_order + 1)
        )
        conn.commit()
    except sqlite3.IntegrityError as ie:
        conn.rollback()
        raise ValueError(f"Database uniqueness constraint violated: {ie}")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def remove_requirement_from_group(db_path, target_group_id, requirement_id):
    """
    Remove a requirement from a group.
    - Re-indexes the selection_order of the remaining requirements.
    - If the group becomes empty, cancels (deletes) the group.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        # Check target group exists
        cursor.execute("SELECT id FROM target_groups WHERE id = ?;", (target_group_id,))
        if not cursor.fetchone():
            raise ValueError(f"Target Group {target_group_id} does not exist.")

        # Delete member
        cursor.execute(
            "DELETE FROM target_group_members WHERE target_group_id = ? AND requirement_id = ?;",
            (target_group_id, requirement_id)
        )

        # Check remaining count
        cursor.execute(
            "SELECT id, requirement_id FROM target_group_members WHERE target_group_id = ? ORDER BY selection_order ASC;",
            (target_group_id,)
        )
        remaining = cursor.fetchall()
        
        if not remaining:
            # Cancel group if empty
            cursor.execute("DELETE FROM target_groups WHERE id = ?;", (target_group_id,))
        else:
            # Re-index selection_order
            for new_order, row in enumerate(remaining, start=1):
                cursor.execute(
                    "UPDATE target_group_members SET selection_order = ? WHERE id = ?;",
                    (new_order, row["id"])
                )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def cancel_target_group(db_path, target_group_id):
    """
    Delete a target group completely. Members are deleted by foreign key cascade constraints.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        cursor.execute("DELETE FROM target_groups WHERE id = ?;", (target_group_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
