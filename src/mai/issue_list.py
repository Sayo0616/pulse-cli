"""Mai CLI - Issue list / show module.

"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import get_queue_sla, get_status_emoji, get_mai_dir
from .issue import read_issue, parse_issue_file
from .lock import check_lock


def list_issues_in_queue(project_root: Path, queue: str,
                          overdue_only: bool = False) -> List[Dict[str, Any]]:
    """Return all issues in a queue, optionally filtered to overdue only."""
    mai = get_mai_dir(project_root)
    queue_dir = mai / "queues" / queue
    if not queue_dir.exists():
        return []

    issues = []
    queue_sla = get_queue_sla(project_root)
    status_emoji = get_status_emoji(project_root)

    for f in sorted(queue_dir.glob("*.md")):
        data = parse_issue_file(f)
        data["queue"] = queue
        
        # Enrich with Lock & SLA info
        issue_id = data["id"]
        li = check_lock(project_root, issue_id)
        data["lock"] = {
            "held": bool(li),
            "holder": li["holder"] if li else None,
            "stale": li["stale"] if li else False,
            "timestamp": li["timestamp"] if li else None
        }

        data["status_emoji"] = status_emoji.get(data["status"].lower(), "❓")

        deadline_str = data.get("sla_deadline")
        data["sla_expired"] = False
        if deadline_str:
            try:
                dl = datetime.fromisoformat(deadline_str)
                if dl < datetime.now():
                    data["sla_expired"] = True
                    # Append overdue icon if available
                    if "overdue" in status_emoji and data["status"].lower() != "completed":
                        data["status_emoji"] += status_emoji["overdue"]
            except Exception:
                pass
        elif queue in queue_sla:
            # Fallback to computing from created
            _, sla_hours = queue_sla[queue]
            created_str = data.get("created", "")
            if sla_hours is not None and created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str)
                    dl = created_dt + timedelta(hours=sla_hours)
                    data["sla_deadline"] = dl.isoformat()
                    if dl < datetime.now():
                        data["sla_expired"] = True
                        if "overdue" in status_emoji and data["status"].lower() != "completed":
                            data["status_emoji"] += status_emoji["overdue"]
                except Exception:
                    pass

        if overdue_only:
            if data["sla_expired"]:
                issues.append(data)
        else:
            issues.append(data)

    # REQ-1: Sort by priority (P0, P1, P2) then by created time
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    issues.sort(key=lambda x: (priority_order.get(x.get("priority", "P2").upper(), 2), x.get("created", "")))

    return issues


def cmd_issue_list(project_root: Path, queue: Optional[str], handler: Optional[str] = None):
    from .mai import out, out_json, GLOBAL
    from .project import ensure_mai_structure
    ensure_mai_structure(project_root)
    queue_sla = get_queue_sla(project_root)

    if handler and handler.startswith("@"):
        handler = handler[1:]

    if queue:
        queues = [queue]
    else:
        queues = list(queue_sla.keys())

    results = {}
    for q in queues:
        issues = list_issues_in_queue(project_root, q)
        if handler:
            issues = [iss for iss in issues if handler.lower() in iss.get("owner", "").lower()]
        results[q] = issues

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "issue list", "queues": results})
    else:
        for q, issues in results.items():
            sla_info = queue_sla.get(q, ("", None))
            sla_str = f" (SLA: {sla_info[0]}/{sla_info[1]}h)" if sla_info[1] else ""
            out(f"\n## Queue: {q}{sla_str} - {len(issues)} issues")
            if not issues:
                out("  (empty)")
            for iss in issues:
                emoji = iss.get("status_emoji", "❓")
                priority = f"[{iss.get('priority', 'P2')}]"
                lock_icon = "🔄" if iss["lock"]["held"] else "🔓"
                lock_info = f" [{lock_icon} {iss['lock']['holder'] or '(无)'}]"
                expired = " ⚠️已过期" if iss["sla_expired"] else ""
                out(f"  [{iss['id']}] {priority} {emoji} {iss['status']:12} {iss['title']}{lock_info} SLA:{iss['sla_deadline']}{expired}")


def cmd_issue_show(project_root: Path, issue_id: str):
    from .mai import out, out_json, err, GLOBAL
    from .lock import check_lock

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    lock_info = check_lock(project_root, issue_id)

    if GLOBAL.format == "json":
        # Keep creator in JSON for backward compatibility but suggest migration
        out_json({"ok": True, "command": "issue show", "issue": issue, "lock": lock_info})
    else:
        queue = issue.get("queue")
        queue_sla = get_queue_sla(project_root)
        q_owner, _ = queue_sla.get(queue, (None, None))

        out(f"\n=== Issue {issue['id']} ===")
        out(f"Queue:    {queue}")
        out(f"Title:    {issue['title']}")
        out(f"Priority: {issue.get('priority', 'P2')}")
        out(f"Status:   {issue.get('status', '')}")
        out(f"Owner:    {q_owner or ''}")
        out(f"Handler:  {issue.get('owner', '')}")
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
            out("\n## 处理记录")
            for t in issue["timeline"]:
                t_indented = t.replace("\n", "\n  ")
                out(f"  - {t_indented}")
