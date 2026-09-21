import json
from pathlib import Path
from typing import Any, List, Optional, Union

import ollama

from app.analyst.analyst_model import AnalystModel
from app.analyst.analyst_prompt import ANALYST_SYSTEM_PROMPT, build_analyst_user_prompt
from app.analyst.schemas import (
    AnalystError,
    AnalystResult,
    AnalystValidationError,
    NonCanonicalPatternError,
)
from app.retrieval.sqlite_retriever import RequirementContext

DEFAULT_OLLAMA_MODEL = "llama3:latest"


class OllamaAnalyst(AnalystModel):
    """
    Concrete AnalystModel implementation using Ollama and Llama 3.
    """

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: Optional[str] = None,
        registry_path: Optional[Union[Path, str]] = None,
        client: Optional[Any] = None,
    ) -> None:
        """
        Initialize the OllamaAnalyst model adapter.

        Args:
            model: Ollama model tag to use (defaults to 'llama3:latest').
            host: Optional Ollama host URL (e.g. 'http://localhost:11434').
            registry_path: Path to Pattern-Registry.json. If None, resolved automatically.
            client: Optional pre-configured Ollama client object (useful for testing/injection).
        """
        super().__init__(registry_path=registry_path)
        self.model = model
        self.host = host

        if client is not None:
            self.client = client
        elif host is not None:
            self.client = ollama.Client(host=host)
        else:
            self.client = ollama

    def analyze(self, requirement_context: RequirementContext) -> AnalystResult:
        """
        Analyzes a single RequirementContext using Llama 3 via Ollama, parses the JSON response,
        validates metadata matching and pattern canonicality, and returns AnalystResult.

        Args:
            requirement_context: RequirementContext instance from SQLite.

        Returns:
            Validated AnalystResult instance.

        Raises:
            AnalystValidationError: If Ollama response is invalid JSON or metadata fails validation.
            NonCanonicalPatternError: If an identified pattern name is not in Pattern-Registry.json.
            AnalystError: If Ollama execution fails or daemon is unreachable.
        """
        # 1. Load canonical pattern catalog dynamically from Pattern-Registry.json
        pattern_catalog = self.load_pattern_catalog()

        # 2. Build system and user prompts
        system_prompt = ANALYST_SYSTEM_PROMPT
        user_prompt = build_analyst_user_prompt(requirement_context, pattern_catalog)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 3. Communicate with Ollama using JSON format mode
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                format="json",
            )
        except Exception as e:
            raise AnalystError(f"Ollama chat execution failed for model '{self.model}': {e}")

        # 4. Extract raw response text
        raw_content: Optional[str] = None
        if hasattr(response, "message") and hasattr(response.message, "content"):
            raw_content = response.message.content
        elif isinstance(response, dict) and "message" in response and "content" in response["message"]:
            raw_content = response["message"]["content"]
        else:
            raw_content = str(response)

        if not raw_content or not raw_content.strip():
            raise AnalystValidationError("Ollama returned empty response content.")

        # 5. Parse JSON
        try:
            parsed_data = json.loads(raw_content)
        except Exception as e:
            raise AnalystValidationError(
                f"Failed to parse model output as JSON: {e}\nRaw Content:\n{raw_content}"
            )

        if not isinstance(parsed_data, dict):
            raise AnalystValidationError(
                f"Parsed JSON must be a JSON object, got {type(parsed_data).__name__}."
            )

        # 6. Construct AnalystResult
        try:
            result = AnalystResult.from_dict(parsed_data, raw_response=raw_content)
        except Exception as e:
            raise AnalystValidationError(f"Failed to map JSON data into AnalystResult: {e}")

        # 7. Perform rigorous validation (identity match, pattern uniqueness, canonicality)
        self.validate_result(requirement_context, result, pattern_catalog)

        return result
