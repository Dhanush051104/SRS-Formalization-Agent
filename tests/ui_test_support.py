"""Test-only helpers. Mock models live here, never in production code.

make_test_pipeline() wires deterministic mock Analyst/Reasoning/Critic models into a REAL
FormalizationPipeline (real SQLite retrieval, real read-only vault retrieval, real revision loop,
real validator, real clarification manager), so tests exercise production logic without Ollama.

IsolatedAppTestCase isolates the Flask app from the network, the user's real result cache
(data/result_cache.json) and the user's real model selections (data/model_config.json).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.analyst.analyst_model import AnalystModel
from app.analyst.schemas import AnalystResult
from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.pipeline import FormalizationPipeline
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.ui import history_store, model_config, result_store
from app.ui.app import app as flask_app


def default_formula(req):
    # The requirement id is embedded so tests can prove each result belongs to its own requirement.
    if getattr(req, "requirement_id", None) == 8 or getattr(req, "srs_id", "") == "[SRS178]":
        return f"G(trigger_{req.requirement_id} -> F[0, 10ms] response_{req.requirement_id})"
    return f"G(trigger_{req.requirement_id} -> F response_{req.requirement_id})"


def make_test_pipeline(
    formula_for=default_formula,
    critic_status="PASS",
    fail_reasoning_for=(),
    unresolved=(),
):
    """Build a real FormalizationPipeline around mock models (no Ollama, no network)."""

    def analyst_side_effect(req_context, **kwargs):
        return AnalystResult(
            requirement_id=req_context.requirement_id,
            global_number=req_context.global_number,
            srs_id=req_context.srs_id,
            identified_patterns=["Timeout / Deadline", "Failure Handling"],
            evidence={"Timeout / Deadline": "temporal deadline", "Failure Handling": "failure reaction"},
            missing_information=[],
        )

    def reasoning_side_effect(context_pkg, **kwargs):
        req = context_pkg.requirements[0]
        if req.requirement_id in fail_reasoning_for:
            raise RuntimeError(f"model crashed on requirement {req.requirement_id}")
        return ReasoningResult(
            requirement_id=req.requirement_id,
            global_number=req.global_number,
            srs_id=req.srs_id,
            formalization=formula_for(req),
            interpretation=f"Interpretation for requirement {req.requirement_id}.",
            identified_entities=["system", "outputs"],
            predicates=[f"trigger_{req.requirement_id}", f"response_{req.requirement_id}"],
            conditions=["trigger == true"],
            actions=["respond()"],
            temporal_constraints=["within 10ms"],
            mathematical_constraints=["response_time <= 10ms"],
            assumptions=[],
            unresolved_items=list(unresolved),
        )

    def critic_side_effect(context_pkg, reasoning_result, **kwargs):
        return CriticResult(
            requirement_id=reasoning_result.requirement_id,
            global_number=reasoning_result.global_number,
            srs_id=reasoning_result.srs_id,
            status=critic_status,
            summary="Mock critic assessment.",
            findings=[],
            missing_constraints=[],
            unsupported_assumptions=[],
        )

    analyst = MagicMock(spec=AnalystModel)
    analyst.analyze.side_effect = analyst_side_effect
    reasoning = MagicMock(spec=ReasoningModel)
    reasoning.reason.side_effect = reasoning_side_effect
    critic = MagicMock(spec=CriticModel)
    critic.critique.side_effect = critic_side_effect
    return FormalizationPipeline(analyst_model=analyst, reasoning_model=reasoning, critic_model=critic)


def result_segment(html_bytes, requirement_id):
    """Return the HTML of one requirement's accordion item in the batch page."""
    text = html_bytes.decode("utf-8")
    start = text.index(f'id="result-{requirement_id}"')
    following = text.find('id="result-', start + 1)
    return text[start: following if following != -1 else len(text)]


class IsolatedAppTestCase(unittest.TestCase):
    """Flask test client with no network access and temp-dir cache/config storage."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_path = Path(tmp.name)
        for patcher in (
            patch.object(result_store, "STORE_PATH", self.tmp_path / "result_cache.json"),
            patch.object(result_store, "_entries", None),
            patch.object(history_store, "HISTORY_STORE_PATH", self.tmp_path / "history_store.json"),
            patch.object(history_store, "RESULT_CACHE_PATH", self.tmp_path / "result_cache.json"),
            patch.object(history_store, "_history_entries", None),
            patch.object(model_config, "CONFIG_PATH", self.tmp_path / "model_config.json"),
            # Any route that needs Ollama sees it as unavailable unless a test overrides this.
            patch("app.ui.app.get_installed_ollama_models", return_value=([], "Ollama disabled in tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = flask_app.test_client()

    def use_pipeline(self, pipeline):
        """Make the app's pipeline construction boundary return `pipeline`; returns the builder mock."""
        builder = MagicMock(return_value=pipeline)
        patcher = patch("app.ui.app.build_configured_pipeline", builder)
        patcher.start()
        self.addCleanup(patcher.stop)
        return builder
