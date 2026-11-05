"""Common interface for LLM providers.

Every provider takes the same (system prompt, user prompt) and must return JSON matching
ANSWER_SCHEMA. Forcing structured output means the citations come back as a list we can
check in code, instead of being parsed out of free text.
"""
from dataclasses import dataclass
from typing import Protocol

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "is_answerable": {
            "type": "boolean",
            "description": "true only if the passages contain information that answers the question",
        },
        "answer": {
            "type": "string",
            "description": "The interpretation, citing passage IDs in square brackets",
        },
        "cited_passage_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "IDs of the passages the answer relies on",
        },
    },
    "required": ["is_answerable", "answer", "cited_passage_ids"],
}


class LLMError(Exception):
    """A provider failed in a way the router should handle by trying the next provider."""

    def __init__(self, provider: str, kind: str, detail: str = ""):
        # kind: not_configured | rate_limited | unavailable | timeout | bad_output | error
        self.provider, self.kind, self.detail = provider, kind, detail
        super().__init__(f"{provider}: {kind} {detail}".strip())


@dataclass
class LLMResult:
    is_answerable: bool
    answer: str
    cited_passage_ids: list[str]
    model: str                      # e.g. "gemini/gemini-3.5-flash" or "ollama/qwen2.5:7b"


class LLMProvider(Protocol):
    name: str

    def generate(self, system: str, user: str) -> LLMResult: ...


def parse_result(raw: dict, model: str, provider: str) -> LLMResult:
    """Validate the provider's JSON; anything malformed counts as bad_output (-> fallback)."""
    try:
        ok = bool(raw["is_answerable"])
        answer = str(raw["answer"]).strip()
        ids = raw["cited_passage_ids"]
        if not isinstance(ids, list):
            raise TypeError("cited_passage_ids is not a list")
        return LLMResult(ok, answer, [str(i).strip() for i in ids], model)
    except (KeyError, TypeError, ValueError) as e:
        raise LLMError(provider, "bad_output", f"unexpected JSON: {e}") from e
