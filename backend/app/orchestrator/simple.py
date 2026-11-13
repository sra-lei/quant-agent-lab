"""Built-in orchestrator: topological execution with parallel fan-out.

~120 lines, zero dependencies, fully readable. This is the reference
implementation the LangGraph version is checked against.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.agents.base import RunContext
from app.agents.registry import SYNTHESIZE_TASK, get_agent, planner, registered_agents
from app.contracts.schemas import AnalystView, MarketSnapshot, ResearchConclusion, TaskPlan
from app.core.logging import get_logger
from app.orchestrator.base import RunResult, validate_plan

log = get_logger(__name__)


class SimpleOrchestrator:
    name = "simple"

    def run(self, plan: TaskPlan, ctx: RunContext) -> RunResult:
        validate_plan(plan, set(registered_agents()), SYNTHESIZE_TASK)

        pending = {t.task_id: t for t in plan.tasks}
        done: dict[str, Any] = {}
        views: list[AnalystView] = []
        snapshot: MarketSnapshot | None = None
        conclusion: ResearchConclusion | None = None
        error: str | None = None

        while pending:
            ready = [
                t for t in pending.values()
                if all(dep in done for dep in t.depends_on)
            ]
            if not ready:
                raise RuntimeError("deadlock: no runnable task (should be caught by validate_plan)")

            # independent tasks run in parallel; the collector is first anyway
            with ThreadPoolExecutor(max_workers=min(4, len(ready))) as pool:
                futures = {pool.submit(self._execute, t, ctx, done): t for t in ready}
                for fut in as_completed(futures):
                    task = futures[fut]
                    try:
                        result = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        error = f"task {task.task_id} ({task.agent}) failed: {exc}"
                        log.error(error)
                        done[task.task_id] = None
                        pending.pop(task.task_id, None)
                        continue

                    done[task.task_id] = result
                    pending.pop(task.task_id, None)

                    if isinstance(result, MarketSnapshot):
                        snapshot = result
                    elif isinstance(result, AnalystView):
                        views.append(result)
                    elif isinstance(result, ResearchConclusion):
                        conclusion = result

        if conclusion is None:
            # synthesis never ran → return what we have, with an honest error
            error = error or "synthesis did not produce a conclusion"

        return RunResult(
            run_id=ctx.run_id,
            status="ok" if conclusion and not error else "partial",
            conclusion=conclusion,
            snapshot=snapshot,
            views=views,
            traces=ctx.traces,
            error=error,
            tokens=ctx.tokens_used,
        )

    # ------------------------------------------------------------------ helpers
    def _execute(self, task, ctx: RunContext, done: dict[str, Any]):
        if task.agent == SYNTHESIZE_TASK:
            view_objs = [v for v in done.values() if isinstance(v, AnalystView)]
            return planner().invoke({"views": view_objs}, ctx)

        agent = get_agent(task.agent)
        payload = dict(task.params)
        return agent.invoke(payload, ctx)
