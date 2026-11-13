"""FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_configs import router as agent_configs_router
from app.api.routes import router
from app.config import settings
from app.core.logging import get_logger
from app.agents.versions import ensure_versions
from app.db.seed import seed_builtin_agents
from app.db.session import init_db, session_scope

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with session_scope() as db:
        seed_builtin_agents(db)
        ensure_versions(db)
    log.info(
        "quant-agent-lab started orchestrator=%s provider=%s",
        settings.orchestrator,
        settings.data_provider,
    )
    yield


app = FastAPI(
    title="quant-agent-lab",
    version="0.1.0",
    description="多智能体 A 股投研工程 / Multi-agent equity research workbench",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(agent_configs_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "quant-agent-lab",
        "version": "0.1.0",
        "docs": "/docs",
        "disclaimer": "本系统仅用于研究，不构成投资建议。",
    }
