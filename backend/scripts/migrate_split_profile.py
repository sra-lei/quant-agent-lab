"""把旧的「一段式角色描述」拆成 role / profile / output_spec 三个字段。

只处理 role 里含 `Profile：` 或 `Output Format` 标记、且 profile 还为空的行，
重复执行安全（已经拆过的不再动）。

用法：cd backend && python scripts/migrate_split_profile.py [--dry-run]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import AgentConfigRow  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402

PROFILE_RE = re.compile(r"^[ \t]*Profile[：:][ \t]*$|^[ \t]*Profile[ \t]*$", re.MULTILINE)
OUTPUT_RE = re.compile(r"^[ \t]*Output[ \t]*Format[ \t]*[：:]?[ \t]*$", re.MULTILINE)


def split_role(text: str) -> tuple[str, str, str]:
    """返回 (role, profile, output_spec)。找不到标记就原样返回 role。"""
    body = (text or "").strip()
    if not body:
        return "", "", ""

    profile = ""
    output_spec = ""

    match_out = OUTPUT_RE.search(body)
    if match_out:
        output_spec = body[match_out.end() :].strip()
        body = body[: match_out.start()].strip()

    match_prof = PROFILE_RE.search(body)
    if match_prof:
        profile = body[match_prof.end() :].strip()
        body = body[: match_prof.start()].strip()

    return body.strip(), profile, output_spec


def main() -> None:
    dry = "--dry-run" in sys.argv
    init_db()

    changed = 0
    with session_scope() as db:
        rows = db.query(AgentConfigRow).all()
        for row in rows:
            if (row.profile or "").strip():
                continue
            if "Profile" not in (row.role or "") and "Output Format" not in (row.role or ""):
                continue

            role, profile, output_spec = split_role(row.role or "")
            print(f"--- {row.agent_id} ({row.name})")
            print(f"    role        : {len(role)} 字符 | {role[:40]}")
            print(f"    profile     : {len(profile)} 字符")
            print(f"    output_spec : {len(output_spec)} 字符")
            if not dry:
                row.role = role
                row.profile = profile
                row.output_spec = output_spec
            changed += 1

    print(f"\n{'[dry-run] ' if dry else ''}共处理 {changed} 个智能体")


if __name__ == "__main__":
    main()
