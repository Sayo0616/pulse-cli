"""Mai CLI - Daily summary module.

v1.1.0
"""

import fcntl
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from .config import (
    get_mai_dir, get_async_dir, get_daily_order, GLOBAL,
    DAILY_SUMMARY_ORDER,
)
from .sync import sync_to_async


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

DAILY_EVENT_FILE = ".daily-summary-event"
DAILY_LOCK_FILE = ".daily-lock"


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
            return {"triggered_at": "", "next_agent": DAILY_SUMMARY_ORDER[0]}
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
    """Idempotent: only creates event if not already present today."""
    from .mai import out
    mai = get_mai_dir(project_root)
    event_file = mai / "events" / DAILY_EVENT_FILE
    if event_file.exists():
        out("Daily summary event already triggered today.",
            command="daily-summary trigger", idempotent=True)
        return

    now = datetime.now().isoformat()
    order = get_daily_order(project_root)
    data = {
        "triggered_at": now,
        "next_agent": order[0] if order else "DONE",
    }
    if not GLOBAL.dry_run:
        _write_daily_event(project_root, data)
    out("Daily summary event triggered.", command="daily-summary trigger", **data)


def daily_summary_write(project_root: Path, agent: str, content: str):
    """
    Per §2.4 Step-by-step:
    Step 1: Check event exists → skip if not
    Step 2: Check .daily-lock (stale → force release, alive → skip)
    Step 3: Check next_agent == agent → skip if not my turn
    Step 4: Create .daily-lock
    Step 5: Write summary
    Step 6: Update next_agent
    Step 7: Remove .daily-lock
    """
    from .mai import out, err
    order = get_daily_order(project_root)
    if agent not in order:
        err(f"Unknown agent: {agent}. Valid: {order}", 1, error="INVALID_AGENT")

    # Step 1
    event = _read_daily_event(project_root)
    if not event.get("triggered_at"):
        out(f"Daily summary not triggered today. Skipping for {agent}.",
            command="daily-summary write")
        return

    mai = get_mai_dir(project_root)
    lock_file = mai / "locks" / DAILY_LOCK_FILE
    today = datetime.now().strftime("%Y-%m-%d")

    # Step 2: Check .daily-lock
    if lock_file.exists():
        stat = lock_file.stat()
        age = datetime.now().timestamp() - stat.st_mtime
        threshold = 5 * 60  # 5 minute threshold for daily lock
        if age <= threshold:
            holder = lock_file.read_text("utf-8", errors="replace").strip()
            out(f"Daily summary still being written by {holder}. Skipping for {agent}.",
                command="daily-summary write")
            return
        else:
            lock_file.unlink(missing_ok=True)

    # Step 3: Check order
    next_agent = event.get("next_agent", order[0] if order else "DONE")
    if next_agent != agent:
        out(f"Not {agent}'s turn (next: {next_agent}). Skipping.",
            command="daily-summary write")
        return

    if not GLOBAL.dry_run:
        # Step 4: Create .daily-lock
        with open(lock_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(f"{agent}|{datetime.now().isoformat()}")
            f.flush()

            # Step 5: Write summary
            summary_dir = mai / "history" / f"daily-{today}"
            summary_dir.mkdir(parents=True, exist_ok=True)
            summary_file = summary_dir / f"{agent}.md"
            summary_file.write_text(
                f"# {agent.title()} Daily Summary - {today}\n\n{content}\n",
                encoding="utf-8"
            )
            sync_to_async(summary_file, project_root)

            # Step 6: Update next_agent
            idx = order.index(agent)
            next_idx = idx + 1
            new_event = dict(event)
            new_event["next_agent"] = order[next_idx] if next_idx < len(order) else "DONE"
            _write_daily_event(project_root, new_event)

            # Step 7: Remove .daily-lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            lock_file.unlink(missing_ok=True)

    out(f"Daily summary written for {agent}.", command="daily-summary write", agent=agent)


def daily_summary_collect(project_root: Path):
    """
    designer-only: reads all agent summaries, generates final report,
    saves to reports/daily-YYYY-MM-DD-summary.md,
    removes .daily-summary-event.
    """
    from .mai import out, out_json, GLOBAL
    mai = get_mai_dir(project_root)
    async_dir = get_async_dir(project_root)
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
        if report_file.exists():
            out(f"Daily report already exists: {report_file}",
                command="daily-summary collect", idempotent=True)
        else:
            lines = [f"# 每日协同汇总 - {today}\n"]
            for agent in order:
                content = results.get(agent, "").strip()
                lines.append(f"\n## {agent.title()}")
                lines.append(content if content else "（无摘要）")
            report_text = "\n".join(lines)
            report_file.write_text(report_text, encoding="utf-8")
            sync_to_async(report_file, project_root)

            # Remove event marker
            event_file = mai / "events" / DAILY_EVENT_FILE
            if event_file.exists():
                event_file.unlink()

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "daily-summary collect",
                  "date": today, "summaries": results})
    else:
        lines = [f"=== Daily Summary - {today} ==="]
        for agent in order:
            lines.append(f"\n## {agent.title()}")
            lines.append(results.get(agent, "") or "(no summary)")
        out("\n".join(lines), command="daily-summary collect")
