"""信息收集员 — 数据管道。

职责单一：把外部数据洗成一份符合契约的 `MarketSnapshot`。
不判断好坏，不预测涨跌，不缺字段就填 0。
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent, RunContext
from app.contracts.schemas import MarketSnapshot
from app.data.aggregator import build_snapshot


class CollectorAgent(BaseAgent):
    name = "collector"

    def _run(self, payload: dict[str, Any], ctx: RunContext) -> MarketSnapshot:
        codes: list[str] = payload.get("codes") or []
        if not codes:
            raise ValueError("collector requires a non-empty 'codes' list")

        snapshot = build_snapshot(
            codes=codes,
            as_of=ctx.as_of,
            provider=ctx.provider,
            run_id=ctx.run_id,
            lookback_days=int(payload.get("days", 60)),
        )
        ctx.artifacts["snapshot"] = snapshot
        return snapshot
