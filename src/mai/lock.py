"""Mai CLI - Lock protocol module.

v1.1.0
"""

import fcntl
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .config import (
    get_mai_dir, get_async_dir, get_heartbeat_intervals, GLOBAL,
)
from .sync import sync_to_async


def lock_path(project_root: Path, issue_id: str) -> Path:
    return get_mai_dir(project_root) / "locks" / f"{issue_id}.lock"


def acquire_lock(project_root: Path, issue_id: str, agent: str) -> bool:
    """Acquire flock-based lock. Returns True if acquired, False if held by alive agent."""
    lp = lock_path(project_root, issue_id)
    lp.parent.mkdir(parents=True, exist_ok=True)

    lock_fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o644)

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stat = os.fstat(lock_fd)
        mtime = stat.st_mtime
        age_seconds = datetime.now().timestamp() - mtime

        os.lseek(lock_fd, 0, os.SEEK_SET)
        content = os.read(lock_fd, 256).decode("utf-8", errors="replace").strip()
        parts = content.split("|")
        holder_agent = parts[0] if parts else "unknown"

        heartbeat = get_heartbeat_intervals(project_root).get(holder_agent, 17)
        threshold_seconds = heartbeat * 1.5 * 60

        if age_seconds > threshold_seconds:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            lp.unlink(missing_ok=True)
            lock_fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            os.close(lock_fd)
            return False

    ts = datetime.now().isoformat()
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, f"{agent}|{ts}".encode("utf-8"))
    os.fsync(lock_fd)
    os.utime(lp, None)
    os.close(lock_fd)

    if not GLOBAL.dry_run:
        proc_dir = get_mai_dir(project_root) / "processing"
        proc_dir.mkdir(parents=True, exist_ok=True)
        proc_file = proc_dir / f"{issue_id}.md"
        proc_file.write_text(
            f"# Processing\n\nIssue: {issue_id}\nAgent: {agent}\nStarted: {ts}\n"
        )
        sync_to_async(proc_file, project_root)

    return True


def release_lock(project_root: Path, issue_id: str):
    lp = lock_path(project_root, issue_id)
    if lp.exists() and not GLOBAL.dry_run:
        lp.unlink()
    proc_file = get_mai_dir(project_root) / "processing" / f"{issue_id}.md"
    if proc_file.exists() and not GLOBAL.dry_run:
        proc_file.unlink()


def check_lock(project_root: Path, issue_id: str) -> Optional[Dict[str, Any]]:
    lp = lock_path(project_root, issue_id)
    if not lp.exists():
        return None
    stat = lp.stat()
    content = lp.read_text("utf-8", errors="replace").strip()
    parts = content.split("|")
    holder = parts[0] if parts else "unknown"
    ts = parts[1] if len(parts) > 1 else ""

    heartbeat = get_heartbeat_intervals(project_root).get(holder, 17)
    threshold_seconds = heartbeat * 1.5 * 60
    age_seconds = datetime.now().timestamp() - stat.st_mtime
    stale = age_seconds > threshold_seconds

    return {
        "issue_id":          issue_id,
        "holder":           holder,
        "timestamp":        ts,
        "age_seconds":      round(age_seconds, 1),
        "threshold_seconds": threshold_seconds,
        "stale":            stale,
    }


# ─────────────────────────────────────────────
# Lock Commands
# ─────────────────────────────────────────────

def cmd_lock_check(project_root: Path, issue_id: str):
    from .mai import out, out_json, GLOBAL
    lock_info = check_lock(project_root, issue_id)
    if lock_info:
        if GLOBAL.format == "json":
            out_json({"ok": True, "command": "lock check", "lock": lock_info})
        else:
            stale_str = " (STALE)" if lock_info["stale"] else ""
            out(
                f"Lock held by {lock_info['holder']} since {lock_info['timestamp']} "
                f"(age: {lock_info['age_seconds']}s, threshold: {lock_info['threshold_seconds']}s){stale_str}",
                command="lock check", **lock_info
            )
    else:
        out(f"No lock on issue {issue_id}.", command="lock check", locked=False)


def cmd_lock_force_release(project_root: Path, issue_id: str):
    from .mai import out, err, write_history, GLOBAL
    lock_info = check_lock(project_root, issue_id)
    if not lock_info:
        out(f"No lock to release on issue {issue_id}.", command="lock force-release")
        return

    if not lock_info["stale"]:
        ttl = round((lock_info["threshold_seconds"] - lock_info["age_seconds"]) / 60, 1)
        err(
            f"Lock on {issue_id} still alive (TTL: {ttl} min). Refusing to force-release.",
            2, error="LOCK_ALIVE", ttl_minutes=ttl
        )

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        write_history(project_root, "system", "lock_force_release",
                      f"Force-released lock on {issue_id} (was held by {lock_info['holder']})")

    out(f"Force-released lock on issue {issue_id} (was held by {lock_info['holder']}).",
        command="lock force-release", former_holder=lock_info["holder"])


def cmd_lock_guardian(project_root: Path):
    from .mai import out, out_json, write_history, GLOBAL
    mai = get_mai_dir(project_root)
    locks_dir = mai / "locks"
    if not locks_dir.exists():
        out("No locks found.", command="lock guardian")
        return

    stale_locks = []
    all_locks = []
    for lock_file in locks_dir.glob("*.lock"):
        issue_id = lock_file.stem
        info = check_lock(project_root, issue_id)
        if info:
            all_locks.append(info)
            if info["stale"]:
                stale_locks.append(info)
                if not GLOBAL.dry_run:
                    release_lock(project_root, issue_id)
                    write_history(project_root, "guardian", "lock_force_release",
                                  f"Guardian released stale lock: {issue_id} (held by {info['holder']})")

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "lock guardian",
                  "total_locks": len(all_locks), "stale_released": len(stale_locks),
                  "stale_locks": stale_locks})
    else:
        out(f"\n## Lock Guardian Report")
        out(f"Total locks: {len(all_locks)}")
        out(f"Stale locks released: {len(stale_locks)}")
        for lk in all_locks:
            stale_str = " STALE → RELEASED" if lk["stale"] else ""
            out(f"  [{lk['issue_id']}] {lk['holder']} - {lk['age_seconds']}s old{stale_str}")
