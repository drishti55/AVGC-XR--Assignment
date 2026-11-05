"""Try providers in order (Gemini first, then local Ollama) until one succeeds."""
import logging
from dataclasses import dataclass

from app.services.llm.base import LLMError, LLMProvider, LLMResult

logger = logging.getLogger("garuda.llm")


class AllProvidersFailed(Exception):
    def __init__(self, errors: list[LLMError]):
        self.errors = errors
        super().__init__("; ".join(str(e) for e in errors))


@dataclass
class LLMRouter:
    providers: list[LLMProvider]

    def generate(self, system: str, user: str) -> tuple[LLMResult, list[LLMError]]:
        """Return the first successful result plus the errors of providers that failed before it."""
        errors: list[LLMError] = []
        for provider in self.providers:
            try:
                return provider.generate(system, user), errors
            except LLMError as e:
                logger.warning("LLM provider failed, trying next: %s", e)
                errors.append(e)
        raise AllProvidersFailed(errors)
