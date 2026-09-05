import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.db.canonical_store import DEFAULT_DB_PATH, get_db_connection


class SQLiteRetrieverError(Exception):
    """Base exception for SQLiteRetriever errors."""
    pass


class DatabaseConnectionError(SQLiteRetrieverError):
    """Raised when connecting to or querying the SQLite database fails."""
    pass


class RequirementNotFoundError(SQLiteRetrieverError):
    """Raised when a requested requirement is not found in the SQLite database."""
    pass


@dataclass
class RequirementContext:
    """Dataclass holding canonical SRS requirement details retrieved from SQLite."""
    requirement_id: int
    global_number: int
    source_number: int
    srs_id: str
    section_number: str
    section_title: Optional[str]
    raw_text: str
    normalized_text: str
    page_number: Optional[int]
    element_index: int
    document_id: int
    source_dependencies: List[str] = field(default_factory=list)


class SQLiteRetriever:
    """
    Deterministic Python retriever component for canonical SRS data from SQLite.
    """

    def __init__(self, db_path: Optional[Union[Path, str]] = None) -> None:
        """
        Initialize the SQLiteRetriever.

        Args:
            db_path: Path to the srs_canonical.db file. If None, resolves
                     robustly relative to the project root directory.
        """
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            db_path = project_root / DEFAULT_DB_PATH

        self.db_path = Path(db_path).resolve()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes and returns an SQLite database connection."""
        if not self.db_path.exists():
            raise DatabaseConnectionError(f"SQLite database file not found: '{self.db_path}'")
        try:
            return get_db_connection(self.db_path)
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to SQLite database at '{self.db_path}': {e}")

    def _row_to_requirement_context(self, row: sqlite3.Row, conn: sqlite3.Connection) -> RequirementContext:
        """Converts an SQLite row into a RequirementContext object."""
        section_title: Optional[str] = None
        if "section_title" in row.keys() and row["section_title"] is not None:
            section_title = row["section_title"]
        elif row["section_id"]:
            cur = conn.cursor()
            cur.execute("SELECT title FROM sections WHERE id = ?", (row["section_id"],))
            sec_row = cur.fetchone()
            if sec_row and sec_row["title"]:
                section_title = sec_row["title"]

        # Canonical database schema does not have a dependencies table; source_dependencies is empty list
        return RequirementContext(
            requirement_id=row["id"],
            global_number=row["global_number"],
            source_number=row["source_number"],
            srs_id=row["srs_id"],
            section_number=row["section_number"],
            section_title=section_title,
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            page_number=row["page_number"],
            element_index=row["element_index"],
            document_id=row["document_id"],
            source_dependencies=[],
        )

    def get_requirement_by_id(self, requirement_id: int) -> RequirementContext:
        """
        Retrieve requirement context by database primary key ID.

        Args:
            requirement_id: Primary key ID in requirements table.

        Returns:
            RequirementContext dataclass.

        Raises:
            RequirementNotFoundError: If requirement ID does not exist.
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.*, s.title as section_title
                FROM requirements r
                LEFT JOIN sections s ON r.section_id = s.id
                WHERE r.id = ?
            """,
                (requirement_id,),
            )
            row = cur.fetchone()
            if not row:
                raise RequirementNotFoundError(
                    f"Requirement with database ID {requirement_id} not found in SQLite database."
                )
            return self._row_to_requirement_context(row, conn)
        finally:
            conn.close()

    def get_requirement_by_global_number(self, global_number: int) -> RequirementContext:
        """
        Retrieve requirement context by sequential global requirement number (e.g., 8 for R8).

        Args:
            global_number: Global requirement number.

        Returns:
            RequirementContext dataclass.

        Raises:
            RequirementNotFoundError: If global number does not exist.
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.*, s.title as section_title
                FROM requirements r
                LEFT JOIN sections s ON r.section_id = s.id
                WHERE r.global_number = ?
            """,
                (global_number,),
            )
            row = cur.fetchone()
            if not row:
                raise RequirementNotFoundError(
                    f"Requirement with global number R{global_number} not found in SQLite database."
                )
            return self._row_to_requirement_context(row, conn)
        finally:
            conn.close()

    def get_requirement_by_srs_id(self, srs_id: str) -> RequirementContext:
        """
        Retrieve requirement context by SRS identifier (e.g., "SRS178" or "[SRS178]").

        Args:
            srs_id: SRS identifier string.

        Returns:
            RequirementContext dataclass.

        Raises:
            RequirementNotFoundError: If SRS identifier is not found.
        """
        clean_id = srs_id.strip()
        bracket_id = f"[{clean_id.strip('[]')}]"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.*, s.title as section_title
                FROM requirements r
                LEFT JOIN sections s ON r.section_id = s.id
                WHERE r.srs_id = ? OR r.srs_id = ?
            """,
                (clean_id, bracket_id),
            )
            row = cur.fetchone()
            if not row:
                raise RequirementNotFoundError(
                    f"Requirement with SRS ID '{srs_id}' not found in SQLite database."
                )
            return self._row_to_requirement_context(row, conn)
        finally:
            conn.close()

    def get_requirements_by_ids(self, requirement_ids: List[int]) -> List[RequirementContext]:
        """
        Retrieve requirement contexts for a list of requirement primary key IDs.
        Preserves input requirement ordering.

        Args:
            requirement_ids: List of database requirement IDs.

        Returns:
            List of RequirementContext objects in input order.
        """
        results: List[RequirementContext] = []
        for req_id in requirement_ids:
            results.append(self.get_requirement_by_id(req_id))
        return results
