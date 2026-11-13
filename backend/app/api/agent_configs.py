"""智能体编辑器 API：配置的增删改查与试运行。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.config_agent import run_config_agent
from app.agents.tools import DEFAULT_OUTPUT_SCHEMA, OUTPUT_FORMATS, all_tools, validate_tools
from app.db.models import AgentConfigRow
from app.db.session import session_scope

router = APIRouter(prefix="/api/agents")

_FORMAT_TYPES = {"json_schema", "markdown_table", "text"}


# --------------------------------------------------------------------- schemas
class WorkflowStep(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    instruction: str = ""


class OutputFormat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["json_schema", "markdown_table", "text"] = "text"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")


class AgentConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = ""
    workflow: list[WorkflowStep] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    output_format: OutputFormat = Field(default_factory=OutputFormat)
    enabled: bool = True

    @field_validator("tools")
    @classmethod
    def _known_tools(cls, value: list[str]) -> list[str]:
        unknown = validate_tools(value)
        if unknown:
            raise ValueError(f"未知工具：{', '.join(unknown)}")
        return value

    @field_validator("output_format")
    @classmethod
    def _schema_required(cls, value: OutputFormat) -> OutputFormat:
        if value.type == "json_schema" and not value.schema_:
            raise ValueError("输出格式为 json_schema 时必须提供 schema")
        return value


class RunAgentIn(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------- helpers
def _row_to_dict(row: AgentConfigRow) -> dict[str, Any]:
    return {
        "agent_id": row.agent_id,
        "name": row.name,
        "role": row.role,
        "workflow": row.workflow or [],
        "tools": row.tools or [],
        "output_format": row.output_format or {"type": "text"},
        "enabled": row.enabled,
        "builtin": row.builtin,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _new_agent_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug or not slug.isascii():
        slug = "custom"
    return f"{slug[:24]}_{uuid.uuid4().hex[:6]}"


# ------------------------------------------------------------------------ meta
@router.get("/meta")
def agent_meta() -> dict[str, Any]:
    return {
        "tools": all_tools(),
        "output_formats": OUTPUT_FORMATS,
        "default_schema": DEFAULT_OUTPUT_SCHEMA,
    }


# ------------------------------------------------------------------------- crud
@router.get("")
def list_agents() -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.query(AgentConfigRow).order_by(AgentConfigRow.builtin.desc(), AgentConfigRow.name).all()
        return [_row_to_dict(r) for r in rows]


@router.get("/{agent_id}")
def get_agent(agent_id: str) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return _row_to_dict(row)


@router.post("", status_code=201)
def create_agent(body: AgentConfigIn) -> dict[str, Any]:
    with session_scope() as db:
        row = AgentConfigRow(
            agent_id=_new_agent_id(body.name),
            name=body.name,
            role=body.role,
            workflow=[s.model_dump() for s in body.workflow],
            tools=body.tools,
            output_format=body.output_format.model_dump(by_alias=True),
            enabled=body.enabled,
            builtin=False,
        )
        db.add(row)
        db.flush()
        return _row_to_dict(row)


@router.put("/{agent_id}")
def update_agent(agent_id: str, body: AgentConfigIn) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")

        row.name = body.name
        row.role = body.role
        row.workflow = [s.model_dump() for s in body.workflow]
        row.tools = body.tools
        row.output_format = body.output_format.model_dump(by_alias=True)
        row.enabled = body.enabled
        row.updated_at = datetime.now()
        db.flush()
        return _row_to_dict(row)


@router.delete("/{agent_id}")
def delete_agent(agent_id: str) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")
        if row.builtin:
            raise HTTPException(status_code=400, detail="内置智能体不可删除，可以停用或修改")
        db.delete(row)
        return {"deleted": agent_id}


# --------------------------------------------------------------------- dry run
@router.post("/{agent_id}/run")
def run_agent(agent_id: str, body: RunAgentIn) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")
        config = _row_to_dict(row)

    try:
        return run_config_agent(config, body.input)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"试运行失败：{exc}") from exc
