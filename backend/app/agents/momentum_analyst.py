"""游资专家 — 情绪与量价视角。

v0.1 只看三件事：短期动量、量能放大、以及全市场情绪温度。
它**不判断公司好坏**，这正是它和价投专家分开的原因——两路结论冲突时，
冲突本身就是信息，不该被平均掉。
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from app.agents.base import BaseAgent, RunContext
from app.contracts.schemas import AnalystView, Candidate, MarketSnapshot, Stance


def _pct(series: list[float], window: int) -> float | None:
    if len(series) <= window:
        return None
    base = series[-1 - window]
    return None if not base else series[-1] / base - 1


class MomentumAnalystAgent(BaseAgent):
    name = "momentum_analyst"

    def _run(self, payload: dict[str, Any], ctx: RunContext) -> AnalystView:
        snapshot: MarketSnapshot | None = ctx.snapshot
        if snapshot is None:
            raise ValueError("momentum_analyst requires a collected snapshot")

        min_vol_ratio = float(payload.get("min_volume_ratio", 1.2))
        max_conviction = float(payload.get("max_conviction", 0.9))
        warnings: list[str] = []

        # 全市场情绪温度：涨跌家数与涨停数
        b = snapshot.breadth
        total = max(b.advancers + b.decliners, 1)
        heat = b.advancers / total
        if b.limit_up >= 60:
            mood, mood_adj = "偏热", 0.05
        elif b.limit_up >= 25:
            mood, mood_adj = "中性偏暖", 0.0
        else:
            mood, mood_adj = "偏冷", -0.05

        if snapshot.quality.stale:
            max_conviction = min(max_conviction, 0.5)
            warnings.append("数据过期（stale），情绪面结论仅供参考")

        candidates: list[Candidate] = []
        for code in snapshot.universe:
            bars = snapshot.bars.get(code) or []
            closes = [x.close for x in bars]
            volumes = [x.volume for x in bars]
            if len(closes) < 21:
                continue

            ret5 = _pct(closes, 5)
            ret20 = _pct(closes, 20)
            avg_vol = mean(volumes[-6:-1]) if len(volumes) >= 6 else 0
            vol_ratio = (volumes[-1] / avg_vol) if avg_vol else 0.0

            if ret5 is None or ret20 is None:
                continue

            score = 0.0
            score += 0.4 * _clip((ret5 + 0.05) / 0.10)      # 5 日动量
            score += 0.3 * _clip((vol_ratio - 0.8) / 1.2)   # 量能放大
            score += 0.2 * _clip((ret20 + 0.10) / 0.20)     # 中期趋势
            score += 0.1 * _clip(heat)                       # 市场温度
            score = _clip(score + mood_adj)

            conviction = round(min(score, max_conviction), 3)

            if conviction >= 0.65 and vol_ratio >= min_vol_ratio:
                stance = Stance.LONG
                stage = "启动/发酵"
            elif conviction >= 0.45:
                stance = Stance.WATCH
                stage = "观察"
            else:
                stance = Stance.AVOID
                stage = "退潮/无催化"

            close = closes[-1]
            candidates.append(
                Candidate(
                    code=code,
                    name=code,
                    stance=stance,
                    conviction=conviction,
                    horizon_days=5,
                    rationale=(
                        f"5 日 {ret5:+.1%}、20 日 {ret20:+.1%}、量比 {vol_ratio:.2f}；"
                        f"情绪阶段：{stage}（全市场 {mood}，涨停 {b.limit_up} 家）"
                    ),
                    entry_zone=[round(close * 0.98, 2), round(close * 1.02, 2)],
                    invalidation="量能萎缩至 5 日均量 80% 以下，或跌破 5 日均线",
                    evidence=[f"{snapshot.snapshot_id}.bars.{code}"],
                )
            )

        candidates.sort(key=lambda c: c.conviction, reverse=True)
        return AnalystView(
            view_id=f"view_momentum_{snapshot.snapshot_id}",
            agent=self.name,
            snapshot_id=snapshot.snapshot_id,
            as_of=snapshot.as_of,
            candidates=candidates[:10],
            notes=f"全市场情绪：{mood}（上涨 {b.advancers} / 下跌 {b.decliners}，涨停 {b.limit_up}）",
            warnings=warnings,
        )


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
