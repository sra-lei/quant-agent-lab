"""Base agent: contract validation + trace recording.

Agents never touch HTTP or the database directly. Everything external comes in
through `RunContext`, which keeps each agent unit-testable in isolation.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel

from app.config import settings
from app.contracts.schemas import MarketSnapshot
from app.core.logging import get_logger
from app.data.base import DataProvider

log = get_logger(__name__)


@dataclass
class RunContext:
    run_id: str
    as_of: date
    provider: DataProvider
    max_tokens: int = field(default_factory=lambda: settings.max_tokens_per_run)
    tokens_used: int = 0
    artifacts: dict[str, Any] = field(default_factory=dict)
    traces: list[dict[str, Any]] = field(default_factory=list)

    def add_trace(self, **kwargs: Any) -> None:
        self.traces.append(kwargs)

    # convenience accessors for cross-agent artifacts
    @property
    def snapshot(self) -> MarketSnapshot | None:
        return self.artifacts.get("snapshot")


class BaseAgent(ABC):
    """All agents share one lifecycle: validate → run → validate → trace."""

    name: str = "base"

    @abstractmethod
    def _run(self, payload: dict[str, Any], ctx: RunContext) -> BaseModel:
        raise NotImplementedError

    def invoke(self, payload: dict[str, Any], ctx: RunContext) -> BaseModel:
        started = time.perf_counter()
        status, error = "ok", None
        try:
            result = self._run(payload, ctx)
            if not isinstance(result, BaseModel):
                raise TypeError(f"{self.name}._run must return a pydantic model")
            return result
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised
            status, error = "error", str(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            ctx.add_trace(
                agent=self.name,
                status=status,
                duration_ms=round(elapsed_ms, 2),
                error=error,
                tokens=0,
            )
            log.info(
                "%s finished status=%s %.1fms", self.name, status, elapsed_ms
            )
