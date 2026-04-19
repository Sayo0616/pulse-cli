"""Mai CLI - Escalation generation module.

v1.1.0
"""

from pathlib import Path

from .config import get_heartbeat_intervals
from .issue import read_issue


def cmd_escalation_gen(project_root: Path, issue_id: str):
    """Generate a human-readable escalation report for a stuck issue."""
    from .mai import out, out_json, err, GLOBAL

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    owner = issue.get("owner", "unknown")
    heartbeat = get_heartbeat_intervals(project_root).get(owner, 17)
    threshold = heartbeat * 1.5

    template = f"""# ⚠️ [冲突升级报告] {issue['id']}

**Issue：** {issue['id']}
**队列：** {issue.get('queue', '')}
**标题：** {issue['title']}
**状态：** {issue.get('status', '')}
**Owner：** {owner}
**创建时间：** {issue.get('created', 'unknown')}
**SLA 截止：** {issue.get('sla_deadline', 'unknown')}

## 冲突升级原因

Issue has been in '{issue.get('status', '')}' status without resolution.

Owner agent: {owner}
Heartbeat interval: {heartbeat} minutes
Lock timeout threshold: {threshold:.1f} minutes

## 问题描述

{issue.get('description', issue.get('title', ''))}

## 处理记录

""" + "\n".join(f"- {t}" for t in issue.get("timeline", []))

    template += """

## 建议选项

- [A] <选项描述>
- [B] <选项描述>

**请用户 (Sayo) 裁决：** [A] / [B]
"""

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "escalation gen",
                  "issue": issue, "escalation_template": template})
    else:
        out(template, command="escalation gen")
