"""Mai CLI - Queue commands module.

v1.1.0
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import get_queue_sla, get_status_emoji, get_mai_dir, get_blockers_queue
from .issue_list import list_issues_in_queue


def cmd_queue_check(project_root: Path, queue: Optional[str], overdue: bool):
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
        issues = list_issues_in_queue(project_root, q, overdue_only=overdue)
        sla_owner, sla_hours = queue_sla.get(q, ("unknown", None))
        results[q] = {
            "sla_owner": sla_owner,
            "sla_hours": sla_hours,
            "total": len(issues),
            "issues": [
                {"id": iss["id"], "title": iss["title"], "status": iss["status"],
                 "created": iss.get("created", ""), "owner": iss.get("owner", "")}
                for iss in issues
            ]
        }

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "queue check", "overdue_only": overdue, "queues": results})
    else:
        for q, data in results.items():
            sla_str = f"{data['sla_hours']}h" if data["sla_hours"] else "no SLA"
            out(f"\n## Queue: {q} (SLA: {data['sla_owner']}/{sla_str}) - {data['total']} issues")
            for iss in data["issues"]:
                emoji = status_emoji.get(iss["status"], "")
                out(f"  [{iss['id']}] {emoji} {iss['title']} "
                    f"(owner: {iss['owner']}, created: {iss['created']})")


def cmd_queue_blockers(project_root: Path):
    from .mai import out, err, out_json, ensure_mai_structure, GLOBAL
    ensure_mai_structure(project_root)
    
    q = get_blockers_queue(project_root)
    queue_sla = get_queue_sla(project_root)
    if q not in queue_sla:
        err(f"Blocker queue '{q}' not configured in config.json", 1, error="INVALID_CONFIG")

    blockers = list_issues_in_queue(project_root, q)
    status_emoji = get_status_emoji(project_root)

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "queue blockers", "blockers": blockers})
    else:
        out(f"\n## {q.replace('-', ' ').title()} ({len(blockers)} issues)")
        for iss in blockers:
            emoji = status_emoji.get(iss["status"], "")
            out(f"  [{iss['id']}] {emoji} {iss['title']}")
        if not blockers:
            out("  (no blockers)")
