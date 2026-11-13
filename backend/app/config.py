"""Runtime configuration.

All settings come from environment variables so the same image can be deployed
to a laptop, a cloud VM, or CI without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw.isdigit() else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- storage -----------------------------------------------------------
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "sqlite:///./quant_agent_lab.db")
    )

    # --- orchestration -----------------------------------------------------
    # "simple" (built-in state machine) or "langgraph" (optional dependency)
    orchestrator: str = field(default_factory=lambda: _env("ORCHESTRATOR", "simple"))

    # --- data providers ----------------------------------------------------
    data_provider: str = field(default_factory=lambda: _env("DATA_PROVIDER", "mock"))
    tdx_mcp_endpoint: str = field(default_factory=lambda: _env("TDX_MCP_ENDPOINT"))
    tdx_mcp_token: str = field(default_factory=lambda: _env("TDX_MCP_TOKEN"))
    wind_mcp_endpoint: str = field(default_factory=lambda: _env("WIND_MCP_ENDPOINT"))
    wind_mcp_token: str = field(default_factory=lambda: _env("WIND_MCP_TOKEN"))

    # --- llm ---------------------------------------------------------------
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "mock"))
    llm_model_cheap: str = field(
        default_factory=lambda: _env("LLM_MODEL_CHEAP", "deepseek-v4-flash")
    )
    llm_model_strong: str = field(
        default_factory=lambda: _env("LLM_MODEL_STRONG", "deepseek-v4-flash")
    )
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_base_url: str = field(
        default_factory=lambda: _env("LLM_BASE_URL", "https://api.deepseek.com/v1")
    )

    # --- guard rails -------------------------------------------------------
    max_tokens_per_run: int = field(default_factory=lambda: _env_int("MAX_TOKENS_PER_RUN", 120_000))
    max_universe: int = field(default_factory=lambda: _env_int("MAX_UNIVERSE", 50))
    demo_mode: bool = field(default_factory=lambda: _env_bool("DEMO_MODE", True))

    # --- misc --------------------------------------------------------------
    api_cors_origins: str = field(default_factory=lambda: _env("API_CORS_ORIGINS", "*"))

    @property
    def cors_origins(self) -> list[str]:
        raw = self.api_cors_origins
        return ["*"] if raw.strip() == "*" else [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
