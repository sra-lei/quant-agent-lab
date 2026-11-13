"""Orchestrator interface.

Two implementations share one contract:
- SimpleOrchestrator  (built-in, no extra deps)  ← default
- LangGraphOrchestrator (optional dependency)    ← learning / checkpointing

Business code (agents + contracts) never imports either of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agents.base import RunContext
from app.contracts.schemas import AnalystView, MarketSnapshot, ResearchConclusion, TaskPlan


@dataclass
class RunResult:
    run_id: str
    status: str
    conclusion: ResearchConclusion | None = None
    snapshot: MarketSnapshot | None = None
    views: list[AnalystView] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    tokens: int = 0


class Orchestrator(Protocol):
    name: str

    def run(self, plan: TaskPlan, ctx: RunContext) -> RunResult: ...


class PlanError(ValueError):
    """Raised when a plan is malformed (cycle, unknown agent, missing dep)."""


def validate_plan(plan: TaskPlan, known_agents: set[str], synthesize_task: str) -> None:
    ids = {t.task_id for t in plan.tasks}
    if len(ids) != len(plan.tasks):
        raise PlanError("duplicate task_id in plan")

    for task in plan.tasks:
        if task.agent != synthesize_task and task.agent not in known_agents:
            raise PlanError(f"task {task.task_id} references unknown agent {task.agent!r}")
        for dep in task.depends_on:
            if dep not in ids:
                raise PlanError(f"task {task.task_id} depends on missing task {dep!r}")

    # cycle detection (Kahn)
    indegree = {t.task_id: len(t.depends_on) for t in plan.tasks}
    edges: dict[str, list[str]] = {t.task_id: [] for t in plan.tasks}
    for t in plan.tasks:
        for dep in t.depends_on:
            edges[dep].append(t.task_id)

    ready = [tid for tid, deg in indegree.items() if deg == 0]
    seen = 0
    while ready:
        tid = ready.pop()
        seen += 1
        for nxt in edges[tid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    if seen != len(plan.tasks):
        raise PlanError("plan contains a dependency cycle")
