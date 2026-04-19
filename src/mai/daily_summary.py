"""Mai CLI - Daily summary module.

v1.2.0
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import (
    get_mai_dir, get_daily_order, GLOBAL,
)
from .sync import sync_to_async


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

DAILY_EVENT_FILE = ".daily-summary-event"


# ─────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────

def _read_daily_event(project_root: Path) -> Dict[str, Any]:
    mai = get_mai_dir(project_root)
    event_file = mai / "events" / DAILY_EVENT_FILE
    if event_file.exists():
        try:
            return json.loads(event_file.read_text("utf-8"))
        except Exception:
            return {"triggered_at": ""}
    return {}


def _write_daily_event(project_root: Path, data: Dict[str, Any]):
    if GLOBAL.dry_run:
        return
    mai = get_mai_dir(project_root)
    event_file = mai / "events" / DAILY_EVENT_FILE
    event_file.parent.mkdir(parents=True, exist_ok=True)
    event_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    sync_to_async(event_file, project_root)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def daily_summary_trigger(project_root: Path):
    """REQ-002-1: Error if already triggered and not finished."""
    from .mai import out, err
    mai = get_mai_dir(project_root)
    event_file = mai / "events" / DAILY_EVENT_FILE
    if event_file.exists():
        err("上一轮汇报尚未结束，请先等待汇报结束", 1, 
            error="EVENT_ALREADY_EXISTS", command="daily-summary trigger")
        return

    now = datetime.now().isoformat()
    data = {
        "triggered_at": now,
    }
    if not GLOBAL.dry_run:
        _write_daily_event(project_root, data)
    out("✅ 每日汇报事件已触发，请各 Agent 于今日提交日报", command="daily-summary trigger", **data)


def daily_summary_read(project_root: Path, agent: Optional[str] = None, read_all: bool = False):
    """REQ-002-2 & REQ-002-3: Read agent diary or all summaries."""
    from .mai import out, out_json
    mai = get_mai_dir(project_root)
    today = datetime.now().strftime("%Y-%m-%d")
    summary_dir = mai / "history" / f"daily-{today}"
    order = get_daily_order(project_root)

    if read_all:
        # Collect and finish event
        return daily_summary_collect(project_root)

    if agent == "." or agent is None:
        # Read all current progress without finishing
        results = {}
        for a in order:
            sf = summary_dir / f"{a}.md"
            results[a] = sf.read_text("utf-8", errors="replace") if sf.exists() else ""
        
        if GLOBAL.format == "json":
            out_json({"ok": True, "summaries": results})
        else:
            lines = [f"=== Daily Progress - {today} ==="]
            for a in order:
                content = results.get(a, "").strip()
                lines.append(f"\n## {a.title()}")
                lines.append(content if content else "(no summary)")
            out("\n".join(lines))
        return

    # Read specific agent
    if agent not in order:
        from .mai import err
        err(f"Unknown agent: {agent}. Valid: {order}", 1, error="INVALID_AGENT")

    sf = summary_dir / f"{agent}.md"
    content = sf.read_text("utf-8", errors="replace") if sf.exists() else ""
    
    if GLOBAL.format == "json":
        out_json({"ok": True, "agent": agent, "content": content})
    else:
        print(content)


def daily_summary_write(project_root: Path, agent: str, content: str):
    """REQ-002-2: Full overwrite, no more turn-based locking."""
    from .mai import out, err
    order = get_daily_order(project_root)
    if agent not in order:
        err(f"Unknown agent: {agent}. Valid: {order}", 1, error="INVALID_AGENT")

    event = _read_daily_event(project_root)
    if not event.get("triggered_at"):
        err("Daily summary not triggered today.", 1, error="NOT_TRIGGERED")
        return

    mai = get_mai_dir(project_root)
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

        # REQ-002: If last agent, auto-finish the cycle
        if order and agent == order[-1]:
            event_file = mai / "events" / DAILY_EVENT_FILE
            if event_file.exists():
                event_file.unlink()

    out(f"Daily summary written for {agent}.", command="daily-summary write", agent=agent)


def daily_summary_collect(project_root: Path):
    """
    REQ-002-3: Summarize all agent summaries and generate a report.
    """
    from .mai import out, out_json, GLOBAL
    mai = get_mai_dir(project_root)
    today = datetime.now().strftime("%Y-%m-%d")
    summary_dir = mai / "history" / f"daily-{today}"
    order = get_daily_order(project_root)

    results = {}
    for agent in order:
        sf = summary_dir / f"{agent}.md"
        results[agent] = sf.read_text("utf-8", errors="replace") if sf.exists() else ""

    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"daily-{today}-summary.md"

    if not GLOBAL.dry_run:
        lines = [f"# 每日协同汇总 - {today}\n"]
        for agent in order:
            content = results.get(agent, "").strip()
            lines.append(f"\n## {agent.title()}")
            lines.append(content if content else "（无摘要）")
        report_text = "\n".join(lines)
        report_file.write_text(report_text, encoding="utf-8")
        sync_to_async(report_file, project_root)

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "daily-summary read --all",
                  "date": today, "summaries": results})
    else:
        lines = [f"=== Daily Summary Report - {today} ==="]
        for agent in order:
            lines.append(f"\n## {agent.title()}")
            lines.append(results.get(agent, "") or "(no summary)")
        out("\n".join(lines), command="daily-summary read --all")
