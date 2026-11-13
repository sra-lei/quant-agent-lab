"""工具注册表。

Agent 编辑器里可选的工具**只能来自这里**——避免用户填一个不存在的工具名，
运行时才炸。新增工具只需在 CATALOG 里加一条。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    key: str
    label: str
    description: str
    #: 该工具需要的数据/参数说明，会拼进运行时提示词
    params: list[str] = field(default_factory=list)


CATALOG: dict[str, ToolSpec] = {
    "market.quotes": ToolSpec(
        key="market.quotes",
        label="日线行情",
        description="取标的的开高低收、成交量与成交额",
        params=["code", "days"],
    ),
    "market.fundamentals": ToolSpec(
        key="market.fundamentals",
        label="财务指标",
        description="取 PE/PB/ROE、营收与净利同比",
        params=["code", "period"],
    ),
    "market.announcements": ToolSpec(
        key="market.announcements",
        label="公告与研报",
        description="取近 N 天公告标题、类型与日期",
        params=["code", "days"],
    ),
    "market.breadth": ToolSpec(
        key="market.breadth",
        label="市场宽度",
        description="涨跌家数、涨停跌停数、换手率",
        params=["date"],
    ),
    "calc.indicators": ToolSpec(
        key="calc.indicators",
        label="技术指标",
        description="计算均线、量比、区间涨跌幅等派生指标",
        params=["code", "window"],
    ),
    "calc.score": ToolSpec(
        key="calc.score",
        label="规则打分",
        description="按既定权重对候选做可解释打分",
        params=["weights"],
    ),
    "llm.complete": ToolSpec(
        key="llm.complete",
        label="模型生成",
        description="把素材交给大模型生成判断或文字结论",
        params=["prompt"],
    ),
    "report.write": ToolSpec(
        key="report.write",
        label="报告写入",
        description="把结构化结论落库并生成可读报告",
        params=["conclusion"],
    ),
}


def all_tools() -> list[dict]:
    return [
        {"key": t.key, "label": t.label, "description": t.description, "params": t.params}
        for t in CATALOG.values()
    ]


def validate_tools(keys: list[str]) -> list[str]:
    """返回未知工具名（空列表表示全部合法）。"""
    return [k for k in keys if k not in CATALOG]


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
