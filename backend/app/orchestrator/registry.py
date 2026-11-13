"""Orchestrator factory."""

from __future__ import annotations

from app.config import settings
from app.orchestrator.base import Orchestrator
from app.orchestrator.simple import SimpleOrchestrator


def get_orchestrator(name: str | None = None) -> Orchestrator:
    key = (name or settings.orchestrator or "simple").lower()
    if key == "simple":
        return SimpleOrchestrator()
    if key == "langgraph":
        from app.orchestrator.langgraph_impl import LangGraphOrchestrator

        return LangGraphOrchestrator()
    raise ValueError(f"unknown orchestrator: {key!r} (expected simple|langgraph)")
