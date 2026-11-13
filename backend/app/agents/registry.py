"""Agent registry — the single place mapping plan task names to implementations."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.collector import CollectorAgent
from app.agents.momentum_analyst import MomentumAnalystAgent
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.value_analyst import ValueAnalystAgent

_AGENTS: dict[str, BaseAgent] = {
    "collector": CollectorAgent(),
    "value_analyst": ValueAnalystAgent(),
    "momentum_analyst": MomentumAnalystAgent(),
    "planner": PlannerAgent(),
    "reviewer": ReviewerAgent(),
}

#: tasks that are executed by the planner itself rather than a standalone agent
SYNTHESIZE_TASK = "planner_synthesize"


def get_agent(name: str) -> BaseAgent:
    if name not in _AGENTS:
        raise KeyError(f"unknown agent {name!r}; registered: {sorted(_AGENTS)}")
    return _AGENTS[name]


def registered_agents() -> list[str]:
    return sorted(_AGENTS)


def planner() -> PlannerAgent:
    return _AGENTS["planner"]  # type: ignore[return-value]
