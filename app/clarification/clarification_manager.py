from typing import Any, Dict, List, Optional, Set

from app.clarification.schemas import (
    ClarificationQuestion,
    ClarificationResult,
)
from app.critic.schemas import CriticResult
from app.reasoning.schemas import ReasoningResult
from app.retrieval.sqlite_retriever import RequirementContext
from app.revision.schemas import RevisionResult


class ClarificationManager:
    """
    Deterministic clarification manager that inspects candidate formalizations,
    Critic findings, and revision results to synthesize structured clarification
    questions for human review without requiring expensive additional LLM calls.
    """

    def generate_clarifications(
        self,
        requirement_context: RequirementContext,
        reasoning_result: Optional[ReasoningResult] = None,
        critic_result: Optional[CriticResult] = None,
        revision_result: Optional[RevisionResult] = None,
    ) -> ClarificationResult:
        """
        Analyzes requirement analysis outputs and generates structured clarification questions.

        Args:
            requirement_context: Canonical RequirementContext from SQLite.
            reasoning_result: Latest candidate ReasoningResult (optional if revision_result provided).
            critic_result: Latest CriticResult (optional if revision_result provided).
            revision_result: Final RevisionResult from RevisionManager (if available).

        Returns:
            ClarificationResult containing deterministically generated questions.
        """
        # Resolve latest reasoning and critic outputs
        final_reasoning = reasoning_result
        final_critic = critic_result
        status = "NEEDS_REVISION"

        if revision_result is not None:
            final_reasoning = revision_result.final_reasoning_result
            final_critic = revision_result.final_critic_result
            status = revision_result.status
        elif critic_result is not None:
            status = critic_result.status

        srs_id = requirement_context.srs_id
        clean_srs = srs_id.strip("[]").replace(" ", "_")
        questions: List[ClarificationQuestion] = []
        seen_constraints: Set[str] = set()
        q_counter = 1

        # 1. Unresolved items from reasoning output
        if final_reasoning and final_reasoning.unresolved_items:
            for item in final_reasoning.unresolved_items:
                item_clean = item.strip()
                if item_clean and item_clean.lower() not in seen_constraints:
                    seen_constraints.add(item_clean.lower())
                    q_id = f"CLARIFY-{clean_srs}-{q_counter:02d}"
                    q_counter += 1
                    questions.append(
                        ClarificationQuestion(
                            question_id=q_id,
                            requirement_srs_id=srs_id,
                            category="UNRESOLVED_ITEM",
                            question_text=f"How should unresolved item '{item_clean}' be formally specified for {srs_id}?",
                            reason="The reasoning model identified unstated engineering parameters or missing operational constraints in the requirement.",
                            related_constraint=item_clean,
                            suggested_options=[
                                f"Specify explicit numerical value or bound for '{item_clean}'",
                                "Confirm as an invariant external system assumption",
                                "Defer parameter binding to subsystem architectural design",
                            ],
                            status="OPEN",
                        )
                    )

        # 2. Unsupported assumptions flagged by Critic
        if final_critic and final_critic.unsupported_assumptions:
            for assumption in final_critic.unsupported_assumptions:
                assump_clean = assumption.strip()
                if assump_clean and assump_clean.lower() not in seen_constraints:
                    seen_constraints.add(assump_clean.lower())
                    q_id = f"CLARIFY-{clean_srs}-{q_counter:02d}"
                    q_counter += 1
                    questions.append(
                        ClarificationQuestion(
                            question_id=q_id,
                            requirement_srs_id=srs_id,
                            category="UNSUPPORTED_ASSUMPTION",
                            question_text=f"Is the assumption '{assump_clean}' approved as valid for {srs_id}?",
                            reason="The Critic flagged this assumption as lacking explicit textual support in the source SRS requirement.",
                            related_constraint=assump_clean,
                            suggested_options=[
                                "Approve assumption as a documented engineering domain invariant",
                                "Reject assumption and require explicit SRS text amendment",
                                "Replace assumption with alternative verified constraint",
                            ],
                            status="OPEN",
                        )
                    )

        # 3. Missing constraints flagged by Critic
        if final_critic and final_critic.missing_constraints:
            for mc in final_critic.missing_constraints:
                mc_clean = mc.strip()
                if mc_clean and mc_clean.lower() not in seen_constraints:
                    seen_constraints.add(mc_clean.lower())
                    q_id = f"CLARIFY-{clean_srs}-{q_counter:02d}"
                    q_counter += 1
                    questions.append(
                        ClarificationQuestion(
                            question_id=q_id,
                            requirement_srs_id=srs_id,
                            category="CRITIC_FINDING",
                            question_text=f"How should the missing constraint '{mc_clean}' be incorporated into {srs_id}?",
                            reason="The verification Critic identified that the candidate formalization omitted a required constraint.",
                            related_constraint=mc_clean,
                            suggested_options=[
                                f"Add explicit temporal or boundary condition for '{mc_clean}'",
                                "Confirm constraint is governed by an external sibling requirement",
                                "Declare constraint optional or out of scope for this requirement",
                            ],
                            status="OPEN",
                        )
                    )

        # 4. Critical Blocked State
        if status.upper() == "BLOCKED":
            q_id = f"CLARIFY-{clean_srs}-{q_counter:02d}"
            q_counter += 1
            summary_msg = final_critic.summary if final_critic else "Fundamental specification conflict."
            questions.append(
                ClarificationQuestion(
                    question_id=q_id,
                    requirement_srs_id=srs_id,
                    category="BLOCKED_FORMALIZATION",
                    question_text=f"Requirement {srs_id} is marked BLOCKED for automated formalization. What stakeholder resolution is required?",
                    reason=f"The Critic or Revision Manager determined formalization cannot proceed: {summary_msg}",
                    related_constraint="Formalization Feasibility",
                    suggested_options=[
                        "Initiate stakeholder review to resolve contradictory requirement statements",
                        "Decompose into multiple atomic, non-conflicting requirements",
                        "Reclassify requirement as informational / non-functional",
                    ],
                    status="OPEN",
                )
            )

        return ClarificationResult(
            requirement_id=requirement_context.requirement_id,
            srs_id=srs_id,
            questions=questions,
            total_questions=len(questions),
            open_questions=sum(1 for q in questions if q.status == "OPEN"),
        )
