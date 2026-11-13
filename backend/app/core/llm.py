"""LLM access layer.

v0.1 note: the two analysts are deterministic on purpose — their scoring rules
are auditable and cheap. LLMs are used where judgement (not arithmetic) is
needed, e.g. turning a snapshot into a readable rationale. The interface below
is what the analysts call once LLM-backed reasoning is enabled (v0.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class LLMResult:
    text: str
    tokens: int = 0


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, user: str) -> LLMResult: ...


class MockLLM:
    """Deterministic stub so the pipeline runs with zero API keys."""

    def __init__(self, model: str = "mock") -> None:
        self.model = model

    def complete(self, system: str, user: str) -> LLMResult:
        return LLMResult(text=f"[mock:{self.model}] {user[:120]}", tokens=0)


class OpenAICompatLLM:
    """Any OpenAI-compatible chat endpoint (DeepSeek, Ark, vLLM, OpenRouter…)."""

    def __init__(self, model: str, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, system: str, user: str) -> LLMResult:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        tokens = int((data.get("usage") or {}).get("total_tokens", 0))
        return LLMResult(text=text, tokens=tokens)


def get_llm(tier: str = "cheap") -> LLMClient:
    """Return an LLM client for the given tier ("cheap" | "strong")."""
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        return MockLLM(model="mock")
    model = settings.llm_model_strong if tier == "strong" else settings.llm_model_cheap
    base_url = settings.llm_base_url if hasattr(settings, "llm_base_url") else ""
    if not base_url:
        log.warning("LLM_BASE_URL not configured; falling back to mock LLM")
        return MockLLM(model="mock")
    return OpenAICompatLLM(model=model, base_url=base_url, api_key=settings.llm_api_key)


def estimate_tokens(text: str) -> int:
    """Rough token estimate for guard rails (4 chars ≈ 1 token for zh+en mix)."""
    return max(1, len(text) // 4)


def dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
