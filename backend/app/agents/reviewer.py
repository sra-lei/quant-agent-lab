"""观察员 — 复盘与评分。

v0.1：给出可计算的评分骨架。没有历史结论时明确返回
`insufficient_samples=True`，而不是编一个"表现良好"。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.agents.base import BaseAgent, RunContext
from app.contracts.schemas import (
    AgentScore,
    Attribution,
    ConclusionPick,
    MarketSnapshot,
    ReviewReport,
    Stance,
)

MIN_SAMPLES = 5


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def _run(self, payload: dict[str, Any], ctx: RunContext) -> ReviewReport:
        """payload:
        {
          "period": "2026-W46",
          "picks": [ {code, stance, sources:[agent], entry_close} ],
        }
        """
        period = str(payload.get("period") or f"{ctx.as_of.year}-W{ctx.as_of.isocalendar().week}")
        raw_picks: list[dict[str, Any]] = payload.get("picks") or []
        snapshot: MarketSnapshot | None = ctx.snapshot

        if not raw_picks or snapshot is None:
            return ReviewReport(
                review_id=f"review_{period}",
                period=period,
                as_of=ctx.as_of,
                samples=0,
                insufficient_samples=True,
                improvements=["历史结论样本不足，先积累 3 个交易日以上再评估"],
            )

        attributions: list[Attribution] = []
        returns: list[float] = []
        per_agent: dict[str, list[float]] = {}

        for item in raw_picks:
            pick = ConclusionPick(**item.get("pick", item)) if "pick" in item else None
            if pick is None:
                continue
            current = snapshot.close(pick.code)
            entry = item.get("entry_close")
            if not current or not entry:
                continue

            ret = current / entry - 1
            returns.append(ret)

            verdict = "hit" if ret > 0.01 else ("miss" if ret < -0.01 else "flat")
            attributions.append(
                Attribution(
                    code=pick.code,
                    verdict=verdict,
                    reason=f"自记录以来 {ret:+.2%}（stance={pick.stance.value}）",
                )
            )
            for agent in pick.sources:
                per_agent.setdefault(agent, []).append(ret)

        samples = len(returns)
        if samples == 0:
            return ReviewReport(
                review_id=f"review_{period}",
                period=period,
                as_of=ctx.as_of,
                samples=0,
                insufficient_samples=True,
                improvements=["无有效样本：入场价或当前价缺失"],
            )

        hit_rate = sum(1 for r in returns if r > 0.01) / samples
        avg_return = sum(returns) / samples
        max_dd = min(returns)

        by_agent = {
            agent: AgentScore(
                hit_rate=sum(1 for r in rs if r > 0.01) / len(rs),
                samples=len(rs),
                avg_return=sum(rs) / len(rs),
            )
            for agent, rs in per_agent.items()
            if rs
        }

        improvements: list[str] = []
        for agent, score in by_agent.items():
            if score.samples >= MIN_SAMPLES and score.hit_rate < 0.45:
                improvements.append(
                    f"{agent} 命中率 {score.hit_rate:.0%}（{score.samples} 样本），"
                    "建议收紧入场条件而非放宽选股范围"
                )
        if not improvements:
            improvements.append("本轮无显著退化信号；继续观察是否存在样本外失效")

        return ReviewReport(
            review_id=f"review_{period}",
            period=period,
            as_of=ctx.as_of,
            samples=samples,
            hit_rate=round(hit_rate, 4),
            avg_return=round(avg_return, 4),
            max_drawdown=round(max_dd, 4),
            by_agent=by_agent,
            attributions=attributions[:20],
            improvements=improvements,
            insufficient_samples=samples < MIN_SAMPLES,
        )
