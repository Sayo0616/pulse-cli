"""Mai CLI - Queue commands module.

"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import get_queue_sla, get_status_emoji, get_mai_dir, get_blockers_queue, load_config, save_config, GLOBAL
from .issue_list import list_issues_in_queue


def cmd_queue_check(project_root: Path, queue: Optional[str], overdue: bool, show_all: bool = False, handler: Optional[str] = None):
    from .mai import out, out_json, ensure_mai_structure, GLOBAL, suggest, err
    ensure_mai_structure(project_root)
    queue_sla = get_queue_sla(project_root)
    status_emoji = get_status_emoji(project_root)

    if queue:
        if queue not in queue_sla:
            hint = suggest(queue, list(queue_sla.keys()), "mai queue check")
            err(f"Unknown queue: {queue}.", 1, error="INVALID_QUEUE", hint=hint)
        queues = [queue]
    else:
        queues = list(queue_sla.keys())

    results = {}
    if handler and handler.startswith("@"):
        handler = handler[1:]

    for q in queues:
        issues = list_issues_in_queue(project_root, q, overdue_only=overdue)
        
        # REQ-2: Hide COMPLETED by default
        if not show_all:
            issues = [iss for iss in issues if iss["status"].upper() not in ("COMPLETED", "DONE")]
        
        # REQ-4: Filter by handler
        if handler:
            issues = [iss for iss in issues if iss.get("owner") == handler]

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
            if not data["issues"]:
                out("  (empty)")
            for iss in data["issues"]:
                emoji = status_emoji.get(iss["status"].lower(), "")
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


def cmd_queue_create(project_root: Path, queue_name: str, owner: str, sla_hours: Optional[float] = None):
    """REQ-013 & REQ-014: Create a new queue."""
    from .mai import out, err, ensure_mai_structure
    config = load_config(project_root)
    queues = config.get("queues", {})
    
    if queue_name in queues:
        err(f"Queue '{queue_name}' already exists.", 1, error="ALREADY_EXISTS")

    queues[queue_name] = {
        "handler": owner,
        "sla_minutes": int(sla_hours * 60) if sla_hours is not None else None,
        "id_prefix": "REQ" # Default prefix
    }
    config["queues"] = queues

    if GLOBAL.dry_run:
        out(f"[dry-run] Would create queue '{queue_name}' (Owner: {owner})", command="queue create")
        return

    save_config(project_root, config)
    ensure_mai_structure(project_root)
    out(f"Queue '{queue_name}' created successfully.", command="queue create", queue=queue_name, owner=owner)
