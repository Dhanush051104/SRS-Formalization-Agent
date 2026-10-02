import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class ReasoningError(Exception):
    """Base exception for all Reasoning module errors."""
    pass


class ReasoningValidationError(ReasoningError):
    """Raised when Reasoning output fails schema validation, JSON structure, or field constraints."""
    pass


@dataclass
class ReasoningResult:
    """
    Structured result produced by a ReasoningModel after processing a ContextPackage.
    Captures formalization, logical components, assumptions, unresolved items, and provenance.
    """
    requirement_id: int
    global_number: int
    srs_id: str
    interpretation: str = ""
    identified_entities: List[str] = field(default_factory=list)
    predicates: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    temporal_constraints: List[str] = field(default_factory=list)
    mathematical_constraints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    formalization: str = ""
    assumptions: List[str] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    reasoning_notes: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw_model_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ReasoningResult instance to a Python dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "global_number": self.global_number,
            "srs_id": self.srs_id,
            "interpretation": self.interpretation,
            "identified_entities": self.identified_entities,
            "predicates": self.predicates,
            "conditions": self.conditions,
            "actions": self.actions,
            "temporal_constraints": self.temporal_constraints,
            "mathematical_constraints": self.mathematical_constraints,
            "dependencies": self.dependencies,
            "formalization": self.formalization,
            "assumptions": self.assumptions,
            "unresolved_items": self.unresolved_items,
            "reasoning_notes": self.reasoning_notes,
            "provenance": self.provenance,
            "raw_model_response": self.raw_model_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], raw_response: Optional[str] = None) -> "ReasoningResult":
        """
        Construct a ReasoningResult instance from a dictionary.

        Args:
            data: Dictionary containing expected keys.
            raw_response: Optional raw JSON text returned by model.

        Returns:
            ReasoningResult instance.
        """
        def _get_list(key: str) -> List[str]:
            val = data.get(key, [])
            if val is None:
                return []
            if not isinstance(val, list):
                raise ReasoningValidationError(f"ReasoningResult field '{key}' must be a list of strings, got {type(val).__name__}.")
            return [str(x) for x in val]

        return cls(
            requirement_id=int(data["requirement_id"]),
            global_number=int(data["global_number"]),
            srs_id=str(data["srs_id"]),
            interpretation=str(data.get("interpretation", "")),
            identified_entities=_get_list("identified_entities"),
            predicates=_get_list("predicates"),
            conditions=_get_list("conditions"),
            actions=_get_list("actions"),
            temporal_constraints=_get_list("temporal_constraints"),
            mathematical_constraints=_get_list("mathematical_constraints"),
            dependencies=_get_list("dependencies"),
            formalization=str(data.get("formalization", "")),
            assumptions=_get_list("assumptions"),
            unresolved_items=_get_list("unresolved_items"),
            reasoning_notes=data.get("reasoning_notes"),
            provenance=dict(data.get("provenance", {})),
            raw_model_response=raw_response or data.get("raw_model_response"),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize the ReasoningResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ReasoningResult":
        """Parse a JSON string into a ReasoningResult instance."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data, raw_response=json_str)
        except Exception as e:
            raise ReasoningValidationError(f"Failed to parse ReasoningResult from JSON string: {e}")
