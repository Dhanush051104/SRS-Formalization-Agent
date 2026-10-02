import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class CriticError(Exception):
    """Base exception for all Critic module errors."""
    pass


class CriticValidationError(CriticError):
    """Raised when Critic output fails schema validation, JSON structure, or field constraints."""
    pass


VALID_STATUSES = {"PASS", "NEEDS_REVISION", "BLOCKED"}
VALID_SEVERITIES = {"INFO", "WARNING", "ERROR"}


@dataclass
class CriticFinding:
    """
    Detailed, explainable finding produced by the Critic Model regarding a specific requirement constraint,
    actor, timing bound, assumption, or formalization detail.
    """
    category: str
    severity: str
    description: str
    source_evidence: str = ""
    reasoning_evidence: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert CriticFinding to a dictionary."""
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "source_evidence": self.source_evidence,
            "reasoning_evidence": self.reasoning_evidence,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriticFinding":
        """Construct CriticFinding from a dictionary."""
        sev = str(data.get("severity", "WARNING")).upper()
        if sev not in VALID_SEVERITIES:
            sev = "WARNING"

        return cls(
            category=str(data.get("category", "General")),
            severity=sev,
            description=str(data.get("description", "")),
            source_evidence=str(data.get("source_evidence", "")),
            reasoning_evidence=str(data.get("reasoning_evidence", "")),
            recommendation=str(data.get("recommendation", "")),
        )


@dataclass
class CriticResult:
    """
    Independent verification and critique result produced by a CriticModel.
    Inspected against original ContextPackage and candidate ReasoningResult.
    """
    requirement_id: int
    global_number: int
    srs_id: str
    status: str = "NEEDS_REVISION"
    findings: List[CriticFinding] = field(default_factory=list)
    missing_constraints: List[str] = field(default_factory=list)
    unsupported_assumptions: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    traceability_issues: List[str] = field(default_factory=list)
    pattern_coverage: Dict[str, Any] = field(default_factory=dict)
    formalization_assessment: str = ""
    revision_required: bool = False
    summary: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw_model_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert CriticResult instance to a Python dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "global_number": self.global_number,
            "srs_id": self.srs_id,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "missing_constraints": self.missing_constraints,
            "unsupported_assumptions": self.unsupported_assumptions,
            "contradictions": self.contradictions,
            "traceability_issues": self.traceability_issues,
            "pattern_coverage": self.pattern_coverage,
            "formalization_assessment": self.formalization_assessment,
            "revision_required": self.revision_required,
            "summary": self.summary,
            "provenance": self.provenance,
            "raw_model_response": self.raw_model_response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], raw_response: Optional[str] = None) -> "CriticResult":
        """
        Construct a CriticResult instance from a dictionary.

        Args:
            data: Dictionary containing expected keys.
            raw_response: Optional raw JSON text returned by model.

        Returns:
            CriticResult instance.
        """
        stat = str(data.get("status", "NEEDS_REVISION")).upper()
        if stat not in VALID_STATUSES:
            stat = "NEEDS_REVISION"

        raw_findings = data.get("findings", [])
        findings_objs: List[CriticFinding] = []
        if isinstance(raw_findings, list):
            for item in raw_findings:
                if isinstance(item, dict):
                    findings_objs.append(CriticFinding.from_dict(item))

        def _get_list(key: str) -> List[str]:
            val = data.get(key, [])
            if val is None:
                return []
            if not isinstance(val, list):
                raise CriticValidationError(f"CriticResult field '{key}' must be a list of strings, got {type(val).__name__}.")
            return [str(x) for x in val]

        rev_req = bool(data.get("revision_required", stat != "PASS"))

        return cls(
            requirement_id=int(data["requirement_id"]),
            global_number=int(data["global_number"]),
            srs_id=str(data["srs_id"]),
            status=stat,
            findings=findings_objs,
            missing_constraints=_get_list("missing_constraints"),
            unsupported_assumptions=_get_list("unsupported_assumptions"),
            contradictions=_get_list("contradictions"),
            traceability_issues=_get_list("traceability_issues"),
            pattern_coverage=dict(data.get("pattern_coverage", {})),
            formalization_assessment=str(data.get("formalization_assessment", "")),
            revision_required=rev_req,
            summary=str(data.get("summary", "")),
            provenance=dict(data.get("provenance", {})),
            raw_model_response=raw_response or data.get("raw_model_response"),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize CriticResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "CriticResult":
        """Parse a JSON string into a CriticResult instance."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data, raw_response=json_str)
        except Exception as e:
            raise CriticValidationError(f"Failed to parse CriticResult from JSON string: {e}")
