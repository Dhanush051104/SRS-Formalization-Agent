import unittest

from app.clarification.clarification_manager import ClarificationManager
from app.clarification.schemas import (
    ClarificationQuestion,
    ClarificationResult,
)
from app.critic.schemas import CriticFinding, CriticResult
from app.reasoning.schemas import ReasoningResult
from app.retrieval.sqlite_retriever import RequirementContext
from app.revision.schemas import RevisionHistoryEntry, RevisionResult


class TestClarificationManager(unittest.TestCase):
    """
    Deterministic offline tests for ClarificationManager and ClarificationQuestion schemas.
    """

    def setUp(self):
        self.manager = ClarificationManager()
        self.req_context = RequirementContext(
            requirement_id=8,
            global_number=8,
            source_number=8,
            srs_id="[SRS178]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            normalized_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            page_number=12,
            element_index=1,
            document_id=1,
        )

    def test_unresolved_items_question_generation(self):
        reasoning = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            formalization="G(comm_lost -> F safe_state)",
            unresolved_items=["Maximum allowable jitter tolerance", "Actuator hold duration"],
        )
        critic = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
        )

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            reasoning_result=reasoning,
            critic_result=critic,
        )

        self.assertIsInstance(res, ClarificationResult)
        self.assertEqual(res.total_questions, 2)
        self.assertEqual(res.open_questions, 2)
        categories = [q.category for q in res.questions]
        self.assertEqual(categories, ["UNRESOLVED_ITEM", "UNRESOLVED_ITEM"])
        self.assertTrue(res.questions[0].question_id.startswith("CLARIFY-SRS178-"))
        self.assertIn("Maximum allowable jitter tolerance", res.questions[0].question_text)
        self.assertGreater(len(res.questions[0].suggested_options), 0)

    def test_unsupported_assumptions_question_generation(self):
        reasoning = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            formalization="G(comm_lost -> safe)",
            assumptions=["Hardware sensors trigger within 1ms"],
        )
        critic = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            unsupported_assumptions=["Hardware sensors trigger within 1ms"],
        )

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            reasoning_result=reasoning,
            critic_result=critic,
        )

        categories = [q.category for q in res.questions]
        self.assertIn("UNSUPPORTED_ASSUMPTION", categories)
        question = next(q for q in res.questions if q.category == "UNSUPPORTED_ASSUMPTION")
        self.assertIn("Hardware sensors trigger within 1ms", question.question_text)
        self.assertEqual(question.status, "OPEN")

    def test_missing_constraints_question_generation(self):
        critic = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            missing_constraints=["Upper bound deadline of 10ms"],
        )

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            critic_result=critic,
        )

        self.assertEqual(res.total_questions, 1)
        q = res.questions[0]
        self.assertEqual(q.category, "CRITIC_FINDING")
        self.assertIn("Upper bound deadline of 10ms", q.question_text)

    def test_blocked_status_question_generation(self):
        critic = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="BLOCKED",
            summary="Contradictory timing bounds specified in requirements 3.2.1 and 3.2.2.",
        )

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            critic_result=critic,
        )

        categories = [q.category for q in res.questions]
        self.assertIn("BLOCKED_FORMALIZATION", categories)
        q = next(q for q in res.questions if q.category == "BLOCKED_FORMALIZATION")
        self.assertIn("BLOCKED", q.question_text)
        self.assertIn("Contradictory timing bounds", q.reason)

    def test_clarification_serialization(self):
        q = ClarificationQuestion(
            question_id="CLARIFY-SRS178-01",
            requirement_srs_id="[SRS178]",
            category="UNRESOLVED_ITEM",
            question_text="How to handle timing?",
            reason="Ambiguous timing",
            related_constraint="timing",
            suggested_options=["Bound 10ms", "Bound 20ms"],
            status="OPEN",
        )
        d = q.to_dict()
        q_roundtrip = ClarificationQuestion.from_dict(d)
        self.assertEqual(q.question_id, q_roundtrip.question_id)
        self.assertEqual(q.suggested_options, q_roundtrip.suggested_options)

    def test_preserve_answered_clarifications(self):
        reasoning = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            formalization="G(comm_lost -> F safe_state)",
            unresolved_items=["Maximum allowable jitter tolerance"],
        )
        existing = [
            {
                "question_id": "CLARIFY-SRS178-01",
                "requirement_srs_id": "[SRS178]",
                "category": "UNRESOLVED_ITEM",
                "question_text": "How should unresolved item 'Maximum allowable jitter tolerance' be formally specified for [SRS178]?",
                "reason": "Test reason",
                "related_constraint": "Maximum allowable jitter tolerance",
                "suggested_options": ["Option A", "Option B"],
                "status": "ANSWERED",
                "answer": "Option A: 2ms maximum jitter bound",
                "answered_at": "2026-10-13T10:00:00Z",
            }
        ]

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            reasoning_result=reasoning,
            existing_clarifications=existing,
        )

        self.assertEqual(res.total_questions, 1)
        self.assertEqual(res.open_questions, 0)
        q = res.questions[0]
        self.assertEqual(q.status, "ANSWERED")
        self.assertEqual(q.answer, "Option A: 2ms maximum jitter bound")
        self.assertEqual(q.answered_at, "2026-10-13T10:00:00Z")

    def test_append_previously_answered_not_reflagged(self):
        reasoning = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            formalization="G(comm_lost -> F safe_state)",
            unresolved_items=["New parameter X"],
        )
        existing = [
            {
                "question_id": "CLARIFY-SRS178-01",
                "requirement_srs_id": "[SRS178]",
                "category": "UNRESOLVED_ITEM",
                "question_text": "Previous question",
                "reason": "Previous reason",
                "related_constraint": "Old constraint Y",
                "suggested_options": ["Old Option 1"],
                "status": "ANSWERED",
                "answer": "Approved old answer",
                "answered_at": "2026-10-13T09:00:00Z",
            }
        ]

        res = self.manager.generate_clarifications(
            requirement_context=self.req_context,
            reasoning_result=reasoning,
            existing_clarifications=existing,
        )

        self.assertEqual(res.total_questions, 2)
        self.assertEqual(res.open_questions, 1)
        new_q = next(q for q in res.questions if q.related_constraint == "New parameter X")
        old_q = next(q for q in res.questions if q.related_constraint == "Old constraint Y")
        self.assertEqual(new_q.status, "OPEN")
        self.assertEqual(new_q.question_id, "CLARIFY-SRS178-02")
        self.assertEqual(old_q.status, "ANSWERED")
        self.assertEqual(old_q.question_id, "CLARIFY-SRS178-01")
        self.assertEqual(old_q.answer, "Approved old answer")

    def test_state_transition_from_needs_clarification_to_pass(self):
        from app.pipeline import PipelineResult
        from app.ui.app import classify_result

        open_res = PipelineResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            status="PASS",
            validation_valid=True,
            clarifications=[
                {"question_id": "CLARIFY-1", "status": "OPEN", "answer": None}
            ],
        )
        self.assertEqual(classify_result(open_res)["label"], "PASS (NEEDS CLARIFICATION)")

        answered_res = PipelineResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            status="PASS",
            validation_valid=True,
            clarifications=[
                {"question_id": "CLARIFY-1", "status": "ANSWERED", "answer": "Approved Bound"}
            ],
        )
        self.assertEqual(classify_result(answered_res)["label"], "PASS")


if __name__ == "__main__":
    unittest.main()

