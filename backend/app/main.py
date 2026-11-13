"""FastAPI entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.versions import ensure_versions
from app.api.agent_configs import router as agent_configs_router
from app.api.reports import router as reports_router
from app.api.routes import router
from app.config import settings
from app.core.logging import get_logger
from app.db.seed import seed_builtin_agents
from app.db.session import init_db, session_scope

log = get_logger(__name__)

#: 设置该环境变量时，同一进程顺带托管前端构建产物（单端口部署）
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", "").strip()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with session_scope() as db:
        seed_builtin_agents(db)
        ensure_versions(db)
    log.info(
        "quant-agent-lab started orchestrator=%s provider=%s frontend=%s",
        settings.orchestrator,
        settings.data_provider,
        FRONTEND_DIST or "api-only",
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
app.include_router(reports_router)


# --------------------------------------------------------------------- serving
_dist = Path(FRONTEND_DIST).expanduser() if FRONTEND_DIST else None
_has_frontend = bool(_dist and _dist.is_dir() and (_dist / "index.html").is_file())

#: index.html 不能缓存：它引用带 hash 的 bundle，缓存住就永远拿不到新前端
_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

if _has_frontend and (_dist / "assets").is_dir():  # type: ignore[operator]
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")


@app.get("/", include_in_schema=not _has_frontend)
def root():
    if _has_frontend:
        return FileResponse(_dist / "index.html", headers=_NO_CACHE)  # type: ignore[operator]
    return {
        "name": "quant-agent-lab",
        "version": "0.1.0",
        "docs": "/docs",
        "disclaimer": "本系统仅用于研究，不构成投资建议。",
    }


if _has_frontend:

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """前端路由回退：/agents 这类子路由刷新后仍返回 index.html。"""
        candidate = _dist / full_path  # type: ignore[operator]
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html", headers=_NO_CACHE)  # type: ignore[operator]
