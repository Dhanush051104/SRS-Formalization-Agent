from dataclasses import replace
from typing import Any, List, Optional

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
from app.formalization_validator import validate_formalization
from app.critic.schemas import CriticFinding


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
        symbol_validator: Optional[Any] = None,
    ) -> None:
        """
        Initialize the RevisionManager.

        Args:
            reasoning_model: Instantiated ReasoningModel adapter.
            critic_model: Instantiated CriticModel adapter.
            max_iterations: Maximum allowed revision iterations (must be >= 1).
            symbol_validator: Optional SymbolValidator instance for canonical symbol checks.

        Raises:
            RevisionValidationError: If max_iterations < 1.
        """
        if max_iterations < 1:
            raise RevisionValidationError(f"max_iterations must be at least 1, got {max_iterations}.")

        self.reasoning_model = reasoning_model
        self.critic_model = critic_model
        self.max_iterations = max_iterations
        self.symbol_validator = symbol_validator

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
            structural_report = validate_formalization(reasoning_res.formalization)
            validation_findings: List[CriticFinding] = []
            if not structural_report.is_valid:
                validation_findings.extend([
                    CriticFinding(
                        category=item["category"], severity=item["severity"],
                        description=item["description"], recommendation=item["recommendation"],
                    ) for item in structural_report.findings
                ])

            # Deterministic symbol validation
            symbol_report = None
            if self.symbol_validator is not None:
                scope = (
                    context_package.requirements[0].srs_id
                    if context_package.requirements
                    else None
                )
                symbol_report = self.symbol_validator.validate_candidate(
                    formalization=reasoning_res.formalization,
                    predicates=reasoning_res.predicates,
                    entities=reasoning_res.identified_entities,
                    current_scope=scope,
                    intermediate_representation=reasoning_res.intermediate_representation,
                )
                if not symbol_report.is_valid:
                    for v in symbol_report.violations:
                        if v.severity == "ERROR":
                            validation_findings.append(CriticFinding(
                                category="SYMBOL_VALIDATION",
                                severity="ERROR",
                                description=v.description,
                                recommendation=f"Ensure symbol '{v.symbol_spelling}' complies with canonical registry definitions and permitted scope.",
                            ))

            if validation_findings:
                # Deterministic validation failures can never be overridden by critic PASS.
                # A critic BLOCKED is kept as BLOCKED. The critic's own result object is copied, not mutated.
                fail_msgs = []
                if not structural_report.is_valid:
                    fail_msgs.append("Deterministic structural validation failed; the formula must be revised.")
                if symbol_report is not None and not symbol_report.is_valid:
                    fail_msgs.append("Deterministic symbol validation failed; the formula must be revised.")
                critic_res = replace(
                    critic_res,
                    findings=list(critic_res.findings) + validation_findings,
                    status="BLOCKED" if critic_res.status.upper() == "BLOCKED" else "NEEDS_REVISION",
                    revision_required=True,
                    summary=(critic_res.summary + " " if critic_res.summary else "") +
                    " ".join(fail_msgs),
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
