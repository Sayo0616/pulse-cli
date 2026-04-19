"""Mai CLI - Main entry point with argument parsing and dispatch.

v1.1.0
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .config import (
    get_mai_dir, get_async_dir, find_project_root,
    load_config, GLOBAL, DAILY_SUMMARY_ORDER,
)
from .sync import sync_to_async
from .log import write_history, read_history
from .safe_exec import exec_safe_check

# ─────────────────────────────────────────────
# Output Helpers
# ─────────────────────────────────────────────

def out(msg: str = "", **kwargs):
    if GLOBAL.format == "json":
        data = {"ok": True, "command": kwargs.pop("command", "unknown"), **kwargs}
        if msg:
            data["message"] = msg
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(msg)


def err(msg: str, code: int = 1, error: str = "", **kwargs):
    if GLOBAL.format == "json":
        data = {
            "ok":       False,
            "error":    error or msg,
            "message":  msg,
            "exit_code": code,
            "command":  kwargs.pop("command", "unknown"),
            **kwargs
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def out_json(data: dict):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_name(subcommand: str, subsubcommand: str = "") -> str:
    return f"{subsubcommand}" if subsubcommand else subcommand


# ─────────────────────────────────────────────
# Project Structure Helper (used by multiple commands)
# ─────────────────────────────────────────────

def ensure_mai_structure(project_root: Path):
    """Create all required .mai/ and async/ subdirectories."""
    from .config import get_queue_sla
    mai = get_mai_dir(project_root)
    (mai / "queues").mkdir(parents=True, exist_ok=True)
    (mai / "processing").mkdir(parents=True, exist_ok=True)
    (mai / "locks").mkdir(parents=True, exist_ok=True)
    (mai / "decisions").mkdir(parents=True, exist_ok=True)
    (mai / "history").mkdir(parents=True, exist_ok=True)
    (mai / "events").mkdir(parents=True, exist_ok=True)
    async_dir = get_async_dir(project_root)
    async_dir.mkdir(parents=True, exist_ok=True)
    queue_sla = get_queue_sla(project_root)
    for q in queue_sla:
        (mai / "queues" / q).mkdir(parents=True, exist_ok=True)
        (async_dir / q).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Argument Parser
# ─────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(prog="mai", description="Agent Collaboration CLI")
    parser.add_argument("--project", dest="project", default=None)
    parser.add_argument("--format", dest="format", choices=["json", "text"], default="text")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # ── issue ──
    issue_sp = sub.add_parser("issue", help="Issue commands")
    iss = issue_sp.add_subparsers(dest="issue_cmd", required=True)

    p = iss.add_parser("new", help="Create new issue")
    p.add_argument("queue"); p.add_argument("title")
    p.add_argument("--ref", default=None)

    p = iss.add_parser("amend", help="Amend issue")
    p.add_argument("issue_id"); p.add_argument("remark", nargs="?", default="")

    p = iss.add_parser("claim", help="Claim issue")
    p.add_argument("issue_id")

    p = iss.add_parser("complete", help="Complete issue")
    p.add_argument("issue_id"); p.add_argument("conclusion", nargs="?", default="")

    p = iss.add_parser("list", help="List issues")
    p.add_argument("queue", nargs="?", default=None)

    p = iss.add_parser("show", help="Show issue")
    p.add_argument("issue_id")

    p = iss.add_parser("escalate", help="Escalate issue")
    p.add_argument("issue_id")

    # ── queue ──
    queue_sp = sub.add_parser("queue")
    q = queue_sp.add_subparsers(dest="queue_cmd", required=True)
    p = q.add_parser("check", help="Check queue")
    p.add_argument("queue", nargs="?", default=None)
    p.add_argument("--overdue", dest="overdue", action="store_true")
    q.add_parser("blockers", help="Show designer blockers")

    # ── lock ──
    lock_sp = sub.add_parser("lock")
    lk = lock_sp.add_subparsers(dest="lock_cmd", required=True)
    p = lk.add_parser("check"); p.add_argument("issue_id")
    p = lk.add_parser("force-release"); p.add_argument("issue_id")
    lk.add_parser("guardian")

    # ── log ──
    log_sp = sub.add_parser("log")
    lg = log_sp.add_subparsers(dest="log_cmd", required=True)
    p = lg.add_parser("history")
    p.add_argument("--date", dest="date", default=None)
    p.add_argument("--agent", dest="agent", default=None)
    p = lg.add_parser("write")
    p.add_argument("agent"); p.add_argument("type"); p.add_argument("summary")
    p.add_argument("status", nargs="?", default="")

    # ── daily-summary ──
    ds_sp = sub.add_parser("daily-summary")
    ds = ds_sp.add_subparsers(dest="ds_cmd", required=True)
    ds.add_parser("trigger")
    p = ds.add_parser("read")
    p.add_argument("target", nargs="?", default=".") # <agent> / .
    p.add_argument("--all", dest="read_all", action="store_true")
    p = ds.add_parser("write")
    p.add_argument("agent"); p.add_argument("content", nargs="+", default=[])

    # ── escalation ──
    esc_sp = sub.add_parser("escalation")
    esc = esc_sp.add_subparsers(dest="esc_cmd", required=True)
    p = esc.add_parser("gen"); p.add_argument("issue_id")

    # ── exec ──
    exec_sp = sub.add_parser("exec")
    ex = exec_sp.add_subparsers(dest="exec_cmd", required=True)
    p = ex.add_parser("safe-check"); p.add_argument("cmd")

    # ── project ──
    proj_sp = sub.add_parser("project")
    pr = proj_sp.add_subparsers(dest="proj_cmd", required=True)
    p = pr.add_parser("init"); p.add_argument("project_name")

    return parser


# ─────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────

def dispatch(args):
    # Lazy import to avoid circular dependency at module load time
    from .issue import (
        cmd_issue_new, cmd_issue_amend, cmd_issue_claim,
        cmd_issue_complete, cmd_issue_escalate,
    )
    from .issue_list import cmd_issue_list, cmd_issue_show
    from .queue import cmd_queue_check, cmd_queue_blockers
    from .lock import cmd_lock_check, cmd_lock_force_release, cmd_lock_guardian
    from .log import cmd_log_history, cmd_log_write
    from .daily_summary import (
        daily_summary_trigger, daily_summary_write, daily_summary_read,
    )
    from .escalation import cmd_escalation_gen
    from .safe_exec import exec_safe_check
    from .project import cmd_project_init

    project_root = None
    if args.subcommand != "project" or args.proj_cmd != "init":
        project_root = find_project_root(args.project)
        if project_root is None:
            err("Project not found. Set AGENTS_PROJECT/MAI_PROJECT or run 'mai project init'.",
                4, error="PROJECT_NOT_FOUND")
        mai_cfg = get_mai_dir(project_root) / "config.json"
        if not mai_cfg.exists():
            err(f"Project not initialized. Run 'mai project init {project_root.name}'.",
                4, error="NOT_INITIALIZED")

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
    except Exception as e:
        err(str(e), 1, error="INTERNAL_ERROR")


def dispatch_issue(args, project_root):
    from .issue import (
        cmd_issue_new, cmd_issue_amend, cmd_issue_claim,
        cmd_issue_complete, cmd_issue_escalate,
    )
    from .issue_list import cmd_issue_list, cmd_issue_show
    if args.issue_cmd == "new":
        cmd_issue_new(project_root, args.queue, args.title, args.ref)
    elif args.issue_cmd == "amend":
        cmd_issue_amend(project_root, args.issue_id, args.remark)
    elif args.issue_cmd == "claim":
        cmd_issue_claim(project_root, args.issue_id)
    elif args.issue_cmd == "complete":
        cmd_issue_complete(project_root, args.issue_id, args.conclusion)
    elif args.issue_cmd == "list":
        cmd_issue_list(project_root, args.queue)
    elif args.issue_cmd == "show":
        cmd_issue_show(project_root, args.issue_id)
    elif args.issue_cmd == "escalate":
        cmd_issue_escalate(project_root, args.issue_id)


def dispatch_queue(args, project_root):
    from .queue import cmd_queue_check, cmd_queue_blockers
    if args.queue_cmd == "check":
        cmd_queue_check(project_root, args.queue, args.overdue)
    elif args.queue_cmd == "blockers":
        cmd_queue_blockers(project_root)


def dispatch_lock(args, project_root):
    from .lock import cmd_lock_check, cmd_lock_force_release, cmd_lock_guardian
    if args.lock_cmd == "check":
        cmd_lock_check(project_root, args.issue_id)
    elif args.lock_cmd == "force-release":
        cmd_lock_force_release(project_root, args.issue_id)
    elif args.lock_cmd == "guardian":
        cmd_lock_guardian(project_root)


def dispatch_log(args, project_root):
    from .log import cmd_log_history, cmd_log_write
    if args.log_cmd == "history":
        cmd_log_history(project_root, args.date, args.agent)
    elif args.log_cmd == "write":
        cmd_log_write(project_root, args.agent, args.type, args.summary, args.status)


def dispatch_daily_summary(args, project_root):
    from .daily_summary import (
        daily_summary_trigger, daily_summary_write, daily_summary_read,
    )
    if args.ds_cmd == "trigger":
        daily_summary_trigger(project_root)
    elif args.ds_cmd == "write":
        content = " ".join(args.content) if args.content else ""
        daily_summary_write(project_root, args.agent, content)
    elif args.ds_cmd == "read":
        daily_summary_read(project_root, args.target, args.read_all)


def dispatch_escalation(args, project_root):
    from .escalation import cmd_escalation_gen
    if args.esc_cmd == "gen":
        cmd_escalation_gen(project_root, args.issue_id)


def dispatch_exec(args, project_root):
    from .safe_exec import exec_safe_check
    if args.exec_cmd == "safe-check":
        safe = exec_safe_check(args.cmd)
        if GLOBAL.format == "json":
            out_json({"ok": True, "command": "exec safe-check",
                      "safe": safe, "command": args.cmd, "exit_code": 0 if safe else 2})
        else:
            out(f"Command is {'SAFE' if safe else 'UNSAFE'}: {args.cmd}",
                command="exec safe-check", safe=safe)
        if not safe:
            sys.exit(2)


def dispatch_project(args):
    from .project import cmd_project_init
    if args.proj_cmd == "init":
        cmd_project_init(args.project_name)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()
    GLOBAL.format = args.format
    GLOBAL.dry_run = args.dry_run
    GLOBAL.project = args.project
    dispatch(args)


if __name__ == "__main__":
    main()
