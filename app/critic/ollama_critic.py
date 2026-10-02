import json
from typing import Any, Optional

import ollama

from app.critic.critic_model import CriticModel
from app.critic.critic_prompt import CRITIC_SYSTEM_PROMPT, build_critic_user_prompt
from app.critic.schemas import (
    CriticError,
    CriticResult,
    CriticValidationError,
)
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage

DEFAULT_OLLAMA_MODEL = "llama3:latest"


class OllamaCritic(CriticModel):
    """
    Concrete CriticModel implementation using Ollama and Llama 3.
    """

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        """
        Initialize the OllamaCritic model adapter.

        Args:
            model: Ollama model tag to use (defaults to 'llama3:latest').
            host: Optional Ollama host URL (e.g. 'http://localhost:11434').
            client: Optional pre-configured Ollama client object (useful for testing/injection).
        """
        self.model = model
        self.host = host

        if client is not None:
            self.client = client
        elif host is not None:
            self.client = ollama.Client(host=host)
        else:
            self.client = ollama

    def critique(
        self,
        context_package: ContextPackage,
        reasoning_result: ReasoningResult,
    ) -> CriticResult:
        """
        Critiques a candidate ReasoningResult against the original ContextPackage using Llama 3 via Ollama,
        parses the JSON response, validates metadata identity matching and schema structure, and returns CriticResult.

        Args:
            context_package: ContextPackage instance containing SRS requirement data & Obsidian knowledge.
            reasoning_result: Candidate ReasoningResult to critique.

        Returns:
            Validated CriticResult instance.

        Raises:
            CriticValidationError: If Ollama response is invalid JSON or metadata fails validation.
            CriticError: If Ollama execution fails or daemon is unreachable.
        """
        if not context_package.requirements:
            raise CriticValidationError("ContextPackage must contain at least one RequirementContext.")

        # 1. Build system and user prompts
        system_prompt = CRITIC_SYSTEM_PROMPT
        user_prompt = build_critic_user_prompt(context_package, reasoning_result)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 2. Communicate with Ollama using JSON format mode
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                format="json",
            )
        except Exception as e:
            raise CriticError(f"Ollama chat execution failed for critic model '{self.model}': {e}")

        # 3. Extract raw response text
        raw_content: Optional[str] = None
        if hasattr(response, "message") and hasattr(response.message, "content"):
            raw_content = response.message.content
        elif isinstance(response, dict) and "message" in response and "content" in response["message"]:
            raw_content = response["message"]["content"]
        else:
            raw_content = str(response)

        if not raw_content or not raw_content.strip():
            raise CriticValidationError("Ollama returned empty response content for critic request.")

        # 4. Parse JSON
        try:
            parsed_data = json.loads(raw_content)
        except Exception as e:
            raise CriticValidationError(
                f"Failed to parse model output as JSON: {e}\nRaw Content:\n{raw_content}"
            )

        if not isinstance(parsed_data, dict):
            raise CriticValidationError(
                f"Parsed JSON must be a JSON object, got {type(parsed_data).__name__}."
            )

        # 5. Construct CriticResult
        try:
            result = CriticResult.from_dict(parsed_data, raw_response=raw_content)
        except Exception as e:
            raise CriticValidationError(f"Failed to map JSON data into CriticResult: {e}")

        # 6. Validate identity match and structure
        self.validate_result(context_package, reasoning_result, result)

        return result
