import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class AnalystError(Exception):
    """Base exception for all Analyst module errors."""
    pass


class AnalystValidationError(AnalystError):
    """Raised when Analyst output fails schema validation, JSON structure, or field constraints."""
    pass


class NonCanonicalPatternError(AnalystValidationError):
    """Raised when an identified pattern name is not present in the canonical Pattern-Registry.json."""
    pass


@dataclass
class AnalystResult:
    """
    Structured result produced by an AnalystModel after analyzing a RequirementContext.
    """
    requirement_id: int
    global_number: int
    srs_id: str
    identified_patterns: List[str] = field(default_factory=list)
    evidence: Dict[str, str] = field(default_factory=dict)
    missing_information: List[str] = field(default_factory=list)
    raw_model_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AnalystResult instance to a Python dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "global_number": self.global_number,
            "srs_id": self.srs_id,
            "identified_patterns": self.identified_patterns,
            "evidence": self.evidence,
            "missing_information": self.missing_information,
            "raw_model_response": self.raw_model_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], raw_response: Optional[str] = None) -> "AnalystResult":
        """
        Construct an AnalystResult instance from a dictionary.
        
        Args:
            data: Dictionary containing expected keys.
            raw_response: Optional raw JSON text returned by model.
            
        Returns:
            AnalystResult instance.
        """
        return cls(
            requirement_id=int(data["requirement_id"]),
            global_number=int(data["global_number"]),
            srs_id=str(data["srs_id"]),
            identified_patterns=list(data.get("identified_patterns", [])),
            evidence=dict(data.get("evidence", {})),
            missing_information=list(data.get("missing_information", [])),
            raw_model_response=raw_response or data.get("raw_model_response"),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize the AnalystResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "AnalystResult":
        """Parse a JSON string into an AnalystResult instance."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data, raw_response=json_str)
        except Exception as e:
            raise AnalystValidationError(f"Failed to parse AnalystResult from JSON string: {e}")
