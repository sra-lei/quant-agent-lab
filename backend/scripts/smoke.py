#!/usr/bin/env python3
"""端到端冒烟：不依赖 pytest、不联网、不花钱，验证五个 Agent 能跑完整条链路。

用法：
    cd backend && python scripts/smoke.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import RunContext  # noqa: E402
from app.agents.planner import PlannerAgent  # noqa: E402
from app.contracts.schemas import RunRequest  # noqa: E402
from app.data.mock import MockProvider  # noqa: E402
from app.orchestrator.simple import SimpleOrchestrator  # noqa: E402


def main() -> int:
    request = RunRequest(
        goal="冒烟：跑通五 Agent 链路",
        universe=["600519", "000858", "300750"],
        capital=100_000,
        risk="medium",
    )
    run_id = "run_smoke_001"
    plan = PlannerAgent().plan(request, run_id)
    ctx = RunContext(run_id=run_id, as_of=date.today(), provider=MockProvider())

    print(f"[plan] {len(plan.tasks)} tasks: " + ", ".join(f"{t.task_id}:{t.agent}" for t in plan.tasks))

    result = SimpleOrchestrator().run(plan, ctx)

    print(f"[run]  status={result.status} tokens={result.tokens}")
    print(f"[snap] source={result.snapshot.source if result.snapshot else None} "
          f"universe={len(result.snapshot.universe) if result.snapshot else 0}")
    for view in result.views:
        top = view.candidates[0] if view.candidates else None
        print(f"[view] {view.agent}: {len(view.candidates)} candidates, "
              f"top={top.code + ' ' + top.stance.value + ' ' + str(top.conviction) if top else 'none'}")

    concl = result.conclusion
    if concl is None:
        print("[FAIL] no conclusion produced")
        return 1

    print(f"[concl] {concl.summary}")
    print(f"[concl] picks={len(concl.picks)} disagreements={len(concl.disagreements)}")
    for pick in concl.picks[:3]:
        print(f"        - {pick.code} {pick.stance.value} {pick.conviction:.2f} sources={pick.sources}")
    for d in concl.disagreements:
        print(f"        ! {d.code} 分歧: {d.summary}")

    print("[traces]", [(t["agent"], t["status"]) for t in result.traces])
    print("\n✅ smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
