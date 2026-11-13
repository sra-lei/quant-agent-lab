"""HTTP API.

Thin layer on purpose: validate, call the service, return the contract model.
No business logic lives here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.registry import registered_agents
from app.config import settings
from app.contracts.schemas import RunRequest
from app.data.registry import available_providers, get_provider
from app.db.models import ConclusionRow, ReviewRow, Run, Strategy
from app.db.session import session_scope
from app.services import execute_run, signals

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------- health
@router.get("/health")
def health() -> dict[str, Any]:
    provider = get_provider()
    try:
        ph = provider.health()
        provider_ok, detail = ph.ok, ph.detail
    except Exception as exc:  # noqa: BLE001
        provider_ok, detail = False, str(exc)

    return {
        "status": "ok" if provider_ok else "degraded",
        "orchestrator": settings.orchestrator,
        "provider": {"name": provider.name, "ok": provider_ok, "detail": detail},
        "available_providers": available_providers(),
        "agents": registered_agents(),
        "demo_mode": settings.demo_mode,
    }


# ----------------------------------------------------------------------- runs
@router.post("/runs")
def create_run(request: RunRequest) -> dict[str, Any]:
    try:
        result = execute_run(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "run_id": result.run_id,
        "status": result.status,
        "error": result.error,
        "conclusion": result.conclusion.model_dump(mode="json") if result.conclusion else None,
        "views": [v.model_dump(mode="json") for v in result.views],
        "traces": result.traces,
        "snapshot_source": result.snapshot.source if result.snapshot else None,
        "snapshot_quality": (
            result.snapshot.quality.model_dump(mode="json") if result.snapshot else None
        ),
    }


@router.get("/runs")
def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.query(Run).order_by(Run.started_at.desc()).limit(limit).all()
        return [
            {
                "run_id": r.run_id,
                "goal": r.goal,
                "status": r.status,
                "orchestrator": r.orchestrator,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error": r.error,
            }
            for r in rows
        ]


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    with session_scope() as db:
        run = db.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        concl = (
            db.query(ConclusionRow)
            .filter(ConclusionRow.run_id == run_id)
            .order_by(ConclusionRow.conclusion_id.desc())
            .first()
        )
        return {
            "run_id": run.run_id,
            "goal": run.goal,
            "status": run.status,
            "error": run.error,
            "conclusion": concl.payload if concl else None,
        }


# -------------------------------------------------------------------- signals
@router.get("/signals")
def list_signals(limit: int = 100) -> list[dict[str, Any]]:
    return signals(limit=limit)


# ----------------------------------------------------------------- strategies
class StrategyIn(BaseModel):
    name: str
    kind: str = "value"
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


@router.get("/strategies")
def list_strategies() -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.query(Strategy).order_by(Strategy.strategy_id.desc()).all()
        return [
            {
                "strategy_id": s.strategy_id,
                "name": s.name,
                "kind": s.kind,
                "params": s.params,
                "enabled": s.enabled,
            }
            for s in rows
        ]


@router.post("/strategies")
def create_strategy(body: StrategyIn) -> dict[str, Any]:
    with session_scope() as db:
        row = Strategy(name=body.name, kind=body.kind, params=body.params, enabled=body.enabled)
        db.add(row)
        db.flush()
        return {"strategy_id": row.strategy_id, "name": row.name}


@router.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: int, body: StrategyIn) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(Strategy, strategy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="strategy not found")
        row.name, row.kind, row.params, row.enabled = body.name, body.kind, body.params, body.enabled
        return {"strategy_id": row.strategy_id, "updated": True}


@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(Strategy, strategy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="strategy not found")
        db.delete(row)
        return {"deleted": strategy_id}


# -------------------------------------------------------------------- reviews
@router.get("/reviews")
def list_reviews(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.query(ReviewRow).order_by(ReviewRow.as_of.desc()).limit(limit).all()
        return [r.payload for r in rows]


@router.get("/meta")
def meta() -> dict[str, Any]:
    return {
        "today": date.today().isoformat(),
        "agents": registered_agents(),
        "providers": available_providers(),
        "orchestrators": ["simple", "langgraph"],
    }
