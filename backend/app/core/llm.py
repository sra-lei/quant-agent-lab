"""LLM access layer.

v0.1 note: the two analysts are deterministic on purpose — their scoring rules
are auditable and cheap. LLMs are used where judgement (not arithmetic) is
needed, e.g. turning a snapshot into a readable rationale. The interface below
is what the analysts call once LLM-backed reasoning is enabled (v0.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class ToolCall:
    """模型请求执行的一次工具调用。"""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResult:
    text: str
    tokens: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    model: str

    def complete(
        self,
        system: str,
        user: str,
        tools: list[dict] | None = None,
    ) -> LLMResult: ...


def _sample_args(schema: dict) -> dict:
    """按参数 schema 造一组最小合法参数（仅 mock 用）。"""
    props = (schema or {}).get("properties") or {}
    required = (schema or {}).get("required") or list(props.keys())
    out: dict = {}
    for key in required:
        spec = props.get(key) or {}
        kind = spec.get("type")
        if kind == "string":
            enum = spec.get("enum")
            out[key] = enum[0] if enum else spec.get("default", "600519")
        elif kind == "integer":
            out[key] = int(spec.get("default", 20))
        elif kind == "number":
            out[key] = float(spec.get("default", 15.0))
        elif kind == "boolean":
            out[key] = True
        else:
            out[key] = None
    return out


class MockLLM:
    """Deterministic stub so the pipeline runs with zero API keys.

    有工具可用时，第一轮返回一次工具调用（先跑通"执行"这条路），
    收到工具结果后再给出最终文本。
    """

    def __init__(self, model: str = "mock") -> None:
        self.model = model

    def complete(
        self,
        system: str,
        user: str,
        tools: list[dict] | None = None,
    ) -> LLMResult:
        if tools and "## 工具执行结果" not in user:
            fn = tools[0]["function"]
            return LLMResult(
                text="",
                tokens=0,
                tool_calls=[
                    ToolCall(
                        id="mock-call-1",
                        name=fn["name"],
                        arguments=_sample_args(fn.get("parameters") or {}),
                    )
                ],
            )
        return LLMResult(text=f"[mock:{self.model}] {user[:120]}", tokens=0)


class OpenAICompatLLM:
    """Any OpenAI-compatible chat endpoint (DeepSeek, Ark, vLLM, OpenRouter…)."""

    def __init__(self, model: str, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def complete(
        self,
        system: str,
        user: str,
        tools: list[dict] | None = None,
    ) -> LLMResult:
        import httpx

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data["choices"][0]["message"]
        tokens = int((data.get("usage") or {}).get("total_tokens", 0))

        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=str(call.get("id") or ""), name=str(fn.get("name") or ""), arguments=args)
            )

        return LLMResult(text=message.get("content") or "", tokens=tokens, tool_calls=tool_calls)


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
