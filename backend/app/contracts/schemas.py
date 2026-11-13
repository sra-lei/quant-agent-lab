"""Agent-facing contracts.

These models are the *only* thing agents exchange. Changing them is a breaking
change: bump `schema_version` and update docs/03-Agent契约.md in the same PR.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "1.0"


class Stance(str, Enum):
    LONG = "long"
    WATCH = "watch"
    AVOID = "avoid"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    goal: str = Field(..., min_length=2, description="本次研究目标")
    capital: float = Field(default=100_000, gt=0)
    risk: Literal["low", "medium", "high"] = "medium"
    universe: list[str] = Field(default_factory=list, description="留空表示全市场（受 MAX_UNIVERSE 限制）")


class PlannedTask(BaseModel):
    task_id: str
    agent: str
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class TaskPlan(BaseModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: str
    goal: str
    tasks: list[PlannedTask]
    budget: dict[str, int] = Field(default_factory=lambda: {"max_tokens": 120_000, "deadline_s": 600})

    @field_validator("tasks")
    @classmethod
    def _non_empty(cls, v: list[PlannedTask]) -> list[PlannedTask]:
        if not v:
            raise ValueError("plan must contain at least one task")
        return v


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
class Bar(BaseModel):
    date: date
    close: float
    #: 部分数据源（如问小达）只提供收盘价与成交量，其余字段留空不臆造
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None


class Fundamental(BaseModel):
    pe_ttm: float | None = None
    pb: float | None = None
    roe: float | None = None
    revenue_yoy: float | None = None
    net_profit_yoy: float | None = None
    report_period: str | None = None


class Announcement(BaseModel):
    code: str
    date: date
    type: str = "其他"
    title: str


class MarketBreadth(BaseModel):
    #: 数据源可能只提供部分字段；None 表示"没拿到"，不是 0
    advancers: int | None = None
    decliners: int | None = None
    limit_up: int | None = None
    limit_down: int | None = None
    turnover_rate: float | None = None


class Quality(BaseModel):
    stale: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    anomalies: list[dict[str, str]] = Field(default_factory=list)


class MarketSnapshot(BaseModel):
    schema_version: str = SCHEMA_VERSION
    snapshot_id: str
    as_of: date
    source: str
    universe: list[str]
    bars: dict[str, list[Bar]] = Field(default_factory=dict)
    breadth: MarketBreadth = Field(default_factory=MarketBreadth)
    fundamentals: dict[str, Fundamental] = Field(default_factory=dict)
    announcements: list[Announcement] = Field(default_factory=list)
    quality: Quality = Field(default_factory=Quality)

    def close(self, code: str) -> float | None:
        series = self.bars.get(code) or []
        return series[-1].close if series else None


# ---------------------------------------------------------------------------
# Analysts
# ---------------------------------------------------------------------------
class Candidate(BaseModel):
    code: str
    name: str = ""
    stance: Stance = Stance.WATCH
    conviction: float = Field(default=0.5, ge=0.0, le=1.0)
    horizon_days: int = 30
    rationale: str
    entry_zone: list[float] = Field(default_factory=list)
    invalidation: str = ""
    evidence: list[str] = Field(default_factory=list)


class AnalystView(BaseModel):
    schema_version: str = SCHEMA_VERSION
    view_id: str
    agent: str
    snapshot_id: str
    as_of: date
    candidates: list[Candidate] = Field(default_factory=list)
    notes: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Planner synthesis
# ---------------------------------------------------------------------------
class ConclusionPick(BaseModel):
    code: str
    name: str = ""
    stance: Stance
    conviction: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    rationale: str = ""
    risk: str = ""


class Disagreement(BaseModel):
    code: str
    agents: list[str]
    summary: str


class ResearchConclusion(BaseModel):
    schema_version: str = SCHEMA_VERSION
    conclusion_id: str
    run_id: str
    as_of: date
    summary: str
    picks: list[ConclusionPick] = Field(default_factory=list)
    disagreements: list[Disagreement] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    disclaimer: str = "本结论由自动化系统生成，不构成投资建议。"


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------
class Attribution(BaseModel):
    code: str
    verdict: Literal["hit", "miss", "flat"]
    reason: str


class AgentScore(BaseModel):
    hit_rate: float
    samples: int
    avg_return: float


class ReviewReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    review_id: str
    period: str
    as_of: date
    samples: int = 0
    hit_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    by_agent: dict[str, AgentScore] = Field(default_factory=dict)
    attributions: list[Attribution] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    insufficient_samples: bool = False
