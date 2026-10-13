"""Small persistent model-selection store; it contains only Ollama model tags."""

import json
import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Fallbacks used only until the user saves a selection on /settings/models.
# They are validated against the installed models before any real run, never silently substituted.
DEFAULT_MODELS = {"analyst": "llama3:latest", "reasoning": "llama3:latest", "critic": "llama3:latest"}
CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "model_config.json"


def load_model_config() -> Dict[str, str]:
    """Return the three role selections; missing, partial or invalid files fall back to defaults."""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(DEFAULT_MODELS)
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable model config %s: %s", CONFIG_PATH, exc)
        return dict(DEFAULT_MODELS)
    if not isinstance(data, dict):
        logger.warning("Ignoring model config %s: top-level value is not an object.", CONFIG_PATH)
        return dict(DEFAULT_MODELS)
    config = {}
    for role, default in DEFAULT_MODELS.items():
        value = data.get(role)
        config[role] = value.strip() if isinstance(value, str) and value.strip() else default
    return config


def save_model_config(models: Dict[str, str]) -> None:
    """Persist the three role selections atomically, creating data/ if needed."""
    clean = {role: str(models[role]).strip() for role in DEFAULT_MODELS}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    os.replace(tmp_path, CONFIG_PATH)
