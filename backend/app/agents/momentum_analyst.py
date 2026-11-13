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

        # 全市场情绪温度：涨跌家数与涨停数（数据源可能只给其中一部分）
        b = snapshot.breadth
        heat: float | None = None
        if b.advancers is not None and b.decliners is not None:
            total = max(b.advancers + b.decliners, 1)
            heat = b.advancers / total
        else:
            warnings.append("数据源未提供涨跌家数，市场温度维度未计分")

        if b.limit_up is None:
            mood, mood_adj = "未知", 0.0
            warnings.append("数据源未提供涨停家数，情绪修正未生效")
        elif b.limit_up >= 60:
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
            raw_volumes = [x.volume for x in bars]
            volumes = [v for v in raw_volumes if v is not None]
            if len(closes) < 6:
                continue

            ret5 = _pct(closes, 5)
            # 部分数据源（问小达）单次最多给 20 个交易日，不足以算 20 日动量
            ret20 = _pct(closes, 20) if len(closes) >= 21 else None
            # 数据源可能不提供成交量（如问小达部分查询），此时不做量能加分，并标注
            has_volume = len(raw_volumes) >= 6 and all(v is not None for v in raw_volumes[-6:])
            avg_vol = mean(volumes[-6:-1]) if has_volume else 0
            vol_ratio = (volumes[-1] / avg_vol) if avg_vol else 0.0
            if not has_volume:
                warnings.append(f"{code} 缺少成交量数据，量能维度记为 0")

            if ret5 is None:
                continue

            score = 0.0
            score += 0.4 * _clip((ret5 + 0.05) / 0.10)      # 5 日动量
            score += 0.3 * _clip((vol_ratio - 0.8) / 1.2)   # 量能放大
            if ret20 is not None:
                score += 0.2 * _clip((ret20 + 0.10) / 0.20)  # 中期趋势
            else:
                warnings.append(f"{code} 历史不足 21 根，20 日趋势维度未计分")
            score += 0.1 * _clip(heat) if heat is not None else 0.0   # 市场温度
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
                        f"5 日 {ret5:+.1%}、20 日 {f'{ret20:+.1%}' if ret20 is not None else '—'}、量比 {vol_ratio:.2f}；"
                        f"情绪阶段：{stage}（全市场 {mood}，涨停 {b.limit_up if b.limit_up is not None else '—'} 家）"
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
            notes=f"全市场情绪：{mood}（上涨 {b.advancers if b.advancers is not None else '—'} / 下跌 {b.decliners if b.decliners is not None else '—'}，涨停 {b.limit_up if b.limit_up is not None else '—'}）",
            warnings=warnings,
        )


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
