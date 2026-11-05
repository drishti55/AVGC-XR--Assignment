"""Primary provider: Google Gemini (free tier via AI Studio API key)."""
import json

import httpx
from google import genai
from google.genai import errors, types

from app.services.llm.base import ANSWER_SCHEMA, LLMError, LLMResult, parse_result


class GeminiProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float, thinking_level: str = "minimal",
                 name: str = "gemini"):
        self.name = name              # "gemini" or "gemini-lite" — shown in fallback notices
        self.model = model
        self.thinking_level = thinking_level
        self._client = None
        if api_key:
            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=int(timeout_seconds * 1000),               # milliseconds
                    # One attempt only: on failure we fall back to Ollama straight away
                    # instead of the SDK silently retrying for many seconds.
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )

    def generate(self, system: str, user: str) -> LLMResult:
        if self._client is None:
            raise LLMError(self.name, "not_configured", "GEMINI_API_KEY is not set")
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,                       # low: stay close to the passages
                    response_mime_type="application/json",
                    response_json_schema=ANSWER_SCHEMA,
                    # Summarising 4 given passages needs little reasoning; less thinking = faster.
                    thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level),
                ),
            )
        except errors.APIError as e:
            kind = "rate_limited" if e.code == 429 else "unavailable" if (e.code or 0) >= 500 else "error"
            raise LLMError(self.name, kind, f"HTTP {e.code}") from e
        except (httpx.TimeoutException, TimeoutError) as e:
            raise LLMError(self.name, "timeout") from e
        except httpx.HTTPError as e:
            raise LLMError(self.name, "unavailable", type(e).__name__) from e

        try:
            raw = json.loads(response.text or "")
        except json.JSONDecodeError as e:
            raise LLMError(self.name, "bad_output", "response was not JSON") from e
        return parse_result(raw, f"gemini/{self.model}", self.name)
