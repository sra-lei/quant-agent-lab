"""预置 Agent 配置。

首次启动时写入数据库；已存在则不覆盖（用户可能已经改过）。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.tools import DEFAULT_OUTPUT_SCHEMA
from app.core.logging import get_logger
from app.db.models import AgentConfigRow

log = get_logger(__name__)


def _json_out(schema: dict | None = None) -> dict:
    return {"type": "json_schema", "schema": schema or DEFAULT_OUTPUT_SCHEMA}


BUILTIN_AGENTS: list[dict] = [
    {
        "agent_id": "collector",
        "name": "信息收集员",
        "role": "你是数据管道。职责是把外部行情、财务、公告数据清洗成统一口径的快照，不判断好坏、不做预测。",
        "workflow": [
            {"name": "取标的池", "instruction": "确认本次要覆盖的标的与时间窗"},
            {"name": "拉取原始数据", "instruction": "按日线、财务、公告、市场宽度四类分别取数"},
            {"name": "质量校验", "instruction": "检查新鲜度、缺失字段与异常值，缺失一律置 null 并登记"},
            {"name": "组装快照", "instruction": "输出统一结构的 MarketSnapshot，并标注来源与 as_of"},
        ],
        "tools": ["market.quotes", "market.fundamentals", "market.announcements", "market.breadth"],
        "output_format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "required": ["as_of", "source", "universe"],
                "properties": {
                    "as_of": {"type": "string"},
                    "source": {"type": "string"},
                    "universe": {"type": "array", "items": {"type": "string"}},
                    "missing_fields": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "agent_id": "value_analyst",
        "name": "价投专家",
        "role": "你是基本面分析师。只依据估值、盈利能力与成长性做判断，不使用情绪面指标作为主要依据。",
        "workflow": [
            {"name": "估值定位", "instruction": "看 PE/PB 处于历史什么分位，是否具备安全边际"},
            {"name": "盈利质量", "instruction": "看 ROE、现金流与净利增速是否可持续"},
            {"name": "给出候选", "instruction": "每个候选必须写明估值方法、关键假设与证伪条件"},
        ],
        "tools": ["market.fundamentals", "calc.score", "llm.complete"],
        "output_format": _json_out(),
    },
    {
        "agent_id": "momentum_analyst",
        "name": "游资专家",
        "role": "你是短线情绪交易员。只看资金、量价与情绪阶段，不判断公司好不好。",
        "workflow": [
            {"name": "情绪定位", "instruction": "判断全市场处于启动、发酵还是退潮阶段"},
            {"name": "个股量价", "instruction": "看短期动量、量能放大与换手变化"},
            {"name": "给出候选", "instruction": "必须写明驱动逻辑、情绪阶段与失效条件"},
        ],
        "tools": ["market.quotes", "market.breadth", "calc.indicators", "llm.complete"],
        "output_format": _json_out(),
    },
    {
        "agent_id": "planner",
        "name": "财务规划官",
        "role": "你是投研组长。负责把目标拆成任务、派给专家，并合并结论。你不直接给买卖点。",
        "workflow": [
            {"name": "拆解目标", "instruction": "把研究目标拆成可执行的任务 DAG"},
            {"name": "分派任务", "instruction": "按任务依赖关系分派给合适的专家"},
            {"name": "合并结论", "instruction": "专家方向冲突时必须单列分歧，禁止取平均"},
        ],
        "tools": ["report.write", "llm.complete"],
        "output_format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "required": ["summary"],
                "properties": {
                    "summary": {"type": "string"},
                    "picks": {"type": "array", "items": {"type": "object"}},
                    "disagreements": {"type": "array", "items": {"type": "object"}},
                    "risk_notes": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "agent_id": "reviewer",
        "name": "观察员",
        "role": "你是复盘官。只评价已经发生的事，用真实行情回算命中率，并给出可执行的改进项。",
        "workflow": [
            {"name": "读取历史结论", "instruction": "取本周期所有结论快照与入场记录"},
            {"name": "回算表现", "instruction": "计算命中率、平均收益与最大回撤"},
            {"name": "归因", "instruction": "区分数据问题、逻辑问题与执行问题"},
            {"name": "提出改进", "instruction": "改进项必须具体可执行，不接受“加强研究”这类空话"},
        ],
        "tools": ["market.quotes", "calc.score", "report.write"],
        "output_format": _json_out(
            {
                "type": "object",
                "required": ["samples", "hit_rate"],
                "properties": {
                    "samples": {"type": "integer", "minimum": 0},
                    "hit_rate": {"type": "number", "minimum": 0, "maximum": 1},
                    "avg_return": {"type": "number"},
                    "improvements": {"type": "array", "items": {"type": "string"}},
                },
            }
        ),
    },
]


def seed_builtin_agents(db: Session) -> int:
    """插入缺失的内置 Agent，返回新增数量。幂等。"""
    existing = {row.agent_id for row in db.query(AgentConfigRow.agent_id).all()}
    added = 0
    for item in BUILTIN_AGENTS:
        if item["agent_id"] in existing:
            continue
        db.add(AgentConfigRow(builtin=True, enabled=True, **item))
        added += 1
    if added:
        db.commit()
        log.info("seeded %d builtin agent configs", added)
    return added
