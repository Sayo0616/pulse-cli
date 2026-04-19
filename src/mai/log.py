"""Mai CLI - History / audit log module.

v1.1.0
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .config import get_mai_dir, GLOBAL
from .sync import sync_to_async


def write_history(project_root: Path, agent: str, event_type: str,
                  summary: str, status: str = ""):
    """Append an entry to today's history log."""
    if GLOBAL.dry_run:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    hist_file = get_mai_dir(project_root) / "history" / f"{today}.log"
    hist_file.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat()
    entry = f"[{ts}] [{agent.upper()}] [{event_type}] {summary}"
    if status:
        entry += f" [{status}]"
    entry += "\n"
    with open(hist_file, "a") as f:
        f.write(entry)
    sync_to_async(hist_file, project_root)


def read_history(project_root: Path,
                 date: Optional[str] = None,
                 agent: Optional[str] = None) -> List[str]:
    """Read history log for a given date, optionally filtered by agent."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    hist_file = get_mai_dir(project_root) / "history" / f"{date}.log"
    if not hist_file.exists():
        return []
    lines = hist_file.read_text("utf-8", errors="replace").splitlines()
    if agent:
        lines = [l for l in lines if f"[{agent.upper()}]" in l]
    return lines


# ─────────────────────────────────────────────
# Log Commands
# ─────────────────────────────────────────────

def cmd_log_history(project_root: Path, date: Optional[str], agent: Optional[str]):
    from .mai import out, out_json, GLOBAL
    lines = read_history(project_root, date, agent)
    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "log history",
                  "date": date or datetime.now().strftime("%Y-%m-%d"),
                  "agent": agent, "entries": lines})
    else:
        if not lines:
            out("(no history entries)")
        else:
            for line in lines:
                out(line)


def cmd_log_write(project_root: Path, agent: str, log_type: str,
                  summary: str, status: str = ""):
    from .mai import out, GLOBAL
    if not GLOBAL.dry_run:
        write_history(project_root, agent, log_type, summary, status or "进行中")
    out(f"Log entry: [{agent}] [{log_type}] {summary}", command="log write")
