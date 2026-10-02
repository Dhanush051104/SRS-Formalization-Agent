from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.critic.schemas import (
    VALID_STATUSES,
    CriticResult,
    CriticValidationError,
)
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage


class CriticModel(ABC):
    """
    Abstract pluggable interface for SRS Formalization Critic / Verification models.
    """

    def validate_result(
        self,
        context_package: ContextPackage,
        reasoning_result: ReasoningResult,
        result: CriticResult,
    ) -> None:
        """
        Rigorously validates a CriticResult against input ContextPackage and ReasoningResult.

        Args:
            context_package: Original ContextPackage instance.
            reasoning_result: Candidate ReasoningResult instance.
            result: CriticResult to validate.

        Raises:
            CriticValidationError: If requirement identity or schema constraints fail.
        """
        if not context_package.requirements:
            raise CriticValidationError("ContextPackage must contain at least one RequirementContext.")

        req = context_package.requirements[0]

        # 1. Validate requirement identity matching
        if result.requirement_id != req.requirement_id:
            raise CriticValidationError(
                f"CriticResult requirement_id mismatch: expected {req.requirement_id}, got {result.requirement_id}."
            )

        if result.global_number != req.global_number:
            raise CriticValidationError(
                f"CriticResult global_number mismatch: expected {req.global_number}, got {result.global_number}."
            )

        clean_context_srs = req.srs_id.strip("[]")
        clean_result_srs = str(result.srs_id).strip("[]")
        if clean_context_srs != clean_result_srs:
            raise CriticValidationError(
                f"CriticResult srs_id mismatch: expected '{req.srs_id}', got '{result.srs_id}'."
            )

        # 2. Validate status
        if result.status not in VALID_STATUSES:
            raise CriticValidationError(
                f"CriticResult status must be one of {VALID_STATUSES}, got '{result.status}'."
            )

        # 3. Validate structural types
        list_fields = [
            ("findings", result.findings),
            ("missing_constraints", result.missing_constraints),
            ("unsupported_assumptions", result.unsupported_assumptions),
            ("contradictions", result.contradictions),
            ("traceability_issues", result.traceability_issues),
        ]

        for field_name, field_val in list_fields:
            if not isinstance(field_val, list):
                raise CriticValidationError(f"CriticResult field '{field_name}' must be a list.")

        if not isinstance(result.pattern_coverage, dict):
            raise CriticValidationError("CriticResult field 'pattern_coverage' must be a dictionary.")

        if not isinstance(result.summary, str):
            raise CriticValidationError("CriticResult field 'summary' must be a string.")

        # Attach provenance from ContextPackage if missing in result
        if not result.provenance and context_package.provenance:
            result.provenance = context_package.provenance

    @abstractmethod
    def critique(
        self,
        context_package: ContextPackage,
        reasoning_result: ReasoningResult,
    ) -> CriticResult:
        """
        Critiques a candidate ReasoningResult against the original ContextPackage and returns a validated CriticResult.

        Args:
            context_package: ContextPackage instance.
            reasoning_result: Candidate ReasoningResult instance.

        Returns:
            Validated CriticResult instance.
        """
        pass
