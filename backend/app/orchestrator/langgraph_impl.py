"""LangGraph 编排实现（可选依赖）。

为什么保留这个文件：
    用状态图表达任务流，能拿到 checkpoint、可视化、条件分支这些能力，
    也是这个项目刻意保留的"学习面"。

为什么它必须可以缺席：
    LangGraph 会带来 langchain-core 等一串依赖。没装时应当**静默降级**到
    SimpleOrchestrator，而不是让整个服务起不来——开源用户 clone 下来第一
    次运行不该被依赖问题卡住。

当前状态：v0.1 骨架。节点按拓扑序串行执行，与 Simple 实现共享同一套
Agent 与契约，因此两者的输出可以直接对照。
"""

from __future__ import annotations

from typing import Any, TypedDict

from app.agents.base import RunContext
from app.agents.registry import SYNTHESIZE_TASK, get_agent, planner, registered_agents
from app.contracts.schemas import AnalystView, MarketSnapshot, ResearchConclusion, TaskPlan
from app.core.logging import get_logger
from app.orchestrator.base import RunResult, validate_plan
from app.orchestrator.simple import SimpleOrchestrator

log = get_logger(__name__)

try:  # optional dependency
    from langgraph.graph import END, StateGraph  # type: ignore

    _LANGGRAPH_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import problem means "not available"
    StateGraph = None  # type: ignore[assignment]
    END = None  # type: ignore[assignment]
    _LANGGRAPH_AVAILABLE = False


class _GraphState(TypedDict, total=False):
    snapshot: MarketSnapshot | None
    views: list[AnalystView]
    conclusion: ResearchConclusion | None
    error: str | None


def _topological_order(plan: TaskPlan) -> list[str]:
    remaining = {t.task_id: set(t.depends_on) for t in plan.tasks}
    order: list[str] = []
    while remaining:
        ready = [tid for tid, deps in remaining.items() if not deps]
        if not ready:
            raise ValueError("dependency cycle in plan")
        for tid in sorted(ready):
            order.append(tid)
            remaining.pop(tid)
        for deps in remaining.values():
            deps.difference_update(ready)
    return order


class LangGraphOrchestrator:
    name = "langgraph"

    def run(self, plan: TaskPlan, ctx: RunContext) -> RunResult:
        if not _LANGGRAPH_AVAILABLE:
            log.warning(
                "langgraph 未安装，自动降级为 SimpleOrchestrator。"
                "安装：pip install -e '.[langgraph]'"
            )
            return SimpleOrchestrator().run(plan, ctx)

        validate_plan(plan, set(registered_agents()), SYNTHESIZE_TASK)
        tasks = {t.task_id: t for t in plan.tasks}
        order = _topological_order(plan)

        builder = StateGraph(_GraphState)

        def make_node(task_id: str):
            def _node(state: _GraphState) -> _GraphState:
                task = tasks[task_id]
                if task.agent == SYNTHESIZE_TASK:
                    out = planner().invoke({"views": state.get("views", [])}, ctx)
                    return {"conclusion": out}
                out = get_agent(task.agent).invoke(dict(task.params), ctx)
                if isinstance(out, MarketSnapshot):
                    return {"snapshot": out}
                if isinstance(out, AnalystView):
                    return {"views": list(state.get("views", [])) + [out]}
                return {}

            return _node

        for task_id in order:
            builder.add_node(task_id, make_node(task_id))

        for task_id in order:
            deps = tasks[task_id].depends_on
            if not deps:
                builder.set_entry_point(task_id)
                continue
            for dep in deps:
                builder.add_edge(dep, task_id)

        for task_id in order:
            if not any(task_id in t.depends_on for t in plan.tasks):
                builder.add_edge(task_id, END)

        graph = builder.compile()
        final_state: dict[str, Any] = graph.invoke({"views": [], "snapshot": None})

        conclusion = final_state.get("conclusion")
        return RunResult(
            run_id=ctx.run_id,
            status="ok" if conclusion else "partial",
            conclusion=conclusion,
            snapshot=final_state.get("snapshot"),
            views=final_state.get("views", []),
            traces=ctx.traces,
            error=None if conclusion else "synthesis did not produce a conclusion",
            tokens=ctx.tokens_used,
        )
