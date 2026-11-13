"""配置版本管理。

三条规则：
1. 整份配置进快照（角色 + 工作流 + 工具 + 输出格式 + 启用状态）
2. 内容没变就不建版本——版本列表只记录真实改动
3. 回滚是"写一条新版本"，历史永不覆写
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import AgentConfigRow, AgentConfigVersion

log = get_logger(__name__)

#: 字段 → 中文名，用于前端 diff 展示
FIELD_LABELS = {
    "name": "名称",
    "role": "角色定位",
    "profile": "角色画像",
    "task": "任务描述",
    "workflow": "工作流",
    "tools": "可用工具",
    "output_format": "输出格式",
    "output_spec": "输出规范",
    "enabled": "启用",
}


def snapshot(row: AgentConfigRow) -> dict[str, Any]:
    return {
        "name": row.name,
        "role": row.role or "",
        "profile": row.profile or "",
        "task": row.task or "",
        "workflow": row.workflow or [],
        "tools": row.tools or [],
        "output_format": row.output_format or {"type": "text"},
        "output_spec": row.output_spec or "",
        "enabled": row.enabled,
    }


def _normalize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def next_version(db: Session, agent_id: str) -> int:
    latest = (
        db.query(AgentConfigVersion)
        .filter(AgentConfigVersion.agent_id == agent_id)
        .order_by(desc(AgentConfigVersion.version))
        .first()
    )
    return (latest.version + 1) if latest else 1


def record_version(
    db: Session,
    row: AgentConfigRow,
    note: str = "",
    force: bool = False,
) -> AgentConfigVersion | None:
    """写入一条新版本；与上一版相同且非 force 时跳过。"""
    payload = snapshot(row)
    latest = (
        db.query(AgentConfigVersion)
        .filter(AgentConfigVersion.agent_id == row.agent_id)
        .order_by(desc(AgentConfigVersion.version))
        .first()
    )
    if latest and not force and _normalize(latest.payload) == _normalize(payload):
        return None

    version = AgentConfigVersion(
        agent_id=row.agent_id,
        version=(latest.version + 1) if latest else 1,
        payload=payload,
        note=note[:200],
    )
    db.add(version)
    db.flush()
    log.info("agent %s version %d recorded (%s)", row.agent_id, version.version, note or "edit")
    return version


def list_versions(db: Session, agent_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(AgentConfigVersion)
        .filter(AgentConfigVersion.agent_id == agent_id)
        .order_by(desc(AgentConfigVersion.version))
        .all()
    )
    return [
        {
            "version": r.version,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "payload": r.payload,
        }
        for r in rows
    ]


def get_version(db: Session, agent_id: str, version: int) -> AgentConfigVersion | None:
    return (
        db.query(AgentConfigVersion)
        .filter(
            AgentConfigVersion.agent_id == agent_id,
            AgentConfigVersion.version == version,
        )
        .first()
    )


def diff_payload(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """字段级差异。仅返回发生变化的字段。"""
    out: list[dict[str, Any]] = []
    for field, label in FIELD_LABELS.items():
        old = before.get(field)
        new = after.get(field)
        if _normalize({"v": old}) == _normalize({"v": new}):
            continue
        out.append({"field": field, "label": label, "before": old, "after": new})
    return out


def restore_version(db: Session, row: AgentConfigRow, version: AgentConfigVersion) -> AgentConfigRow:
    payload = version.payload or {}
    row.name = payload.get("name", row.name)
    row.role = payload.get("role", "")
    row.profile = payload.get("profile", "")
    row.task = payload.get("task", "")
    row.workflow = payload.get("workflow", [])
    row.tools = payload.get("tools", [])
    row.output_format = payload.get("output_format", {"type": "text"})
    row.output_spec = payload.get("output_spec", "")
    row.enabled = bool(payload.get("enabled", True))
    db.flush()
    return row


def ensure_versions(db: Session) -> int:
    """给还没有任何版本记录的 Agent 补一个初始版本（v1）。"""
    created = 0
    rows = db.query(AgentConfigRow).all()
    for row in rows:
        exists = (
            db.query(AgentConfigVersion)
            .filter(AgentConfigVersion.agent_id == row.agent_id)
            .first()
        )
        if exists:
            continue
        record_version(db, row, note="初始版本", force=True)
        created += 1
    if created:
        db.commit()
        log.info("bootstrapped versions for %d agents", created)
    return created
