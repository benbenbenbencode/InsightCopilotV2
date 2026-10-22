"""Minimal client for any OpenAI-compatible /chat/completions endpoint
(Ollama, Groq, OpenAI, vLLM...). No tool-calling API needed, so it also works
with models that don't support it."""
from __future__ import annotations

import time

import requests

from .config import Settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, s: Settings):
        self.url = f"{s.llm_base_url}/chat/completions"
        self.headers = {"Authorization": f"Bearer {s.llm_api_key}"}
        self.model = s.llm_model

    def chat(self, messages: list[dict], retries: int = 2) -> str:
        last = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(
                    self.url,
                    headers=self.headers,
                    json={"model": self.model, "messages": messages, "temperature": 0},
                    timeout=120,
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    last = f"HTTP {r.status_code}"
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"] or ""
            except (requests.RequestException, KeyError, ValueError) as e:
                last = str(e)
                time.sleep(2 ** attempt)
        raise LLMError(f"LLM call failed: {last}")
