import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


class ObsidianRetrieverError(Exception):
    """Base exception for ObsidianRetriever errors."""
    pass


class VaultNotFoundError(ObsidianRetrieverError):
    """Raised when the specified Obsidian vault root directory does not exist."""
    pass


class RegistryNotFoundError(ObsidianRetrieverError):
    """Raised when Pattern-Registry.json is missing in the vault."""
    pass


class InvalidRegistryError(ObsidianRetrieverError):
    """Raised when Pattern-Registry.json is malformed or invalid JSON."""
    pass


class UnsafePathError(ObsidianRetrieverError):
    """Raised when a path in Pattern-Registry.json attempts traversal outside the vault or is absolute."""
    pass


class UnknownPatternError(ObsidianRetrieverError):
    """Raised when a requested pattern name is not found in Pattern-Registry.json."""
    pass


class MissingKnowledgeFileError(ObsidianRetrieverError):
    """Raised when a Markdown file referenced in Pattern-Registry.json does not exist on disk."""
    pass


@dataclass
class NoteContent:
    """Represents the raw loaded content of a Markdown note from SRS-Knowledge."""
    file_path: str
    content: str


@dataclass
class PatternRetrievalItem:
    """Structured retrieval output for a single requested pattern."""
    requested_pattern: str
    pattern_id: str
    pattern_file_path: str
    pattern_note: NoteContent
    formalization_notes: List[NoteContent]
    concept_notes: List[NoteContent]


@dataclass
class RetrievalResult:
    """Container for the complete structured retrieval output."""
    pattern_items: List[PatternRetrievalItem]
    loaded_files_count: int
    read_cache_hits: int


class ObsidianRetriever:
    """
    Deterministic Python retrieval component for the SRS-Knowledge Obsidian vault.

    Translates exact Analyst pattern names into structured engineering, domain,
    and formalization knowledge notes without LLM or GUI dependencies.
    """

    def __init__(
        self,
        vault_root: Optional[Union[Path, str]] = None,
        registry_rel_path: str = "Index/Pattern-Registry.json",
    ) -> None:
        """
        Initialize the ObsidianRetriever.

        Args:
            vault_root: Path to the SRS-Knowledge directory. If None, resolves
                        robustly relative to the project root directory.
            registry_rel_path: Relative path to Pattern-Registry.json from vault_root.
        """
        if vault_root is None:
            # Resolve project root relative to app/retrieval/obsidian_retriever.py location
            project_root = Path(__file__).resolve().parent.parent.parent
            vault_root = project_root / "SRS-Knowledge"

        self.vault_root = Path(vault_root).resolve()
        self.registry_rel_path = registry_rel_path
        self.registry_path = self.vault_root / self.registry_rel_path

        self.registry: Dict[str, Any] = {}
        self._load_and_validate_registry()

    def _validate_path_safety(self, rel_path_str: str) -> Path:
        """
        Validates that a relative path stays strictly within the vault_root.

        Raises:
            UnsafePathError: If path is absolute or attempts traversal outside the vault.
        """
        rel_path = Path(rel_path_str)
        if rel_path.is_absolute():
            raise UnsafePathError(f"Absolute path in registry is forbidden: '{rel_path_str}'")

        try:
            resolved_path = (self.vault_root / rel_path).resolve()
            resolved_path.relative_to(self.vault_root)
        except (ValueError, RuntimeError):
            raise UnsafePathError(
                f"Registry path '{rel_path_str}' attempts traversal outside vault root '{self.vault_root}'."
            )

        return resolved_path

    def _load_and_validate_registry(self) -> None:
        """
        Loads and validates Pattern-Registry.json.

        Raises:
            VaultNotFoundError, RegistryNotFoundError, InvalidRegistryError, UnsafePathError
        """
        if not self.vault_root.exists() or not self.vault_root.is_dir():
            raise VaultNotFoundError(f"Obsidian vault directory not found: '{self.vault_root}'")

        if not self.registry_path.exists():
            raise RegistryNotFoundError(f"Pattern registry file not found: '{self.registry_path}'")

        self._validate_path_safety(self.registry_rel_path)

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise InvalidRegistryError(f"Failed to parse registry JSON at '{self.registry_path}': {e}")

        if not isinstance(data, dict):
            raise InvalidRegistryError("Pattern-Registry.json top-level element must be a JSON object.")

        for pattern_name, entry in data.items():
            if not isinstance(entry, dict):
                raise InvalidRegistryError(f"Entry for pattern '{pattern_name}' must be an object.")

            for required_field in ("id", "pattern_file", "formalization_notes", "concept_notes"):
                if required_field not in entry:
                    raise InvalidRegistryError(
                        f"Pattern '{pattern_name}' entry missing required field '{required_field}'."
                    )

            if not isinstance(entry["formalization_notes"], list) or not isinstance(entry["concept_notes"], list):
                raise InvalidRegistryError(
                    f"Pattern '{pattern_name}' formalization_notes and concept_notes must be lists."
                )

            # Validate path safety for all entries in registry
            self._validate_path_safety(entry["pattern_file"])
            for fn_path in entry["formalization_notes"]:
                self._validate_path_safety(fn_path)
            for cn_path in entry["concept_notes"]:
                self._validate_path_safety(cn_path)

        self.registry = data

    def retrieve_patterns(self, pattern_names: List[str]) -> RetrievalResult:
        """
        Retrieve knowledge notes for an exact list of pattern names.

        Args:
            pattern_names: List of exact Analyst pattern names.

        Returns:
            RetrievalResult containing pattern items, loaded files count, and cache hit metrics.

        Raises:
            UnknownPatternError: If a pattern name is not found in the registry.
            MissingKnowledgeFileError: If a referenced Markdown note file is missing.
            UnsafePathError: If path safety checks fail.
        """
        file_cache: Dict[str, NoteContent] = {}
        loaded_files_count = 0
        read_cache_hits = 0

        def read_note(rel_path_str: str) -> NoteContent:
            nonlocal loaded_files_count, read_cache_hits

            if rel_path_str in file_cache:
                read_cache_hits += 1
                return file_cache[rel_path_str]

            full_path = self._validate_path_safety(rel_path_str)

            if not full_path.exists() or not full_path.is_file():
                raise MissingKnowledgeFileError(
                    f"Referenced knowledge note file missing on disk: '{rel_path_str}' (resolved to '{full_path}')."
                )

            content = full_path.read_text(encoding="utf-8")
            note = NoteContent(file_path=rel_path_str, content=content)
            file_cache[rel_path_str] = note
            loaded_files_count += 1
            return note

        pattern_items: List[PatternRetrievalItem] = []

        for name in pattern_names:
            if name not in self.registry:
                raise UnknownPatternError(
                    f"Pattern '{name}' is not recognized in Pattern-Registry.json. Exact match required."
                )

            entry = self.registry[name]

            pattern_note = read_note(entry["pattern_file"])
            formalization_notes = [read_note(fn_path) for fn_path in entry["formalization_notes"]]
            concept_notes = [read_note(cn_path) for cn_path in entry["concept_notes"]]

            item = PatternRetrievalItem(
                requested_pattern=name,
                pattern_id=entry["id"],
                pattern_file_path=entry["pattern_file"],
                pattern_note=pattern_note,
                formalization_notes=formalization_notes,
                concept_notes=concept_notes,
            )
            pattern_items.append(item)

        return RetrievalResult(
            pattern_items=pattern_items,
            loaded_files_count=loaded_files_count,
            read_cache_hits=read_cache_hits,
        )
