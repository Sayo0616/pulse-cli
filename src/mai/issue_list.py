"""Mai CLI - Issue list / show module.

v1.1.0
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import get_queue_sla, get_status_emoji, get_mai_dir
from .issue import read_issue, parse_issue_file


def list_issues_in_queue(project_root: Path, queue: str,
                          overdue_only: bool = False) -> List[Dict[str, Any]]:
    """Return all issues in a queue, optionally filtered to overdue only."""
    mai = get_mai_dir(project_root)
    queue_dir = mai / "queues" / queue
    if not queue_dir.exists():
        return []

    issues = []
    queue_sla = get_queue_sla(project_root)
    for f in sorted(queue_dir.glob("*.md")):
        data = parse_issue_file(f)
        data["queue"] = queue
        if overdue_only and queue in queue_sla:
            sla_owner, sla_hours = queue_sla[queue]
            if sla_hours is not None:
                created_str = data.get("created", "")
                if created_str:
                    try:
                        created_dt = datetime.fromisoformat(created_str)
                        deadline = created_dt + timedelta(hours=sla_hours)
                        if datetime.now() > deadline:
                            issues.append(data)
                    except Exception:
                        issues.append(data)
                else:
                    issues.append(data)
        else:
            issues.append(data)
    return issues


def cmd_issue_list(project_root: Path, queue: Optional[str]):
    from .mai import out, out_json, ensure_mai_structure, GLOBAL
    ensure_mai_structure(project_root)
    queue_sla = get_queue_sla(project_root)
    status_emoji = get_status_emoji(project_root)

    if queue:
        queues = [queue]
    else:
        queues = list(queue_sla.keys())

    results = {}
    for q in queues:
        issues = list_issues_in_queue(project_root, q)
        results[q] = [
            {"id": iss["id"], "title": iss["title"], "status": iss["status"],
             "owner": iss.get("owner", ""), "created": iss.get("created", "")}
            for iss in issues
        ]

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "issue list", "queues": results})
    else:
        for q, issues in results.items():
            out(f"\n## Queue: {q}")
            if not issues:
                out("  (empty)")
            for iss in issues:
                emoji = status_emoji.get(iss["status"], "")
                out(f"  [{iss['id']}] {emoji} {iss['title']} - owner: {iss['owner']}")


def cmd_issue_show(project_root: Path, issue_id: str):
    from .mai import out, out_json, err, GLOBAL
    from .lock import check_lock

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    lock_info = check_lock(project_root, issue_id)

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "issue show", "issue": issue, "lock": lock_info})
    else:
        out(f"\n=== Issue {issue['id']} ===")
        out(f"Queue:    {issue.get('queue', '')}")
        out(f"Title:    {issue['title']}")
        out(f"Status:   {issue.get('status', '')}")
        out(f"Owner:    {issue.get('owner', '')}")
        out(f"Created:  {issue.get('created', '')}")
        out(f"SLA:      {issue.get('sla_deadline', '')}")
        out(f"Ref:      {issue.get('ref', '')}")
        if lock_info:
            stale_str = " (STALE)" if lock_info["stale"] else ""
            out(f"Lock:     held by {lock_info['holder']} since {lock_info['timestamp']}{stale_str}")
        else:
            out("Lock:     (unlocked)")
        if issue.get("description"):
            out(f"\n## 问题描述\n{issue['description']}")
        if issue.get("context"):
            out(f"\n## 关联上下文\n{issue['context']}")
        if issue.get("timeline"):
            out(f"\n## 处理记录\n" + "\n".join(f"  {t}" for t in issue["timeline"]))
