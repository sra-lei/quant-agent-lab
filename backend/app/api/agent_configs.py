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
from app.agents import versions as versioning
from app.api.reports import save_report
from app.db.models import AgentConfigRow
from app.db.session import session_scope

router = APIRouter(prefix="/api/agents")

_FORMAT_TYPES = {"json_schema", "markdown_table", "text"}


# --------------------------------------------------------------------- schemas
class WorkflowStep(BaseModel):
    #: 步骤序号由系统维护（新增/删除后自动重排），这里只是兼容旧数据与内置 Agent 的语义化命名
    name: str = Field(default="", max_length=80)
    instruction: str = ""


class OutputFormat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["json_schema", "markdown_table", "text"] = "text"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")


class AgentConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=2000)
    #: None = 客户端没传这个字段（老版本前端），此时保留库里原值，不能被默认空串覆盖
    profile: str | None = Field(default=None, max_length=4000)
    workflow: list[WorkflowStep] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    output_format: OutputFormat = Field(default_factory=OutputFormat)
    output_spec: str | None = Field(default=None, max_length=8000)
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
        "profile": row.profile or "",
        "workflow": row.workflow or [],
        "tools": row.tools or [],
        "output_format": row.output_format or {"type": "text"},
        "output_spec": row.output_spec or "",
        "enabled": row.enabled,
        "builtin": row.builtin,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _steps(items: list[WorkflowStep]) -> list[dict[str, Any]]:
    """步骤名留空时由后端补序号，保证排序永远从 1 开始且不重名。"""
    return [
        {"name": s.name.strip() or f"第 {i + 1} 步", "instruction": s.instruction}
        for i, s in enumerate(items)
    ]


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
            profile=body.profile or "",
            workflow=_steps(body.workflow),
            tools=body.tools,
            output_format=body.output_format.model_dump(by_alias=True),
            output_spec=body.output_spec or "",
            enabled=body.enabled,
            builtin=False,
        )
        db.add(row)
        db.flush()
        versioning.record_version(db, row, note="创建", force=True)
        return _row_to_dict(row)


@router.put("/{agent_id}")
def update_agent(agent_id: str, body: AgentConfigIn) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")

        row.name = body.name
        row.role = body.role
        # 未传就沿用旧值：老客户端/局部更新不该把画像和输出规范清空
        if body.profile is not None:
            row.profile = body.profile
        row.workflow = _steps(body.workflow)
        row.tools = body.tools
        row.output_format = body.output_format.model_dump(by_alias=True)
        if body.output_spec is not None:
            row.output_spec = body.output_spec
        row.enabled = body.enabled
        row.updated_at = datetime.now()
        db.flush()
        versioning.record_version(db, row, note="编辑")
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
        result = run_config_agent(config, body.input)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"试运行失败：{exc}") from exc

    # 有产出就留档，前端「报告」页可以直接在线查看
    if result.get("output") and not result.get("error"):
        with session_scope() as db:
            report = save_report(
                db,
                agent_id=agent_id,
                agent_name=config.get("name") or agent_id,
                output=result.get("output"),
                input_payload=body.input,
                tool_calls=result.get("tool_calls") or [],
                tokens=int(result.get("tokens") or 0),
                rounds=int(result.get("rounds") or 0),
                mock=bool(result.get("mock")),
            )
            if report is not None:
                result["report_id"] = report.report_id

    return result


# -------------------------------------------------------------------- versions
@router.get("/{agent_id}/versions")
def list_versions(agent_id: str) -> list[dict[str, Any]]:
    with session_scope() as db:
        if db.get(AgentConfigRow, agent_id) is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return versioning.list_versions(db, agent_id)


@router.get("/{agent_id}/versions/{version}")
def get_version(agent_id: str, version: int) -> dict[str, Any]:
    with session_scope() as db:
        row = versioning.get_version(db, agent_id, version)
        if row is None:
            raise HTTPException(status_code=404, detail="version not found")
        return {
            "version": row.version,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "payload": row.payload,
        }


@router.get("/{agent_id}/versions/{version}/diff")
def diff_version(agent_id: str, version: int, against: int | None = None) -> dict[str, Any]:
    """默认与该版本的"当前配置"对比；传 against=N 则与另一个版本对比。"""
    with session_scope() as db:
        target = versioning.get_version(db, agent_id, version)
        if target is None:
            raise HTTPException(status_code=404, detail="version not found")

        if against is None:
            row = db.get(AgentConfigRow, agent_id)
            if row is None:
                raise HTTPException(status_code=404, detail="agent not found")
            after = versioning.snapshot(row)
            after_label = "当前配置"
        else:
            other = versioning.get_version(db, agent_id, against)
            if other is None:
                raise HTTPException(status_code=404, detail=f"version {against} not found")
            after = other.payload
            after_label = f"v{against}"

        return {
            "before_label": f"v{version}",
            "after_label": after_label,
            "changes": versioning.diff_payload(target.payload, after),
        }


@router.post("/{agent_id}/versions/{version}/restore")
def restore_version(agent_id: str, version: int) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentConfigRow, agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")
        target = versioning.get_version(db, agent_id, version)
        if target is None:
            raise HTTPException(status_code=404, detail="version not found")

        versioning.restore_version(db, row, target)
        row.updated_at = datetime.now()
        db.flush()
        new_version = versioning.record_version(db, row, note=f"回滚至 v{version}", force=True)

        result = _row_to_dict(row)
        result["restored_from"] = version
        result["new_version"] = new_version.version if new_version else None
        return result
