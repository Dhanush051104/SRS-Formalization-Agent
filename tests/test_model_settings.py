"""Offline tests for Ollama model discovery, the /settings/models page and the real-pipeline
construction guard. No Ollama or network is contacted: discovery is patched at the HTTP boundary."""

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from app.pipeline import FormalizationPipeline
from app.ui import app as ui_app
from app.ui import model_config
from tests.ui_test_support import IsolatedAppTestCase


class FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestOllamaDiscovery(unittest.TestCase):
    def discover(self, **patch_kwargs):
        with patch("app.ui.app._open_local", **patch_kwargs) as opener:
            return ui_app.get_installed_ollama_models(), opener

    def test_installed_models_are_sorted_and_deduplicated(self):
        body = {"models": [{"name": "b:1"}, {"name": "a:1"}, {"name": "a:1"}, {"name": ""}, {}]}
        (names, error), opener = self.discover(return_value=FakeResponse(body))
        self.assertEqual(names, ["a:1", "b:1"])
        self.assertIsNone(error)
        self.assertEqual(opener.call_args.args[0], "http://localhost:11434/api/tags")

    def test_service_unavailable_is_reported_not_raised(self):
        (names, error), _ = self.discover(side_effect=URLError("connection refused"))
        self.assertEqual(names, [])
        self.assertIn("Ollama is unavailable", error)

    def test_timeout_is_reported_not_raised(self):
        (names, error), _ = self.discover(side_effect=TimeoutError("timed out"))
        self.assertEqual(names, [])
        self.assertIn("Ollama is unavailable", error)

    def test_invalid_json_is_reported(self):
        (names, error), _ = self.discover(return_value=FakeResponse(b"<html>not json</html>"))
        self.assertEqual(names, [])
        self.assertIsNotNone(error)

    def test_unexpected_payload_shapes_are_reported(self):
        for body in ([], {"models": None}, {"models": "x"}):
            (names, error), _ = self.discover(return_value=FakeResponse(body))
            self.assertEqual(names, [], body)
            self.assertIsNotNone(error, body)

    def test_no_installed_models_is_not_an_error(self):
        (names, error), _ = self.discover(return_value=FakeResponse({"models": []}))
        self.assertEqual(names, [])
        self.assertIsNone(error)


class TestBuildConfiguredPipeline(unittest.TestCase):
    CONFIG = {"analyst": "a:1", "reasoning": "r:1", "critic": "c:1"}

    def build(self, installed, error=None):
        with patch("app.ui.app.load_model_config", return_value=dict(self.CONFIG)), \
                patch("app.ui.app.get_installed_ollama_models", return_value=(installed, error)):
            return ui_app.build_configured_pipeline()

    def test_ollama_unavailable_fails_clearly(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.build([], "Ollama is unavailable or returned invalid installed-model data: refused")
        self.assertIn("Ollama is unavailable", str(ctx.exception))

    def test_missing_model_fails_naming_it_and_never_substitutes(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.build(["a:1", "r:1", "other:9"])  # critic model c:1 missing; an unrelated model exists
        message = str(ctx.exception)
        self.assertIn("c:1", message)
        self.assertNotIn("a:1,", message)

    def test_no_installed_models_fails(self):
        with self.assertRaises(RuntimeError):
            self.build([])

    def test_all_installed_builds_real_pipeline_with_independent_models(self):
        pipeline = self.build(["a:1", "r:1", "c:1"])
        self.assertIsInstance(pipeline, FormalizationPipeline)
        self.assertEqual(pipeline.analyst_model.model, "a:1")
        self.assertEqual(pipeline.reasoning_model.model, "r:1")
        self.assertEqual(pipeline.critic_model.model, "c:1")


class TestModelSettingsPage(IsolatedAppTestCase):
    def installed(self, models, error=None):
        return patch("app.ui.app.get_installed_ollama_models", return_value=(models, error))

    def test_page_lists_installed_models(self):
        with self.installed(["a:1", "b:1"]):
            response = self.client.get("/settings/models")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"a:1", response.data)
        self.assertIn(b"b:1", response.data)

    def test_ollama_unavailable_message_and_disabled_controls(self):
        response = self.client.get("/settings/models")  # default test patch: Ollama unavailable
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ollama disabled in tests", response.data)
        self.assertIn(b"disabled", response.data)

    def test_no_models_installed_shows_useful_message(self):
        with self.installed([]):
            response = self.client.get("/settings/models")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"no installed models", response.data)

    def test_configured_but_missing_model_is_flagged_not_silently_replaced(self):
        model_config.save_model_config({"analyst": "gone:1", "reasoning": "b:1", "critic": "b:1"})
        with self.installed(["a:1", "b:1"]):
            response = self.client.get("/settings/models")
        self.assertIn(b"Configured but not installed", response.data)
        self.assertIn(b"gone:1", response.data)
        self.assertIn(b"choose an installed model", response.data)

    def test_save_persists_independent_roles_and_survives_reload(self):
        form = {"analyst": "a:1", "reasoning": "b:1", "critic": "c:1"}
        with self.installed(["a:1", "b:1", "c:1"]):
            response = self.client.post("/settings/models", data=form, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Model selections saved.", response.data)
        self.assertTrue(model_config.CONFIG_PATH.exists())
        self.assertEqual(model_config.load_model_config(), form)  # read back from disk, as after a restart

    def test_uninstalled_model_is_rejected_and_nothing_is_saved(self):
        form = {"analyst": "a:1", "reasoning": "ghost:1", "critic": "a:1"}
        with self.installed(["a:1"]):
            response = self.client.post("/settings/models", data=form)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"not currently installed", response.data)
        self.assertFalse(model_config.CONFIG_PATH.exists())

    def test_missing_role_field_is_rejected(self):
        with self.installed(["a:1"]):
            response = self.client.post("/settings/models", data={"analyst": "a:1", "critic": "a:1"})
        self.assertIn(b"not currently installed", response.data)
        self.assertFalse(model_config.CONFIG_PATH.exists())

    def test_save_while_ollama_down_is_rejected(self):
        form = {"analyst": "a:1", "reasoning": "a:1", "critic": "a:1"}
        response = self.client.post("/settings/models", data=form)  # default: Ollama unavailable
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ollama disabled in tests", response.data)
        self.assertFalse(model_config.CONFIG_PATH.exists())


if __name__ == "__main__":
    unittest.main()
