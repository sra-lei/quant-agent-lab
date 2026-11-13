"""契约测试：这些断言就是"接口不能随便改"的执行版本。

跑法：pytest -q      （或 python scripts/smoke.py 做端到端冒烟）
"""

from __future__ import annotations

from datetime import date

import pytest

from app.agents.base import RunContext
from app.agents.planner import PlannerAgent
from app.agents.registry import registered_agents
from app.contracts.schemas import (
    AnalystView,
    Candidate,
    ResearchConclusion,
    RunRequest,
    Stance,
)
from app.data.mock import MockProvider
from app.orchestrator.base import PlanError, validate_plan
from app.orchestrator.simple import SimpleOrchestrator


def _ctx(run_id: str = "run_test_001") -> RunContext:
    return RunContext(run_id=run_id, as_of=date(2026, 11, 13), provider=MockProvider())


def test_plan_is_valid_dag():
    plan = PlannerAgent().plan(RunRequest(goal="测试", universe=["600519"]), "run_test_001")
    validate_plan(plan, set(registered_agents()), "planner_synthesize")
    assert [t.task_id for t in plan.tasks] == ["t1", "t2", "t3", "t4"]


def test_plan_rejects_unknown_agent():
    plan = PlannerAgent().plan(RunRequest(goal="测试", universe=["600519"]), "run_x")
    plan.tasks[0].agent = "nonexistent_agent"
    with pytest.raises(PlanError):
        validate_plan(plan, set(registered_agents()), "planner_synthesize")


def test_disagreement_is_never_averaged():
    """方向相反时必须进 disagreements，不能合并成一个中间值。"""
    planner = PlannerAgent()
    ctx = _ctx()
    # 手工构造两个方向相反的 view
    from app.agents.collector import CollectorAgent

    snap = CollectorAgent().invoke({"codes": ["600519"]}, ctx)
    long_view = AnalystView(
        view_id="v1", agent="value_analyst", snapshot_id=snap.snapshot_id, as_of=ctx.as_of,
        candidates=[Candidate(code="600519", stance=Stance.LONG, conviction=0.8, rationale="便宜")],
    )
    avoid_view = AnalystView(
        view_id="v2", agent="momentum_analyst", snapshot_id=snap.snapshot_id, as_of=ctx.as_of,
        candidates=[Candidate(code="600519", stance=Stance.AVOID, conviction=0.6, rationale="资金流出")],
    )

    conclusion: ResearchConclusion = planner.invoke({"views": [long_view, avoid_view]}, ctx)

    assert len(conclusion.disagreements) == 1
    assert conclusion.disagreements[0].code == "600519"
    assert conclusion.picks == [], "冲突标的不应出现在 picks 里"


def test_end_to_end_simple_orchestrator():
    request = RunRequest(goal="跑通链路", universe=["600519", "000858"])
    plan = PlannerAgent().plan(request, "run_e2e_001")
    ctx = _ctx("run_e2e_001")

    result = SimpleOrchestrator().run(plan, ctx)

    assert result.status == "ok"
    assert result.snapshot is not None
    assert result.snapshot.source == "mock"
    assert len(result.views) == 2
    assert result.conclusion is not None
    assert result.conclusion.disclaimer


def test_snapshot_marks_quality_instead_of_filling_zeros():
    from app.agents.collector import CollectorAgent

    ctx = _ctx()
    snap = CollectorAgent().invoke({"codes": ["600519"]}, ctx)
    # mock 提供全部数据，缺失列表应为空；关键是不允许出现"缺失但填了 0"
    for code, series in snap.bars.items():
        assert series, f"{code} 有 key 就必须有数据"
        for bar in series:
            assert bar.close > 0
