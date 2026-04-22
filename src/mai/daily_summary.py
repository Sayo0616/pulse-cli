"""Mai CLI - Daily summary module.

"""

import json
import fcntl
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import (
    get_mai_dir, get_daily_order, GLOBAL,
)
from .sync import sync_to_async


# ─────────────────────────────────────────────
# Structured Return Type
# ─────────────────────────────────────────────

@dataclass
class DailySummaryResult:
    """统一返回值类型，所有分支返回同类对象。"""
    date: str                       # 哪一天的日报
    summaries: Dict[str, str]       # agent -> content
    is_all: bool                   # 是否为 --all 汇总模式

    def get(self, agent: str) -> str:
        """获取指定 agent 的内容，不存在返回空字符串。"""
        return self.summaries.get(agent, "")


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

DAILY_STATUS_FILE = "status.json"
DAILY_LOCK_FILE   = ".daily-summary.lock"


# ─────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────

def _status_file_path(project_root: Path) -> Path:
    return get_mai_dir(project_root) / "daily-summary" / DAILY_STATUS_FILE


def _read_status(project_root: Path) -> Dict[str, Any]:
    stat_file = _status_file_path(project_root)
    if stat_file.exists():
        try:
            return json.loads(stat_file.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def _write_status(project_root: Path, data: Dict[str, Any]):
    if GLOBAL.dry_run:
        return
    stat_file = _status_file_path(project_root)
    stat_file.parent.mkdir(parents=True, exist_ok=True)
    stat_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    sync_to_async(stat_file, project_root)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def daily_summary_trigger(project_root: Path):
    """REQ-002-1 & REQ-011: Initialize status.json for the daily round."""
    from .mai import out, err
    status = _read_status(project_root)
    if status.get("triggered_at"):
        err("Today's round is already triggered. Use 'mai daily-summary reset' if needed.", 
            1, error="ALREADY_TRIGGERED", command="daily-summary trigger")
        return

    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")
    order = get_daily_order(project_root)
    
    data = {
        "date": today,
        "triggered_at": now,
        "participants": order,
        "status": {agent: "pending" for agent in order}
    }
    
    if not GLOBAL.dry_run:
        _write_status(project_root, data)
    
    out(f"✅ Daily summary triggered for {today}.", command="daily-summary trigger", **data)
    if order:
        out(f"Next up: {order[0]}")


def daily_summary_read(project_root: Path, agent: Optional[str] = None, read_all: bool = False) -> DailySummaryResult:
    """REQ-002-2 & REQ-002-3: 统一返回 DailySummaryResult。"""
    from .mai import out, out_json, err
    mai = get_mai_dir(project_root)
    today = datetime.now().strftime("%Y-%m-%d")
    summary_dir = mai / "history" / f"daily-{today}"
    order = get_daily_order(project_root)

    if read_all:
        return daily_summary_collect(project_root)

    if agent == "." or agent is None:
        err("Must specify an agent (e.g., 'mai daily-summary read programmer').", 1, error="AGENT_REQUIRED")

    if agent not in order:
        err(f"Unknown agent: {agent}. Valid: {order}", 1, error="INVALID_AGENT")

    sf = summary_dir / f"{agent}.md"
    content = sf.read_text("utf-8", errors="replace") if sf.exists() else ""
    summaries = {agent: content}

    result = DailySummaryResult(date=today, summaries=summaries, is_all=False)
    if GLOBAL.format == "json":
        out_json({"ok": True, "date": today, "agent": agent, "content": content})
    else:
        out(content)
    return result


def daily_summary_write(project_root: Path, agent: str, content: str):
    """REQ-002-2 & REQ-011: Write diary with turn checking and status updates."""
    from .mai import out, err, suggest
    status = _read_status(project_root)
    if not status.get("triggered_at"):
        err("Daily summary not triggered today.", 1, error="NOT_TRIGGERED", hint="Run 'mai daily-summary trigger' to start today's round.")
        return

    order = status.get("participants", [])
    if agent not in order:
        hint = suggest(agent, order, "mai agent list")
        err(f"Agent '{agent}' is not a participant.", 1, error="INVALID_AGENT", hint=hint)
        return

    agent_status = status.get("status", {})
    if agent_status.get(agent) == "written":
        out(f"Agent '{agent}' already submitted for today.", command="daily-summary write", idempotent=True)
        return

    mai = get_mai_dir(project_root)
    lock_file = mai / "events" / DAILY_LOCK_FILE
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_file, "w") as f:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            status = _read_status(project_root)
            agent_status = status.get("status", {})

            if agent_status.get(agent) == "written":
                 out(f"Agent '{agent}' already submitted for today.", command="daily-summary write", idempotent=True)
                 return

            today = datetime.now().strftime("%Y-%m-%d")

            if not GLOBAL.dry_run:
                summary_dir = mai / "history" / f"daily-{today}"
                summary_dir.mkdir(parents=True, exist_ok=True)
                summary_file = summary_dir / f"{agent}.md"
                summary_file.write_text(
                    f"# {agent.title()} Daily Summary - {today}\n\n{content}\n",
                    encoding="utf-8"
                )
                sync_to_async(summary_file, project_root)

                agent_status[agent] = "written"
                status["status"] = agent_status
                _write_status(project_root, status)

        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    out(f"Daily summary written for {agent}.", command="daily-summary write", agent=agent)


def daily_summary_status(project_root: Path):
    """REQ-011: Show current round status."""
    from .mai import out, out_json
    status = _read_status(project_root)
    if not status:
        out("Daily summary not triggered today.")
        return

    date = status.get("date")
    participants = status.get("participants", [])
    agent_status = status.get("status", {})

    if GLOBAL.format == "json":
        out_json({"ok": True, "date": date, "participants": participants, "status": agent_status})
        return

    out(f"Daily Summary Status ({date}):")
    next_up = None
    for p in participants:
        s = agent_status.get(p, "pending")
        icon = "✓" if s == "written" else "⏳"
        out(f"  {p:12}: {icon} {s}")
        if s == "pending" and next_up is None:
            next_up = p
    
    if next_up:
        out(f"\nNext up: {next_up}")
    else:
        out("\nAll summaries complete for today!")


def daily_summary_reset(project_root: Path):
    """REQ-011: Reset today's round by deleting status.json."""
    from .mai import out
    if GLOBAL.dry_run:
        out("[dry-run] Would delete status.json", command="daily-summary reset")
        return

    stat_file = _status_file_path(project_root)
    if stat_file.exists():
        stat_file.unlink()
        out("✅ Daily summary round reset.", command="daily-summary reset")
    else:
        out("No daily summary round to reset.", command="daily-summary reset", idempotent=True)


def daily_summary_collect(project_root: Path) -> DailySummaryResult:
    """REQ-002-3: 汇总所有 agent 日报，生成报告文件。"""
    from .mai import out, out_json, GLOBAL
    mai = get_mai_dir(project_root)
    today = datetime.now().strftime("%Y-%m-%d")
    summary_dir = mai / "history" / f"daily-{today}"
    order = get_daily_order(project_root)

    summaries: Dict[str, str] = {}
    for agent in order:
        sf = summary_dir / f"{agent}.md"
        summaries[agent] = sf.read_text("utf-8", errors="replace") if sf.exists() else ""

    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"daily-{today}-summary.md"

    if not GLOBAL.dry_run:
        lines = [f"# 每日协同汇总 - {today}\n"]
        for agent in order:
            content = summaries.get(agent, "").strip()
            lines.append(f"\n## {agent.title()}")
            lines.append(content if content else "（无摘要）")
        report_text = "\n".join(lines)
        report_file.write_text(report_text, encoding="utf-8")
        sync_to_async(report_file, project_root)

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "daily-summary read --all",
                  "date": today, "summaries": summaries})
    else:
        lines = [f"=== Daily Summary Report - {today} ==="]
        for agent in order:
            lines.append(f"\n## {agent.title()}")
            lines.append(summaries.get(agent, "") or "（无摘要）")
        out("\n".join(lines), command="daily-summary read --all")

    return DailySummaryResult(date=today, summaries=summaries, is_all=True)
