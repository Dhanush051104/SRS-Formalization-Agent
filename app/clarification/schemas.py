import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClarificationQuestion:
    """
    Structured clarification question identifying an unstated parameter, ambiguous actor,
    missing timing constraint, or unsupported assumption in an SRS requirement.
    """
    question_id: str
    requirement_srs_id: str
    category: str  # "UNRESOLVED_ITEM", "UNSUPPORTED_ASSUMPTION", "CRITIC_FINDING", "BLOCKED_FORMALIZATION"
    question_text: str
    reason: str
    related_constraint: str
    suggested_options: List[str] = field(default_factory=list)
    status: str = "OPEN"  # "OPEN", "ANSWERED"
    answer: Optional[str] = None
    answered_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert ClarificationQuestion to a dictionary."""
        return {
            "question_id": self.question_id,
            "requirement_srs_id": self.requirement_srs_id,
            "category": self.category,
            "question_text": self.question_text,
            "reason": self.reason,
            "related_constraint": self.related_constraint,
            "suggested_options": list(self.suggested_options),
            "status": self.status,
            "answer": self.answer,
            "answered_at": self.answered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClarificationQuestion":
        """Construct ClarificationQuestion from a dictionary."""
        raw_options = data.get("suggested_options", [])
        return cls(
            question_id=str(data["question_id"]),
            requirement_srs_id=str(data.get("requirement_srs_id", "")),
            category=str(data.get("category", "UNRESOLVED_ITEM")),
            question_text=str(data.get("question_text", "")),
            reason=str(data.get("reason", "")),
            related_constraint=str(data.get("related_constraint", "")),
            suggested_options=[str(opt) for opt in raw_options] if isinstance(raw_options, list) else [],
            status=str(data.get("status", "OPEN")),
            answer=data.get("answer"),
            answered_at=data.get("answered_at"),
        )


@dataclass
class ClarificationResult:
    """
    Collection of structured clarification questions generated for a requirement analysis.
    """
    requirement_id: int
    srs_id: str
    questions: List[ClarificationQuestion] = field(default_factory=list)
    total_questions: int = 0
    open_questions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert ClarificationResult to a dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "srs_id": self.srs_id,
            "questions": [q.to_dict() for q in self.questions],
            "total_questions": len(self.questions),
            "open_questions": sum(1 for q in self.questions if q.status == "OPEN"),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClarificationResult":
        """Construct ClarificationResult from a dictionary."""
        raw_questions = data.get("questions", [])
        question_objs = [
            ClarificationQuestion.from_dict(q) for q in raw_questions if isinstance(q, dict)
        ]
        return cls(
            requirement_id=int(data.get("requirement_id", 0)),
            srs_id=str(data.get("srs_id", "")),
            questions=question_objs,
            total_questions=len(question_objs),
            open_questions=sum(1 for q in question_objs if q.status == "OPEN"),
        )
