"""配置驱动的 Agent。

编辑器保存的配置（角色 / 工作流 / 工具 / 输出格式）在这里被真正执行，
所以"保存后能不能跑"不是靠猜。v0.1 用 LLM 抽象层，未配 key 时走 Mock。
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from app.agents.tool_handlers import ToolContext, execute_tool
from app.agents.tools import key_from_function_name, openai_tools
from app.core.llm import estimate_tokens, get_llm
from app.core.logging import get_logger
from app.data.registry import get_provider

log = get_logger(__name__)

#: 单次运行最多几轮"模型 → 工具 → 模型"
MAX_TOOL_ROUNDS = 4


class ConfigAgentError(RuntimeError):
    pass


def build_prompt(config: dict[str, Any], input_payload: dict[str, Any]) -> str:
    role = config.get("role") or "你是一名投研分析师。"
    steps = config.get("workflow") or []
    tools = config.get("tools") or []
    fmt = (config.get("output_format") or {}).get("type", "text")

    step_lines = "\n".join(
        f"{i + 1}. {s.get('name', '')}：{s.get('instruction', '')}"
        for i, s in enumerate(steps)
    ) or "（未定义工作流，按角色描述自行处理）"

    tool_lines = "\n".join(f"- {t}" for t in tools) or "（无可用工具，仅凭输入数据推理）"

    fmt_hint = {
        "json_schema": "严格输出 JSON，且必须符合给定 schema，不要包裹解释性文字。",
        "markdown_table": "输出 Markdown 表格，表头用中文。",
        "text": "输出简洁的中文结论，要点化。",
    }.get(fmt, "输出简洁的中文结论。")

    return f"""{role}

## 你的工作流
{step_lines}

## 你可以使用的工具
{tool_lines}

## 输出要求
{fmt_hint}

## 本次输入
{json.dumps(input_payload, ensure_ascii=False, indent=2)}
"""


def run_config_agent(
    config: dict[str, Any],
    input_payload: dict[str, Any],
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    """执行一次配置驱动的 Agent：模型可多轮调用工具，最后产出结论。"""
    prompt = build_prompt(config, input_payload)
    tool_keys = list(config.get("tools") or [])
    tools = openai_tools(tool_keys)

    llm = get_llm(tier="strong" if tool_keys else "cheap")
    is_mock = type(llm).__name__ == "MockLLM"

    tool_ctx = ctx or ToolContext(provider=get_provider(), as_of=date.today())

    transcript = prompt
    text = ""
    tokens = 0
    tool_trace: list[dict[str, Any]] = []
    rounds = 0

    for rounds in range(1, MAX_TOOL_ROUNDS + 1):
        result = llm.complete(
            system="你是一个严格遵循工作流与输出格式的投研 Agent。需要数据时调用工具，不要凭记忆编造数字。",
            user=transcript,
            tools=tools or None,
        )
        tokens += result.tokens

        if not result.tool_calls:
            text = result.text
            break

        batch: list[dict[str, Any]] = []
        for call in result.tool_calls:
            key = key_from_function_name(call.name)
            if key not in tool_keys:
                batch.append({"tool": key, "error": "该工具不在本 Agent 的可用列表中，已拒绝执行"})
                continue
            output = execute_tool(tool_ctx, key, call.arguments)
            batch.append({"tool": key, "args": call.arguments, "result": output})

        tool_trace.extend(batch)
        transcript += "\n\n## 工具执行结果\n" + json.dumps(batch, ensure_ascii=False, indent=2)[:6000]
        transcript += "\n\n请基于以上工具结果给出最终答案。"

    output_format = config.get("output_format") or {}
    parsed: Any = None
    error: str | None = None

    if output_format.get("type") == "json_schema":
        try:
            parsed = _extract_json(text) if text else None
            if parsed is None:
                raise ConfigAgentError("模型未返回 JSON")
            _validate(parsed, output_format.get("schema") or {})
        except Exception as exc:  # noqa: BLE001
            if is_mock:
                # 演示模式：模型不会真的产出合规 JSON，按 schema 造样例，
                # 但保留 mock 标记，前端会明确提示这不是真实推理。
                parsed = _sample_from_schema(output_format.get("schema") or {})
                error = None
            else:
                error = f"输出未通过 schema 校验：{exc}"
                parsed = None

    if not text and not tool_trace:
        error = error or "模型没有返回内容"

    return {
        "agent_id": config.get("agent_id"),
        "output": parsed if parsed is not None else (text or tool_trace),
        "raw": text,
        "format_ok": error is None,
        "error": error,
        "tokens": tokens or estimate_tokens(transcript),
        "mock": is_mock,
        "tool_calls": tool_trace,
        "rounds": rounds,
        "prompt_preview": prompt[:800],
    }


def _sample_from_schema(schema: dict[str, Any]) -> Any:
    """按 schema 生成一个最小合法样例（仅用于无 Key 的演示模式）。"""
    if not schema:
        return {}

    kind = schema.get("type", "object")
    if kind == "object":
        required = schema.get("required") or list((schema.get("properties") or {}).keys())
        props = schema.get("properties") or {}
        return {key: _sample_from_schema(props.get(key, {})) for key in required}

    if kind == "array":
        return [_sample_from_schema(schema.get("items") or {})]

    if kind == "string":
        enum = schema.get("enum")
        return enum[0] if enum else "示例"

    if kind == "integer":
        return int(schema.get("minimum", 0))

    if kind == "number":
        return float(schema.get("minimum", 0))

    if kind == "boolean":
        return True

    return None


# --------------------------------------------------------------------- helpers
def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ConfigAgentError("输出中找不到 JSON") from None
        return json.loads(match.group(0))


def _validate(data: Any, schema: dict[str, Any]) -> None:
    """极简 JSON Schema 校验：只覆盖我们用到的关键字。

    不引入 jsonschema 依赖——开源用户不该为了一个校验器多装一个包。
    支持的：type / required / properties / enum / minimum / maximum / items。
    """
    if not schema:
        return

    expected = schema.get("type")
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
    }
    if expected and expected in types and not isinstance(data, types[expected]):
        raise ConfigAgentError(f"期望 {expected}，实际 {type(data).__name__}")

    if expected == "object":
        for key in schema.get("required", []):
            if key not in data:
                raise ConfigAgentError(f"缺少必填字段 {key}")
        for key, sub in (schema.get("properties") or {}).items():
            if key in data:
                _validate(data[key], sub)

    elif expected == "array":
        items = schema.get("items") or {}
        for idx, item in enumerate(data):
            try:
                _validate(item, items)
            except ConfigAgentError as exc:
                raise ConfigAgentError(f"第 {idx} 项：{exc}") from exc

    if "enum" in schema and data not in schema["enum"]:
        raise ConfigAgentError(f"{data!r} 不在允许值 {schema['enum']} 中")

    if isinstance(data, (int, float)):
        if "minimum" in schema and data < schema["minimum"]:
            raise ConfigAgentError(f"{data} 小于最小值 {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            raise ConfigAgentError(f"{data} 大于最大值 {schema['maximum']}")
