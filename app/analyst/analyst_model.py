import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union

from app.analyst.schemas import (
    AnalystResult,
    AnalystValidationError,
    NonCanonicalPatternError,
)
from app.retrieval.sqlite_retriever import RequirementContext

DEFAULT_REGISTRY_PATH = Path("SRS-Knowledge") / "Index" / "Pattern-Registry.json"


class AnalystModel(ABC):
    """
    Abstract pluggable interface for SRS Formalization Analyst models.
    """

    def __init__(self, registry_path: Optional[Union[Path, str]] = None) -> None:
        """
        Initialize the AnalystModel.

        Args:
            registry_path: Path to Pattern-Registry.json. If None, resolved
                           robustly relative to the project repository root.
        """
        if registry_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            registry_path = project_root / DEFAULT_REGISTRY_PATH
        
        self.registry_path = Path(registry_path).resolve()

    def load_pattern_catalog(self) -> List[str]:
        """
        Loads the exact canonical pattern names directly from Pattern-Registry.json.

        Returns:
            List of exact pattern name strings.

        Raises:
            FileNotFoundError: If Pattern-Registry.json is not found.
            ValueError: If Pattern-Registry.json is invalid JSON.
        """
        if not self.registry_path.exists():
            raise FileNotFoundError(
                f"Canonical pattern registry file not found at: '{self.registry_path}'"
            )

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Pattern-Registry.json root structure must be a JSON object.")

            return list(data.keys())
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise e
            raise ValueError(f"Failed to load canonical pattern catalog from '{self.registry_path}': {e}")

    def validate_result(
        self,
        requirement_context: RequirementContext,
        result: AnalystResult,
        pattern_catalog: List[str],
    ) -> None:
        """
        Rigorously validates an AnalystResult against input RequirementContext and canonical catalog.

        Args:
            requirement_context: Input RequirementContext instance.
            result: AnalystResult to validate.
            pattern_catalog: List of exact canonical pattern names.

        Raises:
            AnalystValidationError: If requirement metadata, schema fields, or duplicate constraints fail.
            NonCanonicalPatternError: If an identified pattern is not present in pattern_catalog.
        """
        # 1. Validate requirement identity fields
        if result.requirement_id != requirement_context.requirement_id:
            raise AnalystValidationError(
                f"AnalystResult requirement_id mismatch: expected {requirement_context.requirement_id}, got {result.requirement_id}."
            )

        if result.global_number != requirement_context.global_number:
            raise AnalystValidationError(
                f"AnalystResult global_number mismatch: expected {requirement_context.global_number}, got {result.global_number}."
            )

        # Allow matching with or without brackets e.g. "SRS178" vs "[SRS178]"
        clean_context_srs = requirement_context.srs_id.strip("[]")
        clean_result_srs = str(result.srs_id).strip("[]")
        if clean_context_srs != clean_result_srs:
            raise AnalystValidationError(
                f"AnalystResult srs_id mismatch: expected '{requirement_context.srs_id}', got '{result.srs_id}'."
            )

        # 2. Validate identified_patterns structure & uniqueness
        if not isinstance(result.identified_patterns, list):
            raise AnalystValidationError("identified_patterns must be a list of strings.")

        seen_patterns = set()
        for pat in result.identified_patterns:
            if not isinstance(pat, str):
                raise AnalystValidationError(f"Pattern name must be a string, got: {type(pat).__name__}")
            if pat in seen_patterns:
                raise AnalystValidationError(f"Duplicate pattern name found in identified_patterns: '{pat}'")
            seen_patterns.add(pat)

        # 3. Canonical pattern validation (Strict match against registry keys)
        catalog_set = set(pattern_catalog)
        for pat in result.identified_patterns:
            if pat not in catalog_set:
                raise NonCanonicalPatternError(
                    f"Non-canonical pattern name identified by Analyst: '{pat}'. "
                    f"Must strictly match a key in Pattern-Registry.json."
                )

        # 4. Validate evidence structure
        if not isinstance(result.evidence, dict):
            raise AnalystValidationError("evidence must be a dictionary mapping pattern names to quotes/reasoning.")

        # 5. Validate missing_information structure
        if not isinstance(result.missing_information, list):
            raise AnalystValidationError("missing_information must be a list of strings.")

    @abstractmethod
    def analyze(self, requirement_context: RequirementContext) -> AnalystResult:
        """
        Analyzes a single RequirementContext and returns a validated AnalystResult.

        Args:
            requirement_context: RequirementContext instance retrieved from SQLite.

        Returns:
            Validated AnalystResult instance.
        """
        pass
