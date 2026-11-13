"""价投专家 — 基本面视角。

v0.1 用可解释的打分规则（估值 / 盈利能力 / 成长），**不调用 LLM**：
规则可以被审计、被回测，也能在没有 API Key 时跑通。v0.2 再把"把结论写成
人话"这一步交给 LLM，规则本身保持确定性。
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent, RunContext
from app.contracts.schemas import AnalystView, Candidate, MarketSnapshot, Stance

# 缺失数据时的中性分，避免"没数据反而排前"
NEUTRAL = 0.3


def _pe_score(pe: float | None) -> float:
    if pe is None or pe <= 0:
        return NEUTRAL
    if pe <= 15:
        return 1.0
    if pe <= 25:
        return 0.7
    if pe <= 40:
        return 0.4
    return 0.1


def _roe_score(roe: float | None) -> float:
    if roe is None:
        return NEUTRAL
    if roe >= 0.20:
        return 1.0
    if roe >= 0.12:
        return 0.7
    if roe >= 0.06:
        return 0.4
    return 0.1


def _growth_score(yoy: float | None) -> float:
    if yoy is None:
        return NEUTRAL
    if yoy >= 0.20:
        return 1.0
    if yoy >= 0.05:
        return 0.6
    if yoy >= 0:
        return 0.4
    return 0.1


class ValueAnalystAgent(BaseAgent):
    name = "value_analyst"

    def _run(self, payload: dict[str, Any], ctx: RunContext) -> AnalystView:
        snapshot: MarketSnapshot | None = ctx.snapshot
        if snapshot is None:
            raise ValueError("value_analyst requires a collected snapshot")

        max_conviction = float(payload.get("max_conviction", 0.9))
        candidates: list[Candidate] = []
        warnings: list[str] = []

        if snapshot.quality.stale:
            max_conviction = min(max_conviction, 0.5)
            warnings.append("数据过期（stale），本次结论置信度上限已下调至 0.5")

        anomalous = {a.get("code") for a in snapshot.quality.anomalies}

        for code in snapshot.universe:
            fund = snapshot.fundamentals.get(code)
            if fund is None:
                continue

            score = (
                0.4 * _pe_score(fund.pe_ttm)
                + 0.3 * _roe_score(fund.roe)
                + 0.3 * _growth_score(fund.net_profit_yoy)
            )
            if code in anomalous:
                score = min(score, 0.5)

            conviction = round(min(score, max_conviction), 3)
            if conviction >= 0.70:
                stance = Stance.LONG
            elif conviction >= 0.45:
                stance = Stance.WATCH
            else:
                stance = Stance.AVOID

            close = snapshot.close(code)
            candidates.append(
                Candidate(
                    code=code,
                    name=_name_of(snapshot, code),
                    stance=stance,
                    conviction=conviction,
                    horizon_days=60,
                    rationale=(
                        f"PE={fund.pe_ttm}（估值分 {_pe_score(fund.pe_ttm):.2f}）、"
                        f"ROE={fund.roe}（{_roe_score(fund.roe):.2f}）、"
                        f"净利同比={fund.net_profit_yoy}（{_growth_score(fund.net_profit_yoy):.2f}）；"
                        f"综合 {conviction:.2f}"
                    ),
                    entry_zone=_zone(close),
                    invalidation="下季度净利同比转负，或估值分位升破 60%",
                    evidence=[f"{snapshot.snapshot_id}.fundamentals.{code}"],
                )
            )

        candidates.sort(key=lambda c: c.conviction, reverse=True)
        return AnalystView(
            view_id=f"view_value_{snapshot.snapshot_id}",
            agent=self.name,
            snapshot_id=snapshot.snapshot_id,
            as_of=snapshot.as_of,
            candidates=candidates[:10],
            notes="规则打分：估值 40% + 盈利能力 30% + 成长 30%",
            warnings=warnings,
        )


def _name_of(snapshot: MarketSnapshot, code: str) -> str:
    return str(snapshot.artifacts_names.get(code, "")) if hasattr(snapshot, "artifacts_names") else code


def _zone(close: float | None) -> list[float]:
    if not close:
        return []
    return [round(close * 0.97, 2), round(close * 1.03, 2)]
