import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.critic.schemas import CriticResult
from app.reasoning.schemas import ReasoningResult


class RevisionError(Exception):
    """Base exception for all Revision module errors."""
    pass


class RevisionValidationError(RevisionError):
    """Raised when Revision output or configuration fails validation."""
    pass


VALID_REVISION_STATUSES = {"PASS", "BLOCKED", "MAX_ITERATIONS"}
VALID_TERMINATION_REASONS = {"CRITIC_PASSED", "CRITIC_BLOCKED", "MAX_ITERATIONS_REACHED"}


@dataclass
class RevisionHistoryEntry:
    """
    Records the outcome of a single reasoning-critique iteration within the revision loop.
    """
    iteration: int
    reasoning_result: ReasoningResult
    critic_result: CriticResult
    revision_prompt_used: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert RevisionHistoryEntry to a Python dictionary."""
        return {
            "iteration": self.iteration,
            "reasoning_result": self.reasoning_result.to_dict(),
            "critic_result": self.critic_result.to_dict(),
            "revision_prompt_used": self.revision_prompt_used,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RevisionHistoryEntry":
        """Construct RevisionHistoryEntry from a Python dictionary."""
        rr_data = data.get("reasoning_result", {})
        cr_data = data.get("critic_result", {})

        return cls(
            iteration=int(data["iteration"]),
            reasoning_result=ReasoningResult.from_dict(rr_data) if isinstance(rr_data, dict) else rr_data,
            critic_result=CriticResult.from_dict(cr_data) if isinstance(cr_data, dict) else cr_data,
            revision_prompt_used=data.get("revision_prompt_used"),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass
class RevisionResult:
    """
    Final output produced by the RevisionManager after running the bounded revision loop.
    Captures the final reasoning/critic results, complete iteration history, status, and termination reason.
    """
    requirement_id: int
    global_number: int
    srs_id: str
    status: str
    final_reasoning_result: ReasoningResult
    final_critic_result: CriticResult
    iterations_conducted: int
    max_iterations: int
    history: List[RevisionHistoryEntry] = field(default_factory=list)
    termination_reason: str = "MAX_ITERATIONS_REACHED"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert RevisionResult to a Python dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "global_number": self.global_number,
            "srs_id": self.srs_id,
            "status": self.status,
            "final_reasoning_result": self.final_reasoning_result.to_dict(),
            "final_critic_result": self.final_critic_result.to_dict(),
            "iterations_conducted": self.iterations_conducted,
            "max_iterations": self.max_iterations,
            "history": [entry.to_dict() for entry in self.history],
            "termination_reason": self.termination_reason,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RevisionResult":
        """Construct RevisionResult from a Python dictionary."""
        stat = str(data.get("status", "MAX_ITERATIONS")).upper()
        if stat not in VALID_REVISION_STATUSES:
            stat = "MAX_ITERATIONS"

        term_reason = str(data.get("termination_reason", "MAX_ITERATIONS_REACHED")).upper()
        if term_reason not in VALID_TERMINATION_REASONS:
            term_reason = "MAX_ITERATIONS_REACHED"

        raw_history = data.get("history", [])
        history_objs: List[RevisionHistoryEntry] = []
        if isinstance(raw_history, list):
            for item in raw_history:
                if isinstance(item, dict):
                    history_objs.append(RevisionHistoryEntry.from_dict(item))

        rr_data = data.get("final_reasoning_result", {})
        cr_data = data.get("final_critic_result", {})

        return cls(
            requirement_id=int(data["requirement_id"]),
            global_number=int(data["global_number"]),
            srs_id=str(data["srs_id"]),
            status=stat,
            final_reasoning_result=ReasoningResult.from_dict(rr_data) if isinstance(rr_data, dict) else rr_data,
            final_critic_result=CriticResult.from_dict(cr_data) if isinstance(cr_data, dict) else cr_data,
            iterations_conducted=int(data.get("iterations_conducted", 1)),
            max_iterations=int(data.get("max_iterations", 3)),
            history=history_objs,
            termination_reason=term_reason,
            provenance=dict(data.get("provenance", {})),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize RevisionResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "RevisionResult":
        """Parse a JSON string into a RevisionResult instance."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except Exception as e:
            raise RevisionValidationError(f"Failed to parse RevisionResult from JSON string: {e}")
