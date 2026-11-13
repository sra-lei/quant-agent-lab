"""Service layer: run a research job end-to-end and persist the results."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from app.agents.base import RunContext
from app.agents.registry import planner
from app.config import settings
from app.contracts.schemas import RunRequest
from app.core.logging import get_logger
from app.data.registry import get_provider
from app.db.models import AgentTrace, ConclusionRow, Run, SnapshotRow, ViewRow
from app.db.session import session_scope
from app.orchestrator.base import RunResult
from app.orchestrator.registry import get_orchestrator

log = get_logger(__name__)


def default_universe(limit: int = 5) -> list[str]:
    """Demo universe. In production this comes from a strategy or an index."""
    base = ["600519", "000858", "300750", "601318", "000001"]
    return base[:limit]


def execute_run(request: RunRequest) -> RunResult:
    run_id = f"run_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    as_of = date.today()
    provider = get_provider()

    codes = request.universe or default_universe()
    if not codes:
        raise ValueError("universe is empty and no default is available")

    plan = planner().plan(request.model_copy(update={"universe": codes}), run_id)

    ctx = RunContext(run_id=run_id, as_of=as_of, provider=provider)
    orchestrator = get_orchestrator()

    with session_scope() as db:
        db.add(Run(run_id=run_id, goal=request.goal, status="running", orchestrator=orchestrator.name))

    result = orchestrator.run(plan, ctx)

    _persist(run_id, as_of, result)
    return result


def _persist(run_id: str, as_of: date, result: RunResult) -> None:
    with session_scope() as db:
        run = db.get(Run, run_id)
        if run is not None:
            run.status = result.status
            run.cost_tokens = result.tokens
            run.error = result.error
            run.finished_at = datetime.now()

        if result.snapshot is not None:
            snap = result.snapshot
            db.merge(
                SnapshotRow(
                    snapshot_id=snap.snapshot_id,
                    run_id=run_id,
                    as_of=snap.as_of.isoformat(),
                    source=snap.source,
                    payload=snap.model_dump(mode="json"),
                    quality=snap.quality.model_dump(mode="json"),
                )
            )

        for view in result.views:
            db.merge(
                ViewRow(
                    view_id=view.view_id,
                    run_id=run_id,
                    agent=view.agent,
                    snapshot_id=view.snapshot_id,
                    payload=view.model_dump(mode="json"),
                )
            )

        if result.conclusion is not None:
            concl = result.conclusion
            db.merge(
                ConclusionRow(
                    conclusion_id=concl.conclusion_id,
                    run_id=run_id,
                    as_of=concl.as_of.isoformat(),
                    payload=concl.model_dump(mode="json"),
                    disagreements=[d.model_dump(mode="json") for d in concl.disagreements],
                )
            )

        for trace in result.traces:
            db.add(
                AgentTrace(
                    run_id=run_id,
                    agent=str(trace.get("agent", "")),
                    step=str(trace.get("step", "")),
                    status=str(trace.get("status", "ok")),
                    duration_ms=float(trace.get("duration_ms", 0.0)),
                    tokens=int(trace.get("tokens", 0)),
                    error=trace.get("error"),
                )
            )
    log.info("run %s persisted status=%s", run_id, result.status)


def signals(limit: int = 50) -> list[dict[str, Any]]:
    """Flatten persisted conclusions into a signal list for the UI."""
    from app.db.models import ConclusionRow as CR

    out: list[dict[str, Any]] = []
    with session_scope() as db:
        rows = db.query(CR).order_by(CR.as_of.desc()).limit(limit).all()
        for row in rows:
            payload = row.payload or {}
            for pick in payload.get("picks", []):
                out.append(
                    {
                        "as_of": row.as_of,
                        "run_id": row.run_id,
                        "code": pick.get("code"),
                        "name": pick.get("name"),
                        "stance": pick.get("stance"),
                        "conviction": pick.get("conviction"),
                        "sources": pick.get("sources", []),
                        "rationale": pick.get("rationale", ""),
                    }
                )
    return out
