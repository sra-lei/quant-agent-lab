"""财务规划官 — 任务规划 + 结论合并。

两条硬规则：
1. 专家结论冲突时，**必须**写进 `disagreements`，不许取平均后只报一个。
2. 规划官不直接给买卖点，只做取舍与合并。
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent, RunContext
from app.contracts.schemas import (
    AnalystView,
    ConclusionPick,
    Disagreement,
    MarketSnapshot,
    ResearchConclusion,
    RunRequest,
    Stance,
    TaskPlan,
)


class PlannerAgent(BaseAgent):
    name = "planner"

    # ---------------------------------------------------------------- planning
    def plan(self, request: RunRequest, run_id: str) -> TaskPlan:
        return TaskPlan(
            plan_id=f"plan_{run_id}",
            goal=request.goal,
            tasks=[
                {
                    "task_id": "t1",
                    "agent": "collector",
                    "depends_on": [],
                    "params": {"codes": request.universe, "days": 60},
                },
                {
                    "task_id": "t2",
                    "agent": "value_analyst",
                    "depends_on": ["t1"],
                    "params": {},
                },
                {
                    "task_id": "t3",
                    "agent": "momentum_analyst",
                    "depends_on": ["t1"],
                    "params": {},
                },
                {
                    "task_id": "t4",
                    "agent": "planner_synthesize",
                    "depends_on": ["t2", "t3"],
                    "params": {},
                },
            ],
        )

    # ------------------------------------------------------------- synthesize
    def _run(self, payload: dict[str, Any], ctx: RunContext) -> ResearchConclusion:
        views: list[AnalystView] = payload.get("views") or []
        snapshot: MarketSnapshot | None = ctx.snapshot
        if snapshot is None:
            raise ValueError("synthesis requires a collected snapshot")
        if not views:
            raise ValueError("synthesis requires at least one analyst view")

        # code -> list[(agent, candidate)]
        table: dict[str, list[tuple[str, Any]]] = {}
        for view in views:
            for cand in view.candidates:
                table.setdefault(cand.code, []).append((view.agent, cand))

        picks: list[ConclusionPick] = []
        disagreements: list[Disagreement] = []
        risk_notes: list[str] = []

        for code, entries in table.items():
            stances = {c.stance for _, c in entries}
            agents = [a for a, _ in entries]

            # 方向冲突 → 显式记录，不做平均
            if Stance.LONG in stances and Stance.AVOID in stances:
                parts = [
                    f"{agent}={c.stance.value}({c.conviction:.2f})" for agent, c in entries
                ]
                disagreements.append(
                    Disagreement(
                        code=code,
                        agents=agents,
                        summary="方向相反：" + "；".join(parts),
                    )
                )
                continue

            best_agent, best = max(entries, key=lambda x: x[1].conviction)
            picks.append(
                ConclusionPick(
                    code=code,
                    name=best.name or code,
                    stance=best.stance,
                    conviction=best.conviction,
                    sources=agents,
                    rationale=best.rationale,
                    risk=best.invalidation,
                )
            )

        picks.sort(key=lambda p: p.conviction, reverse=True)

        if snapshot.quality.stale:
            risk_notes.append("数据过期，本次结论置信度已整体下调")
        if snapshot.quality.missing_fields:
            preview = ", ".join(snapshot.quality.missing_fields[:5])
            risk_notes.append(f"数据缺失字段：{preview}")
        if snapshot.source == "mock":
            risk_notes.append("当前使用演示数据（mock），不代表真实行情")

        long_count = sum(1 for p in picks if p.stance is Stance.LONG)
        summary = (
            f"本次共 {len(picks)} 个候选（看多 {long_count} 个），"
            f"存在 {len(disagreements)} 处专家分歧。"
        )
        if disagreements:
            summary += "分歧标的已单列，未做合并。"

        return ResearchConclusion(
            conclusion_id=f"concl_{ctx.run_id}",
            run_id=ctx.run_id,
            as_of=ctx.as_of,
            summary=summary,
            picks=picks[:10],
            disagreements=disagreements,
            risk_notes=risk_notes,
        )
