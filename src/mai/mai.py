"""Mai CLI - Main entry point with argument parsing and dispatch.

"""

import argparse
import json
import sys
import difflib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("mai-cli")
except PackageNotFoundError:
    __version__ = "1.9.2"

from .config import (
    get_mai_dir, get_async_dir, find_project_root,
    load_config, GLOBAL, DAILY_SUMMARY_ORDER,
    get_status_emoji,
)
from .sync import sync_to_async
from .log import write_history, read_history
from .safe_exec import exec_safe_check


# ─────────────────────────────────────────────
# Output & Error Helpers
# ─────────────────────────────────────────────

def out(msg: str = "", **kwargs):
    """Standardized output (HINT: supports dry_run=True prefix)."""
    dry_run = kwargs.pop("dry_run", False)
    prefix = "[dry-run] " if dry_run else ""
    if GLOBAL.format == "json":
        data = {"ok": True, "command": kwargs.pop("command", "unknown"), **kwargs}
        if msg:
            data["message"] = f"{prefix}{msg}"
        data["dry_run"] = dry_run
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if msg:
            print(f"{prefix}{msg}")
        elif dry_run:
            print(f"{prefix}")


def err(msg: str, code: int = 1, error: str = "", hint: str = "", **kwargs):
    if GLOBAL.format == "json":
        data = {
            "ok":       False,
            "error":    error or msg,
            "message":  msg,
            "hint":     hint,
            "exit_code": code,
            "command":  kwargs.pop("command", "unknown"),
            **kwargs
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"ERROR: {msg}", file=sys.stderr)
        if hint:
            print(f"HINT: {hint}", file=sys.stderr)
    sys.exit(code)


def out_json(data: dict):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def suggest(word: str, possibilities: List[str], command_tmpl: Optional[str] = None) -> str:
    """REQ-014: Suggest a close match if available."""
    matches = difflib.get_close_matches(word, possibilities, n=1, cutoff=0.6)
    hint = ""
    if matches:
        hint = f"Did you mean '{matches[0]}'?"
    
    if command_tmpl:
        if hint:
            hint += " "
        hint += f"Run '{command_tmpl}' to see all valid options."
    
    return hint


from .project import ensure_mai_structure

# ─────────────────────────────────────────────
# Argument Parser
# ─────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(prog="mai", description="Agent Collaboration CLI")
    parser.add_argument("-v", "--version", action="version", version=f"mai {__version__}")
    parser.add_argument("--project", dest="project", default=None, help="Project root (default: CWD search)")
    parser.add_argument("--format", dest="format", choices=["json", "text"], default="text")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # ── setup (Global Setup) ──
    setup_sp = sub.add_parser("setup", help="Eagerly setup global .mai-cli configuration")
    setup_sp.add_argument("--root", help="Root agents (comma separated)")

    # ── status (Global view) ──
    p = sub.add_parser("status", help="Show global project status")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed issue list")

    # ── init (shortcut for project init) ──
    init_sp = sub.add_parser("init", help="Initialize project in current directory")
    init_sp.add_argument("-o", "--operator", required=True, help="Operator name (strictly required)")

    # ... rest of issue commands ...

    # ── issue ──
    issue_sp = sub.add_parser("issue", help="Issue commands")
    iss = issue_sp.add_subparsers(dest="issue_cmd", required=True)

    p = iss.add_parser("new", help="Create new issue")
    p.add_argument("queue"); p.add_argument("title")
    p.add_argument("--ref", default=None)
    p.add_argument("--priority", choices=["P0", "P1", "P2"], default="P2", help="Issue priority (default: P2)")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("amend", help="Amend issue")
    p.add_argument("issue_id"); p.add_argument("remark", nargs="?", default="")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("claim", help="Claim issue")
    p.add_argument("issue_id")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("block", help="Block an issue")
    p.add_argument("issue_id"); p.add_argument("reason")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("unblock", help="Unblock an issue")
    p.add_argument("issue_id")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("complete", help="Complete an issue")
    p.add_argument("issue_id"); p.add_argument("conclusion")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("reopen", help="Reopen a completed issue")
    p.add_argument("issue_id"); p.add_argument("reason")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("status", help="Show issue status history")
    p.add_argument("issue_id")

    p = iss.add_parser("list", help="List issues")
    p.add_argument("queue", nargs="?", default=None)
    p.add_argument("--handler", help="Filter by handler (owner)")

    p = iss.add_parser("transfer", help="Transfer issue to another handler")
    p.add_argument("issue_id"); p.add_argument("next_handler")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    # Deprecated/Removed
    p = iss.add_parser("submit-to-creator", help="[REMOVED] Use transfer instead")
    p.add_argument("issue_id")

    p = iss.add_parser("confirm", help="Confirm issue completion (owner only)")
    p.add_argument("issue_id")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("reject", help="Reject and reopen issue (owner only)")
    p.add_argument("issue_id"); p.add_argument("reason")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("show", help="Show issue")
    p.add_argument("issue_id")

    p = iss.add_parser("escalate", help="Escalate issue")
    p.add_argument("issue_id")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    p = iss.add_parser("discard", help="Discard an issue (root/owner only)")
    p.add_argument("issue_id"); p.add_argument("reason")
    p.add_argument("-o", "--operator", help="Operator name (required for write actions)")

    # ── queue ──
    queue_sp = sub.add_parser("queue")
    q = queue_sp.add_subparsers(dest="queue_cmd", required=True)
    p = q.add_parser("check", help="Check queue")
    p.add_argument("queue", nargs="?", default=None)
    p.add_argument("--all", action="store_true", help="Show all issues including COMPLETED")
    p.add_argument("--handler", help="Filter by handler (owner)")
    p.add_argument("--overdue", action="store_true", help="Show only overdue issues")
    q.add_parser("blockers", help="Show designer blockers")
    p = q.add_parser("create", help="Create queue")
    p.add_argument("queue")
    p.add_argument("--owner", required=True, help="Queue owner agent name")
    p.add_argument("--sla", type=int, default=None)

    # ── lock ──
    lock_sp = sub.add_parser("lock")
    lk = lock_sp.add_subparsers(dest="lock_cmd", required=True)
    p = lk.add_parser("check"); p.add_argument("issue_id")
    p = lk.add_parser("release", help="Release lock")
    p.add_argument("issue_id")
    p.add_argument("--force", action="store_true", help="Force release if not owner")
    p.add_argument("--yes", action="store_true", help="Skip confirmation")
    lk.add_parser("guardian")

    # ── log ──
    log_sp = sub.add_parser("log")
    lg = log_sp.add_subparsers(dest="log_cmd", required=True)
    lg.add_parser("undo", help="Undo last log entry")
    p = lg.add_parser("history")
    p.add_argument("--date", dest="date", default=None)
    p.add_argument("--agent", dest="agent", default=None)
    p = lg.add_parser("write")
    p.add_argument("agent"); p.add_argument("type"); p.add_argument("summary")
    p.add_argument("--status", dest="status", default="")

    # ── daily-summary ──
    ds_sp = sub.add_parser("daily-summary")
    ds = ds_sp.add_subparsers(dest="ds_cmd", required=True)
    ds.add_parser("trigger")
    ds.add_parser("status")
    ds.add_parser("reset")
    p = ds.add_parser("read")
    p.add_argument("target", nargs="?", default=".") # <agent> / .
    p.add_argument("--all", dest="read_all", action="store_true")
    p = ds.add_parser("write")
    p.add_argument("agent"); p.add_argument("content", nargs="+", default=[])

    # ── escalation ──
    esc_sp = sub.add_parser("escalation")
    es = esc_sp.add_subparsers(dest="esc_cmd", required=True)
    p = es.add_parser("gen")
    p.add_argument("issue_id")

    # ── exec ──
    exec_sp = sub.add_parser("exec")
    ex = exec_sp.add_subparsers(dest="exec_cmd", required=True)
    p = ex.add_parser("safe-check"); p.add_argument("cmd")

    # ── project ──
    proj_sp = sub.add_parser("project")
    pr = proj_sp.add_subparsers(dest="proj_cmd", required=True)
    p = pr.add_parser("init")
    p.add_argument("name", nargs="?", default=".", help="Project name or path (optional, default '.')")
    p.add_argument("-o", "--operator", required=True, help="Operator name (strictly required)")
    
    p = pr.add_parser("delete", help="Delete a project (root only)")
    p.add_argument("name", help="Project name or path")
    p.add_argument("-o", "--operator", required=True, help="Operator name (strictly required)")

    p = pr.add_parser("list", help="List registered projects")
    p.add_argument("--agent", help="Filter by agent participation")

    # ── agent ──
    agent_sp = sub.add_parser("agent")
    ag = agent_sp.add_subparsers(dest="agent_cmd", required=True)
    ag.add_parser("list", help="List all agents")
    p = ag.add_parser("add", help="Add a new agent")
    p.add_argument("name")
    p.add_argument("--heartbeat-minutes", type=int, default=30)

    return parser

# ─────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────

def cmd_status(project_root: Path, verbose: bool = False):
    """REQ-012: Global status view."""
    from .issue_list import list_issues_in_queue
    from .lock import check_lock
    from .daily_summary import _read_status
    from .config import get_queue_sla, get_status_emoji
    from .permission import get_all_roots

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    roots = get_all_roots(project_root)
    out(f"Project: {project_root}")
    out(f"Roots:   {', '.join(roots)}")
    out(f"Updated: {now}\n")

    # 1. Queues
    out("Queues:")
    queue_sla = get_queue_sla(project_root)
    status_emoji = get_status_emoji(project_root)
    for q in queue_sla:
        issues = list_issues_in_queue(project_root, q)
        counts = {"open": 0, "in_progress": 0, "blocked": 0, "completed": 0, "discarded": 0}
        for iss in issues:
            st = iss.get("status", "open").lower()
            if st in counts:
                counts[st] += 1
            else:
                counts["open"] += 1

        out(f"  {q:15} OPEN: {counts['open']:<3} IN_PROGRESS: {counts['in_progress']:<3} BLOCKED: {counts['blocked']:<3} DISCARDED: {counts['discarded']:<3}")
        if verbose and issues:
            for iss in issues:
                st_icon = status_emoji.get(iss.get("status", "open").lower(), "❓")
                out(f"    {st_icon} {iss['id']:8} {iss.get('title', 'No Title')}")

    # 2. Locks
    out("\nLocks:")
    mai = get_mai_dir(project_root)
    locks_dir = mai / "locks"
    lock_found = False
    if locks_dir.exists():
        for lf in locks_dir.glob("*.lock"):
            info = check_lock(project_root, lf.stem)
            if info:
                stale_str = " (expired)" if info["stale"] else f" expires in {round((info['threshold_seconds']-info['age_seconds'])/60, 1)}m"
                out(f"  {info['issue_id']:8} {info['holder']:12} {stale_str}")
                lock_found = True
    if not lock_found:
        out("  (no active locks)")

    # 3. Daily Summary
    status = _read_status(project_root)
    if status:
        date = status.get("date")
        out(f"\nDaily Summary ({date}):")
        participants = status.get("participants", [])
        agent_status = status.get("status", {})
        for p in participants:
            s = agent_status.get(p, "pending")
            icon = "✓" if s == "written" else "⏳"
            out(f"  {p:12}: {icon} {s}")
        if all(s == "written" for s in agent_status.values()):
            out("  All summaries complete for today!")
    else:
        out("\nDaily Summary: Not triggered today.")


def dispatch(args) -> None:
    from .global_config import get_global_config_path, save_global_config, get_global_config

    # REQ: Global initialization check
    if args.subcommand != "setup":
        if not get_global_config_path().exists():
            err("Global configuration not initialized. Run 'mai setup' first.", 100, error="NOT_GLOBAL_INITIALIZED", hint="Run 'mai setup' to initialize global configuration and set root users.")

    if args.subcommand == "setup":
        if get_global_config_path().exists():
            out("Global configuration already exists.", command="setup")
            return
        
        roots = []
        if args.root:
            roots = [r.strip() for r in args.root.split(",") if r.strip()]
        else:
            try:
                raw_input = input("Please enter the root agents for this machine (comma separated): ")
                roots = [r.strip() for r in raw_input.split(",") if r.strip()]
            except EOFError:
                err("Interactive input not available and --root not provided.", 1, error="SETUP_FAILED")
        
        config = get_global_config()
        config["root"] = roots
        save_global_config(config)
        out("Global configuration initialized successfully.", command="setup")
        return

    # Lazy import to avoid circular dependency at module load time
    from .issue import (
        cmd_issue_new, cmd_issue_amend, cmd_issue_claim,
        cmd_issue_complete, cmd_issue_block, cmd_issue_unblock,
        cmd_issue_reopen, cmd_issue_status,
    )
    from .issue_list import cmd_issue_list, cmd_issue_show
    from .queue import cmd_queue_check, cmd_queue_blockers, cmd_queue_create
    from .lock import cmd_lock_check, cmd_lock_release, cmd_lock_guardian
    from .log import cmd_log_history, cmd_log_write, cmd_log_undo
    from .daily_summary import (
        daily_summary_trigger, daily_summary_write, daily_summary_read,
        daily_summary_status, daily_summary_reset,
    )
    from .escalation import cmd_escalation_gen
    from .safe_exec import exec_safe_check
    from .project import cmd_project_init
    from .agent import cmd_agent_add, cmd_agent_list

    project_root = None
    if args.subcommand == "status":
        project_root = find_project_root(args.project)
        if project_root is None:
             err("Project not found. Run 'mai init'.", 4, error="PROJECT_NOT_FOUND", hint="Run 'mai init' to start a project.")
        cmd_status(project_root, getattr(args, "verbose", False))
        return

    if args.subcommand not in ["project", "init"] or (args.subcommand == "project" and args.proj_cmd not in ["init", "list", "delete"]):
        project_root = find_project_root(args.project)
        if project_root is None:
            err("Project not found. Run 'mai init'.",
                4, error="PROJECT_NOT_FOUND", hint="Run 'mai init' to initialize the current directory.")
        
        mai_cfg = get_mai_dir(project_root) / "config.json"
        if not mai_cfg.exists():
            err(f"Project not initialized. Run 'mai init'.",
                4, error="NOT_INITIALIZED", hint="Run 'mai init' to create configuration.")

    try:
        if args.subcommand == "issue":
            dispatch_issue(args, project_root)
        elif args.subcommand == "queue":
            dispatch_queue(args, project_root)
        elif args.subcommand == "lock":
            dispatch_lock(args, project_root)
        elif args.subcommand == "log":
            dispatch_log(args, project_root)
        elif args.subcommand == "daily-summary":
            dispatch_daily_summary(args, project_root)
        elif args.subcommand == "escalation":
            dispatch_escalation(args, project_root)
        elif args.subcommand == "exec":
            dispatch_exec(args, project_root)
        elif args.subcommand == "project":
            dispatch_project(args)
        elif args.subcommand == "init":
            from .project import cmd_project_init
            cmd_project_init(".", operator=getattr(args, "operator", None))
        elif args.subcommand == "agent":
            dispatch_agent(args, project_root)
    except Exception as e:
        if GLOBAL.dry_run:
            raise
        err(str(e), 1, error="INTERNAL_ERROR")


def get_operator(args) -> str:
    """REQ-A: Resolve operator name from args or environment."""
    op = getattr(args, "operator", None)
    if not op:
        op = os.environ.get("MAI_OPERATOR")
    if not op:
        # Fallback to MAI_AGENT or AGENT_NAME for backward compatibility if needed, 
        # but REQ-A says it must be provided.
        op = os.environ.get("MAI_AGENT") or os.environ.get("AGENT_NAME")
    
    if not op:
        err("操作需要 --operator 参数，如：mai issue claim <id> --operator <name>",
            1, error="OPERATOR_REQUIRED")
    return op


def dispatch_issue(args, project_root: Path) -> None:
    from .issue import (
        cmd_issue_new, cmd_issue_amend, cmd_issue_claim,
        cmd_issue_complete, cmd_issue_block, cmd_issue_unblock,
        cmd_issue_reopen, cmd_issue_status,
        cmd_issue_transfer,
        cmd_issue_confirm, cmd_issue_reject,
        cmd_issue_discard,
    )
    from .issue_list import cmd_issue_list, cmd_issue_show
    if args.issue_cmd == "new":
        op = get_operator(args)
        cmd_issue_new(project_root, args.queue, args.title, args.ref, getattr(args, "priority", "P2"), operator=op)
    elif args.issue_cmd == "amend":
        op = get_operator(args)
        cmd_issue_amend(project_root, args.issue_id, args.remark, operator=op)
    elif args.issue_cmd == "claim":
        op = get_operator(args)
        cmd_issue_claim(project_root, args.issue_id, operator=op)
    elif args.issue_cmd == "block":
        op = get_operator(args)
        cmd_issue_block(project_root, args.issue_id, args.reason, operator=op)
    elif args.issue_cmd == "unblock":
        op = get_operator(args)
        cmd_issue_unblock(project_root, args.issue_id, operator=op)
    elif args.issue_cmd == "complete":
        op = get_operator(args)
        cmd_issue_complete(project_root, args.issue_id, args.conclusion, operator=op)
    elif args.issue_cmd == "reopen":
        op = get_operator(args)
        cmd_issue_reopen(project_root, args.issue_id, args.reason, operator=op)
    elif args.issue_cmd == "status":
        cmd_issue_status(project_root, args.issue_id)
    elif args.issue_cmd == "list":
        cmd_issue_list(project_root, args.queue, getattr(args, "handler", None))
    elif args.issue_cmd == "transfer":
        op = get_operator(args)
        cmd_issue_transfer(project_root, args.issue_id, args.next_handler, operator=op)
    elif args.issue_cmd == "submit-to-creator":
        err("Command 'submit-to-creator' is removed. Please use 'transfer <issue-id> <next-handler>' instead.", 1)
    elif args.issue_cmd == "confirm":
        op = get_operator(args)
        cmd_issue_confirm(project_root, args.issue_id, operator=op)
    elif args.issue_cmd == "reject":
        op = get_operator(args)
        cmd_issue_reject(project_root, args.issue_id, args.reason, operator=op)
    elif args.issue_cmd == "show":
        cmd_issue_show(project_root, args.issue_id)
    elif args.issue_cmd == "escalate":
        from .issue import cmd_issue_escalate
        op = get_operator(args)
        cmd_issue_escalate(project_root, args.issue_id, operator=op)
    elif args.issue_cmd == "discard":
        op = get_operator(args)
        cmd_issue_discard(project_root, args.issue_id, args.reason, operator=op)


def dispatch_project(args) -> None:
    from .project import cmd_project_init, cmd_project_delete
    if args.proj_cmd == "init":
        cmd_project_init(args.name, operator=getattr(args, "operator", None))
    elif args.proj_cmd == "delete":
        op = get_operator(args)
        cmd_project_delete(args.name, operator=op)
    elif args.proj_cmd == "list":
        cmd_project_list(agent=args.agent)


def cmd_project_list(agent: Optional[str] = None):
    """List registered projects."""
    from .project_registry import list_projects, list_projects_by_agent
    if agent:
        projects = list_projects_by_agent(agent)
        out(f"Projects involving agent '{agent}':")
    else:
        projects = list_projects()
        out("Registered Mai Projects:")
    
    if not projects:
        out("  (None)")
        return
        
    for p in projects:
        out(f"  - {p['name']:15} path: {p['path']}")
        out(f"    description: {p.get('description', '')}")
        out(f"    agents:      {', '.join(p.get('agents', []))}")


def dispatch_queue(args, project_root: Path) -> None:
    from .queue import cmd_queue_check, cmd_queue_blockers, cmd_queue_create
    if args.queue_cmd == "check":
        cmd_queue_check(project_root, args.queue, getattr(args, "overdue", False),
                        show_all=getattr(args, "all", False),
                        handler=getattr(args, "handler", None))
    elif args.queue_cmd == "blockers":
        cmd_queue_blockers(project_root)
    elif args.queue_cmd == "create":
        cmd_queue_create(project_root, args.queue, args.owner, args.sla)


def dispatch_lock(args, project_root: Path) -> None:
    from .lock import cmd_lock_check, cmd_lock_release, cmd_lock_guardian
    if args.lock_cmd == "check":
        cmd_lock_check(project_root, args.issue_id)
    elif args.lock_cmd == "release":
        cmd_lock_release(project_root, args.issue_id, args.force, args.yes)
    elif args.lock_cmd == "guardian":
        cmd_lock_guardian(project_root)


def dispatch_log(args, project_root: Path) -> None:
    from .log import cmd_log_history, cmd_log_write, cmd_log_undo
    if args.log_cmd == "history":
        cmd_log_history(project_root, args.date, args.agent)
    elif args.log_cmd == "write":
        cmd_log_write(project_root, args.agent, args.type, args.summary, args.status)
    elif args.log_cmd == "undo":
        cmd_log_undo(project_root)


def dispatch_daily_summary(args, project_root: Path) -> None:
    from .daily_summary import (
        daily_summary_trigger, daily_summary_write, daily_summary_read,
        daily_summary_status, daily_summary_reset,
    )
    if args.ds_cmd == "trigger":
        daily_summary_trigger(project_root)
    elif args.ds_cmd == "write":
        daily_summary_write(project_root, args.agent, args.content)
    elif args.ds_cmd == "read":
        daily_summary_read(project_root, args.target, args.read_all)
    elif args.ds_cmd == "status":
        daily_summary_status(project_root)
    elif args.ds_cmd == "reset":
        daily_summary_reset(project_root)


def dispatch_escalation(args, project_root: Path) -> None:
    from .escalation import cmd_escalation_gen
    if args.esc_cmd == "gen":
        cmd_escalation_gen(project_root, args.issue_id)


def dispatch_exec(args, project_root: Path) -> None:
    from .safe_exec import exec_safe_check
    if args.exec_cmd == "safe-check":
        exec_safe_check(project_root, args.cmd)


def dispatch_agent(args, project_root: Path) -> None:
    from .agent import cmd_agent_add, cmd_agent_list
    if args.agent_cmd == "add":
        cmd_agent_add(project_root, args.name, args.heartbeat_minutes)
    elif args.agent_cmd == "list":
        cmd_agent_list(project_root)


def main():
    parser = build_parser()
    args = parser.parse_args()
    GLOBAL.format = args.format
    GLOBAL.dry_run = args.dry_run
    GLOBAL.project = args.project
    dispatch(args)


if __name__ == "__main__":
    main()
