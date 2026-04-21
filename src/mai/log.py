"""Mai CLI - History / audit log module.

"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .config import get_mai_dir, GLOBAL
from .sync import sync_to_async


def write_history(project_root: Path, agent: str, event_type: str,
                  summary: str, status: str = ""):
    """Append an entry to today's history log, creating a backup first."""
    if GLOBAL.dry_run:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    hist_file = get_mai_dir(project_root) / "history" / f"{today}.log"
    hist_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 3c-i: Snapshot mechanism
    if hist_file.exists():
        shutil.copy2(hist_file, hist_file.with_suffix(".log.bak"))

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


def cmd_log_undo(project_root: Path):
    """3c-ii: Undo the last log entry using the backup or by rewriting."""
    from .mai import out, err
    today = datetime.now().strftime("%Y-%m-%d")
    hist_file = get_mai_dir(project_root) / "history" / f"{today}.log"
    bak_file = hist_file.with_suffix(".log.bak")

    if GLOBAL.dry_run:
        out("[dry-run] Would undo the last log entry", command="log undo")
        return

    if not hist_file.exists():
        err("No log file for today to undo.", 1, error="NO_LOG")

    lines = hist_file.read_text("utf-8", errors="replace").splitlines()
    if not lines:
        err("Log file is empty.", 1, error="EMPTY_LOG")

    # If we have a backup, we could just restore it? 
    # But backup might be from many commands ago if write_history is called frequently.
    # Actually, my write_history creates a backup EVERY time. So backup IS the state before last write.
    
    last_line = lines[-1]
    if bak_file.exists():
        shutil.move(bak_file, hist_file)
    else:
        # Fallback: manually remove last line
        hist_file.write_text("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
    
    sync_to_async(hist_file, project_root)
    out(f"✅ Undone last log entry: {last_line}", command="log undo")
