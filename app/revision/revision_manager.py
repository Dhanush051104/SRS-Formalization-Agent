from typing import List, Optional

from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage
from app.revision.revision_prompt import build_revision_user_prompt
from app.revision.schemas import (
    RevisionHistoryEntry,
    RevisionResult,
    RevisionValidationError,
)


class RevisionManager:
    """
    Orchestrates the bounded automated revision loop between ReasoningModel and CriticModel.
    Runs iteratively up to max_iterations, forwarding full Critic findings to ReasoningModel
    on each iteration, terminating immediately on PASS, BLOCKED, or max_iterations reached.
    """

    def __init__(
        self,
        reasoning_model: ReasoningModel,
        critic_model: CriticModel,
        max_iterations: int = 3,
    ) -> None:
        """
        Initialize the RevisionManager.

        Args:
            reasoning_model: Instantiated ReasoningModel adapter.
            critic_model: Instantiated CriticModel adapter.
            max_iterations: Maximum allowed revision iterations (must be >= 1).

        Raises:
            RevisionValidationError: If max_iterations < 1.
        """
        if max_iterations < 1:
            raise RevisionValidationError(f"max_iterations must be at least 1, got {max_iterations}.")

        self.reasoning_model = reasoning_model
        self.critic_model = critic_model
        self.max_iterations = max_iterations

    def run_revision_loop(self, context_package: ContextPackage) -> RevisionResult:
        """
        Runs the bounded automated reasoning-critique revision loop for a ContextPackage.

        Args:
            context_package: Input ContextPackage containing requirement data and retrieved knowledge.

        Returns:
            RevisionResult containing final results, iteration count, and full history.

        Raises:
            RevisionValidationError: If ContextPackage contains no requirements.
        """
        if not context_package.requirements:
            raise RevisionValidationError("ContextPackage must contain at least one RequirementContext.")

        req = context_package.requirements[0]
        history: List[RevisionHistoryEntry] = []

        current_prompt_override: Optional[str] = None
        final_reasoning_result: Optional[ReasoningResult] = None
        final_critic_result: Optional[CriticResult] = None
        final_status: str = "MAX_ITERATIONS"
        termination_reason: str = "MAX_ITERATIONS_REACHED"

        for iteration in range(1, self.max_iterations + 1):
            # 1. Execute ReasoningModel
            reasoning_res = self.reasoning_model.reason(
                context_package,
                user_prompt=current_prompt_override,
            )
            final_reasoning_result = reasoning_res

            # 2. Execute CriticModel
            critic_res = self.critic_model.critique(
                context_package,
                reasoning_res,
            )
            final_critic_result = critic_res

            # 3. Record history entry
            entry = RevisionHistoryEntry(
                iteration=iteration,
                reasoning_result=reasoning_res,
                critic_result=critic_res,
                revision_prompt_used=current_prompt_override,
            )
            history.append(entry)

            # 4. Check Critic status for early termination or next prompt construction
            status_upper = critic_res.status.upper()
            if status_upper == "PASS":
                final_status = "PASS"
                termination_reason = "CRITIC_PASSED"
                break
            elif status_upper == "BLOCKED":
                final_status = "BLOCKED"
                termination_reason = "CRITIC_BLOCKED"
                break
            elif status_upper == "NEEDS_REVISION":
                if iteration < self.max_iterations:
                    # Construct prompt override for next iteration
                    current_prompt_override = build_revision_user_prompt(
                        context_package,
                        reasoning_res,
                        critic_res,
                    )
                else:
                    final_status = "MAX_ITERATIONS"
                    termination_reason = "MAX_ITERATIONS_REACHED"
            else:
                # Fallback for unexpected status
                if iteration == self.max_iterations:
                    final_status = "MAX_ITERATIONS"
                    termination_reason = "MAX_ITERATIONS_REACHED"

        return RevisionResult(
            requirement_id=req.requirement_id,
            global_number=req.global_number,
            srs_id=req.srs_id,
            status=final_status,
            final_reasoning_result=final_reasoning_result,
            final_critic_result=final_critic_result,
            iterations_conducted=len(history),
            max_iterations=self.max_iterations,
            history=history,
            termination_reason=termination_reason,
            provenance=context_package.provenance or {},
        )
