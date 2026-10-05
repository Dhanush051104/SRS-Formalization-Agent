from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.reasoning.schemas import ReasoningResult, ReasoningValidationError
from app.retrieval.context_builder import ContextPackage


class ReasoningModel(ABC):
    """
    Abstract pluggable interface for SRS Formalization Reasoning models.
    """

    def validate_result(
        self,
        context_package: ContextPackage,
        result: ReasoningResult,
    ) -> None:
        """
        Rigorously validates a ReasoningResult against input ContextPackage.

        Args:
            context_package: Input ContextPackage instance.
            result: ReasoningResult to validate.

        Raises:
            ReasoningValidationError: If requirement identity or structural constraints fail.
        """
        if not context_package.requirements:
            raise ReasoningValidationError("ContextPackage must contain at least one RequirementContext.")

        req = context_package.requirements[0]

        # 1. Validate requirement identity fields
        if result.requirement_id != req.requirement_id:
            raise ReasoningValidationError(
                f"ReasoningResult requirement_id mismatch: expected {req.requirement_id}, got {result.requirement_id}."
            )

        if result.global_number != req.global_number:
            raise ReasoningValidationError(
                f"ReasoningResult global_number mismatch: expected {req.global_number}, got {result.global_number}."
            )

        clean_context_srs = req.srs_id.strip("[]")
        clean_result_srs = str(result.srs_id).strip("[]")
        if clean_context_srs != clean_result_srs:
            raise ReasoningValidationError(
                f"ReasoningResult srs_id mismatch: expected '{req.srs_id}', got '{result.srs_id}'."
            )

        # 2. Validate structural types
        list_fields = [
            ("identified_entities", result.identified_entities),
            ("predicates", result.predicates),
            ("conditions", result.conditions),
            ("actions", result.actions),
            ("temporal_constraints", result.temporal_constraints),
            ("mathematical_constraints", result.mathematical_constraints),
            ("dependencies", result.dependencies),
            ("assumptions", result.assumptions),
            ("unresolved_items", result.unresolved_items),
        ]

        for field_name, field_val in list_fields:
            if not isinstance(field_val, list):
                raise ReasoningValidationError(f"ReasoningResult field '{field_name}' must be a list.")

        if not isinstance(result.interpretation, str):
            raise ReasoningValidationError("ReasoningResult field 'interpretation' must be a string.")

        if not isinstance(result.formalization, str):
            raise ReasoningValidationError("ReasoningResult field 'formalization' must be a string.")

        # Attach provenance from ContextPackage if missing in result
        if not result.provenance and context_package.provenance:
            result.provenance = context_package.provenance

    @abstractmethod
    def reason(
        self,
        context_package: ContextPackage,
        user_prompt: Optional[str] = None,
    ) -> ReasoningResult:
        """
        Processes a ContextPackage and returns a validated ReasoningResult.

        Args:
            context_package: ContextPackage instance containing SRS data and retrieved knowledge.
            user_prompt: Optional customized user prompt (e.g. including Critic feedback during revision).

        Returns:
            Validated ReasoningResult instance.
        """
        pass
