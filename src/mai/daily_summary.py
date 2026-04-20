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

DAILY_EVENT_FILE = ".daily-summary-event"
DAILY_LOCK_FILE  = ".daily-summary.lock"


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


def daily_summary_read(project_root: Path, agent: Optional[str] = None, read_all: bool = False) -> DailySummaryResult:
    """REQ-002-2 & REQ-002-3: 统一返回 DailySummaryResult。"""
    from .mai import out, out_json, err
    mai = get_mai_dir(project_root)
    today = datetime.now().strftime("%Y-%m-%d")
    summary_dir = mai / "history" / f"daily-{today}"
    order = get_daily_order(project_root)

    if read_all:
        # 直接透传 collect 的结果（已是 DailySummaryResult，is_all=True）
        return daily_summary_collect(project_root)

    if agent == "." or agent is None:
        err("Must specify an agent (e.g., 'mai daily-summary read programmer').", 1, error="AGENT_REQUIRED")

    # 读取指定 agent
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
    """REQ-002-2: Write diary with flock protection."""
    from .mai import out, err
    order = get_daily_order(project_root)
    if agent not in order:
        err(f"Unknown agent: {agent}. Valid: {order}", 1, error="INVALID_AGENT")

    mai = get_mai_dir(project_root)
    lock_file = mai / "events" / DAILY_LOCK_FILE
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_file, "w") as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            event = _read_daily_event(project_root)
            if not event.get("triggered_at"):
                err("Daily summary not triggered today.", 1, error="NOT_TRIGGERED")
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

                # REQ-002: If last agent, auto-finish the cycle
                if order and agent == order[-1]:
                    event_file = mai / "events" / DAILY_EVENT_FILE
                    if event_file.exists():
                        event_file.unlink()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    out(f"Daily summary written for {agent}.", command="daily-summary write", agent=agent)


def daily_summary_collect(project_root: Path) -> DailySummaryResult:
    """
    REQ-002-3: 汇总所有 agent 日报，生成报告文件。
    返回 DailySummaryResult，与 daily_summary_read 保持类型一致。
    """
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
            lines.append(summaries.get(agent, "") or "(no summary)")
        out("\n".join(lines), command="daily-summary read --all")

    return DailySummaryResult(date=today, summaries=summaries, is_all=True)
