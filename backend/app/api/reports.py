"""报告在线查看：列表、详情、删除。

报告是智能体运行的产物快照——存下来就不再依赖当时的 LLM 响应，
前端可以随时回看排版好的内容。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AgentReport
from app.db.session import session_scope

router = APIRouter(prefix="/api/reports")

MAX_TITLE = 80


def _new_report_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"rpt_{stamp}_{uuid.uuid4().hex[:8]}"


def build_title(content: str, agent_name: str) -> str:
    """标题取正文第一行有内容的文字，去掉【】和日期括号噪音。"""
    for raw in (content or "").splitlines():
        line = raw.strip().lstrip("#").strip()
        if not line:
            continue
        line = line.strip("【】[]")
        return line[:MAX_TITLE] or agent_name
    return agent_name or "未命名报告"


def save_report(
    db: Session,
    *,
    agent_id: str,
    agent_name: str,
    output: Any,
    input_payload: dict[str, Any],
    tool_calls: list[dict[str, Any]] | None = None,
    tokens: int = 0,
    rounds: int = 0,
    mock: bool = False,
) -> AgentReport | None:
    """把一次运行的产出落库；空输出不落库，避免列表里全是空壳。"""
    if isinstance(output, str):
        content = output.strip()
        fmt = "text"
    elif output is None:
        return None
    else:
        import json

        content = json.dumps(output, ensure_ascii=False, indent=2)
        fmt = "json"

    if not content:
        return None

    row = AgentReport(
        report_id=_new_report_id(),
        agent_id=agent_id,
        agent_name=agent_name,
        title=build_title(content if fmt == "text" else agent_name, agent_name),
        content=content,
        format=fmt,
        input_payload=input_payload or {},
        tool_calls=tool_calls or [],
        tokens=tokens,
        rounds=rounds,
        mock=mock,
    )
    db.add(row)
    db.flush()
    return row


def _to_dict(row: AgentReport, with_content: bool = True) -> dict[str, Any]:
    data = {
        "report_id": row.report_id,
        "agent_id": row.agent_id,
        "agent_name": row.agent_name,
        "title": row.title,
        "format": row.format,
        "tokens": row.tokens,
        "rounds": row.rounds,
        "mock": row.mock,
        "tool_calls": row.tool_calls or [],
        "input": row.input_payload or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "length": len(row.content or ""),
    }
    if with_content:
        data["content"] = row.content
    return data


@router.get("")
def list_reports(agent_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with session_scope() as db:
        query = db.query(AgentReport)
        if agent_id:
            query = query.filter(AgentReport.agent_id == agent_id)
        rows = query.order_by(AgentReport.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [_to_dict(r, with_content=False) for r in rows]


@router.get("/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(AgentReport, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="report not found")
        return _to_dict(row)


@router.delete("/{report_id}")
def delete_report(report_id: str) -> dict[str, str]:
    with session_scope() as db:
        row = db.get(AgentReport, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="report not found")
        db.delete(row)
        return {"deleted": report_id}
