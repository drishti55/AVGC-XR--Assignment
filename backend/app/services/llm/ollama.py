"""Fallback provider: a local open-source model served by Ollama (no internet, no key)."""
import json

import httpx

from app.services.llm.base import ANSWER_SCHEMA, LLMError, LLMResult, parse_result


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds

    def generate(self, system: str, user: str) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "keep_alive": "30m",                # keep the model in memory: avoids slow cold starts
            "format": ANSWER_SCHEMA,            # Ollama constrains the output to this JSON schema
            "options": {
                "temperature": 0.2,
                "num_ctx": 8192,                # default context is too small for 4 passages in 2 languages
            },
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except httpx.TimeoutException as e:
            raise LLMError(self.name, "timeout") from e
        except httpx.HTTPError as e:
            raise LLMError(self.name, "unavailable", "is `ollama serve` running?") from e
        if r.status_code != 200:
            raise LLMError(self.name, "unavailable" if r.status_code >= 500 else "error", f"HTTP {r.status_code}")
        try:
            raw = json.loads(r.json()["message"]["content"])
        except (KeyError, ValueError) as e:
            raise LLMError(self.name, "bad_output", "response was not JSON") from e
        return parse_result(raw, f"ollama/{self.model}", self.name)
