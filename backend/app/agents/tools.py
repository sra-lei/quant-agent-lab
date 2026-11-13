"""工具注册表（声明层）。

Agent 编辑器里可选的工具**只能来自这里**——避免用户填一个不存在的工具名，
运行时才炸。

一个工具由两部分组成：
- 声明：本文件的 `ToolSpec`（key / 文案 / 参数 schema）
- 实现：`tool_handlers.py` 里同名的 handler

`args_schema` 直接作为 function calling 的参数定义交给模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    key: str
    label: str
    description: str
    #: 参数名列表（给前端展示用）
    params: list[str] = field(default_factory=list)
    #: JSON Schema，作为 function calling 的参数定义
    args_schema: dict = field(default_factory=dict)


CATALOG: dict[str, ToolSpec] = {
    "market.quotes": ToolSpec(
        key="market.quotes",
        label="日线行情",
        description="取标的的开高低收、成交量与成交额",
        params=["code", "days"],
        args_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 600519"},
                "days": {"type": "integer", "description": "回看的交易日数量", "default": 60},
            },
            "required": ["code"],
        },
    ),
    "market.fundamentals": ToolSpec(
        key="market.fundamentals",
        label="财务指标",
        description="取 PE/PB/ROE、营收与净利同比",
        params=["code", "period"],
        args_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码"},
                "period": {"type": "string", "description": "报告期，如 2026Q3"},
            },
            "required": ["code"],
        },
    ),
    "market.announcements": ToolSpec(
        key="market.announcements",
        label="公告与研报",
        description="取近 N 天公告标题、类型与日期",
        params=["code", "days"],
        args_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码"},
                "days": {"type": "integer", "description": "回看天数", "default": 90},
            },
            "required": ["code"],
        },
    ),
    "market.breadth": ToolSpec(
        key="market.breadth",
        label="市场宽度",
        description="涨跌家数、涨停跌停数、换手率",
        params=["date"],
        args_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期 YYYY-MM-DD，缺省为今天"},
            },
        },
    ),
    "zvt.kline": ToolSpec(
        key="zvt.kline",
        label="本地日线+缠论",
        description="从本地 zvt 全市场库取个股日线（后复权），附带缠论方向/笔/中枢状态",
        params=["code", "days"],
        args_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 600519"},
                "days": {"type": "integer", "description": "回看的交易日数量", "default": 60},
            },
            "required": ["code"],
        },
    ),
    "zvt.limit_board": ToolSpec(
        key="zvt.limit_board",
        label="涨停梯队（本地库）",
        description="全市场涨停股清单与连板梯队、炸板数、封板成功率、面王、涨跌家数",
        params=["date"],
        args_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "交易日 YYYY-MM-DD，缺省为库内最新交易日"},
            },
        },
    ),
    "zvt.breadth": ToolSpec(
        key="zvt.breadth",
        label="市场宽度（本地库）",
        description="涨跌家数、涨跌停数、中位涨幅、成交额、封板成功率",
        params=["date"],
        args_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "交易日 YYYY-MM-DD，缺省为库内最新交易日"},
            },
        },
    ),
    "calc.indicators": ToolSpec(
        key="calc.indicators",
        label="技术指标",
        description="计算均线、量比、区间涨跌幅等派生指标",
        params=["code", "window"],
        args_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码"},
                "window": {"type": "integer", "description": "统计窗口（交易日）", "default": 20},
            },
            "required": ["code"],
        },
    ),
    "calc.score": ToolSpec(
        key="calc.score",
        label="规则打分",
        description="按既定权重对候选做可解释打分",
        params=["pe", "roe", "growth"],
        args_schema={
            "type": "object",
            "properties": {
                "pe": {"type": "number", "description": "市盈率 TTM"},
                "roe": {"type": "number", "description": "净资产收益率（小数，0.15 表示 15%）"},
                "growth": {"type": "number", "description": "净利同比（小数）"},
            },
            "required": ["pe", "roe", "growth"],
        },
    ),
    "llm.complete": ToolSpec(
        key="llm.complete",
        label="模型生成",
        description="把素材交给大模型生成判断或文字结论",
        params=["prompt"],
        args_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "要交给模型的具体问题"},
            },
            "required": ["prompt"],
        },
    ),
    "report.write": ToolSpec(
        key="report.write",
        label="报告写入",
        description="把结构化结论写成 Markdown 报告文件",
        params=["title", "body"],
        args_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "报告标题"},
                "body": {"type": "string", "description": "Markdown 正文"},
            },
            "required": ["title", "body"],
        },
    ),
}


def all_tools() -> list[dict]:
    return [
        {
            "key": t.key,
            "label": t.label,
            "description": t.description,
            "params": t.params,
            "args_schema": t.args_schema,
        }
        for t in CATALOG.values()
    ]


def validate_tools(keys: list[str]) -> list[str]:
    """返回未知工具名（空列表表示全部合法）。"""
    return [k for k in keys if k not in CATALOG]


def openai_tools(keys: list[str]) -> list[dict]:
    """把选中的工具转成 OpenAI function calling 的 tools 参数。"""
    out: list[dict] = []
    for key in keys:
        spec = CATALOG.get(key)
        if spec is None:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": key.replace(".", "__"),
                    "description": f"{spec.label}：{spec.description}",
                    "parameters": spec.args_schema or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def key_from_function_name(name: str) -> str:
    """function name 不能带点，映射回来。"""
    return name.replace("__", ".")


OUTPUT_FORMATS: list[dict] = [
    {
        "type": "json_schema",
        "label": "JSON Schema（结构化）",
        "description": "输出必须通过给定 JSON Schema 校验，适合下游程序消费",
    },
    {
        "type": "markdown_table",
        "label": "Markdown 表格",
        "description": "输出为可读表格，适合直接展示",
    },
    {
        "type": "text",
        "label": "纯文本",
        "description": "自由文本结论，不做结构约束",
    },
]

DEFAULT_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["code", "stance", "conviction", "rationale"],
                "properties": {
                    "code": {"type": "string"},
                    "stance": {"type": "string", "enum": ["long", "watch", "avoid"]},
                    "conviction": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string"},
                },
            },
        },
        "notes": {"type": "string"},
    },
}
