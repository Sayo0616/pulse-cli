"""Mai CLI - Issue commands module.

v1.1.0
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import (
    get_queue_sla, get_queue_id_prefix, get_status_emoji,
    get_mai_dir, get_async_dir, GLOBAL,
)
from .sync import sync_to_async
from .lock import acquire_lock, release_lock, check_lock
from .log import write_history


# ─────────────────────────────────────────────
# Issue ID Generation
# ─────────────────────────────────────────────

def next_issue_id(project_root: Path, queue: str) -> str:
    prefix = get_queue_id_prefix(project_root).get(queue, "REQ")
    queue_dir = get_mai_dir(project_root) / "queues" / queue
    queue_dir.mkdir(parents=True, exist_ok=True)
    max_num = 0
    for f in queue_dir.glob("*.md"):
        m = re.match(rf"^{prefix}-(\d+)\.md$", f.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}-{max_num + 1:03d}"


# ─────────────────────────────────────────────
# Issue File Format (per AGENTS_COLLAB_DESIGN_CMD.md §七·P0-1)
# ─────────────────────────────────────────────

def make_issue_content(
    issue_id: str,
    queue: str,
    title: str,
    status: str = "open",
    owner: str = "",
    ref: str = "",
    description: str = "",
    timeline: Optional[List[str]] = None,
    escalated_blocker_id: str = "",
    project_root: Optional[Path] = None,
) -> str:
    """Build a spec-compliant issue markdown file."""
    now = datetime.now().isoformat()
    emoji = get_status_emoji(project_root).get(status, "🔓") if project_root else "🔓"

    owner_sla = ""
    sla_hours = None
    if project_root:
        owner_sla, sla_hours = get_queue_sla(project_root).get(queue, ("", None))

    sla_deadline = ""
    if sla_hours is not None:
        sla_dt = datetime.fromisoformat(now) + timedelta(hours=sla_hours)
        sla_deadline = sla_dt.isoformat()

    owner_field = owner or owner_sla

    lines = [
        f"# [{issue_id}] {title}",
        "",
        f"**发起方：** @{owner_field}",
        f"**处理方：** @{owner_field}",
        f"**创建时间：** {now}",
        f"**状态：** {emoji} {'open' if status == 'open' else status}",
        f"**SLA 截止：** {sla_deadline}",
        f"**队列：** {queue}",
    ]
    if ref:
        lines.append(f"**关联 Issue：** [{ref}](#)")
    if escalated_blocker_id:
        lines.append(f"** escalated_blocker_id：** {escalated_blocker_id}")
    lines.extend(["", "---", ""])

    lines.extend(["## 问题描述", "", description or title, ""])
    lines.extend(["## 关联上下文", ""])
    if ref:
        lines.append(f"- 关联 Issue：{ref}")
    lines.extend(["", "## 处理记录", ""])
    timeline = timeline or []
    for entry in timeline:
        lines.append(f"- [{now}] @{owner_field}: {entry}")
    lines.append(f"- [{now}] @{owner_field}: 创建")

    return "\n".join(lines)


def parse_issue_file(path: Path) -> Dict[str, Any]:
    """Parse spec-format issue markdown file."""
    content = path.read_text("utf-8", errors="replace")
    data = {
        "path":               str(path),
        "raw":                content,
        "id":                 "",
        "queue":              "",
        "title":              "",
        "status":             "open",
        "owner":              "",
        "ref":                "",
        "escalated_blocker_id": "",
        "created":            "",
        "sla_deadline":       "",
        "description":        "",
        "context":            "",
        "timeline":           [],
    }

    first_line = content.splitlines()[0] if content else ""
    m = re.match(r"#\s+\[([^\]]+)\]\s+(.+)", first_line)
    if m:
        data["id"] = m.group(1)
        data["title"] = m.group(2).strip()

    for line in content.splitlines():
        m = re.match(r"\*\*([^：]+)：\*\*\s*(.+)", line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            key_map = {
                "发起方":            "owner",
                "处理方":            "owner",
                "创建时间":          "created",
                "状态":              "status",
                "SLA 截止":          "sla_deadline",
                "队列":              "queue",
                "关联 Issue":        "ref",
                "escalated_blocker_id": "escalated_blocker_id",
            }
            if key in key_map:
                data[key_map[key]] = val
            if key == "状态":
                data["status"] = re.sub(r"^[^\s]+\s*", "", val).strip()

    sections = {}
    current = None
    body_lines = []
    for line in content.splitlines()[1:]:
        sm = re.match(r"##\s+(.+)", line)
        if sm:
            if current:
                sections[current] = "\n".join(body_lines).strip()
            current = sm.group(1).strip()
            body_lines = []
        else:
            body_lines.append(line)
    if current:
        sections[current] = "\n".join(body_lines).strip()

    data["description"] = sections.get("问题描述", "")
    data["context"] = sections.get("关联上下文", "")
    timeline_str = sections.get("处理记录", "")
    data["timeline"] = [
        l.strip() for l in timeline_str.splitlines() if l.strip().startswith("- [")
    ]

    return data


def read_issue(project_root: Path, issue_id: str) -> Optional[Dict[str, Any]]:
    """Find and read issue by its ID across all queues."""
    mai = get_mai_dir(project_root)
    if not (mai / "queues").exists():
        return None
    for queue_dir in (mai / "queues").iterdir():
        if not queue_dir.is_dir():
            continue
        clean_id = issue_id.strip()
        for f in queue_dir.glob("*.md"):
            data = parse_issue_file(f)
            if data["id"] == clean_id:
                data["queue"] = queue_dir.name
                return data
    return None


def issue_file_path(project_root: Path, queue: str, issue_id: str) -> Path:
    return get_mai_dir(project_root) / "queues" / queue / f"{issue_id}.md"


# ─────────────────────────────────────────────
# Issue Commands
# ─────────────────────────────────────────────

def cmd_issue_new(project_root: Path, queue: str, title: str, ref: Optional[str]):
    from .mai import out, err, ensure_mai_structure
    queue_sla = get_queue_sla(project_root)
    if queue not in queue_sla:
        err(f"Unknown queue: {queue}. Valid: {list(queue_sla.keys())}", 1, error="INVALID_QUEUE")

    ensure_mai_structure(project_root)
    issue_id = next_issue_id(project_root, queue)
    owner, _ = queue_sla[queue]

    content = make_issue_content(
        issue_id=issue_id,
        queue=queue,
        title=title,
        status="open",
        owner=owner,
        ref=ref or "",
        project_root=project_root,
    )

    if GLOBAL.dry_run:
        out(f"[dry-run] Would create Issue {issue_id} in queue '{queue}'",
            command="issue new", issue_id=issue_id, queue=queue, owner=owner)
        return

    fpath = issue_file_path(project_root, queue, issue_id)
    if fpath.exists():
        err(f"Issue {issue_id} already exists", 1, error="ALREADY_EXISTS")

    fpath.write_text(content, encoding="utf-8")
    sync_to_async(fpath, project_root)
    write_history(project_root, "system", "issue_new",
                  f"Issue {issue_id} created in {queue}: {title}", "open")

    out(f"Issue {issue_id} created in queue '{queue}'",
        command="issue new", issue_id=issue_id, queue=queue, owner=owner)


def cmd_issue_amend(project_root: Path, issue_id: str, remark: str):
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    mai = get_mai_dir(project_root)
    dec_dir = mai / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    dec_file = dec_dir / f"{issue_id}.md"

    now = datetime.now().isoformat()
    amend_entry = (
        f"\n## 修订记录 @ {now}\n\n"
        f"**修订人：** system\n"
        f"**备注：** {remark}\n"
        f"**状态：** 已修订\n"
    )

    if not GLOBAL.dry_run:
        if dec_file.exists():
            dec_file.write_text(dec_file.read_text("utf-8") + amend_entry)
        else:
            dec_file.write_text(f"# 修订记录 - Issue {issue_id}\n{amend_entry}")
        sync_to_async(dec_file, project_root)

        fpath = Path(issue["path"])
        content = fpath.read_text("utf-8")
        content = re.sub(r"\*\*状态：\*\*.*", f"**状态：** ⚠️ 已修订", content)
        fpath.write_text(content, encoding="utf-8")
        sync_to_async(fpath, project_root)
        write_history(project_root, "system", "issue_amend",
                      f"Issue {issue_id} amended: {remark}", "amended")

    out(f"Issue {issue_id} amended.", command="issue amend", issue_id=issue_id)


def cmd_issue_claim(project_root: Path, issue_id: str):
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    lock_info = check_lock(project_root, issue_id)
    if lock_info and lock_info["holder"] == agent and not lock_info["stale"]:
        out(f"Issue {issue_id} already claimed by you.",
            command="issue claim", issue_id=issue_id, holder=agent)
        return

    if not acquire_lock(project_root, issue_id, agent):
        lock_info = check_lock(project_root, issue_id)
        ttl = 0
        if lock_info:
            ttl = round((lock_info["threshold_seconds"] - lock_info["age_seconds"]) / 60, 1)
        err(
            f"Issue {issue_id} is locked by {lock_info['holder'] if lock_info else 'another agent'} "
            f"(TTL: {ttl} min).",
            2, error="LOCK_HELD",
            holder=lock_info["holder"] if lock_info else "unknown",
            ttl_minutes=ttl
        )

    if not GLOBAL.dry_run:
        fpath = Path(issue["path"])
        content = fpath.read_text("utf-8")
        content = re.sub(r"\*\*状态：\*\*.*", "**状态：** 🔄 进行中", content)
        fpath.write_text(content, encoding="utf-8")
        sync_to_async(fpath, project_root)
        write_history(project_root, agent, "issue_claim", f"Issue {issue_id} claimed", "claimed")

    out(f"Issue {issue_id} claimed by {agent}.",
        command="issue claim", issue_id=issue_id, holder=agent)


def cmd_issue_complete(project_root: Path, issue_id: str, conclusion: str):
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)

        mai = get_mai_dir(project_root)
        dec_dir = mai / "decisions"
        dec_file = dec_dir / f"{issue_id}.md"
        now = datetime.now().isoformat()
        complete_entry = (
            f"\n## 结论 @ {now}\n\n"
            f"**结论：** {conclusion}\n"
            f"**处理人：** {agent}\n"
        )
        if dec_file.exists():
            dec_file.write_text(dec_file.read_text("utf-8") + complete_entry)
        else:
            dec_file.write_text(f"# 结论 - Issue {issue_id}\n{complete_entry}")
        sync_to_async(dec_file, project_root)

        fpath = Path(issue["path"])
        content = fpath.read_text("utf-8")
        content = re.sub(r"\*\*状态：\*\*.*", "**状态：** ✅ 完成", content)
        content = re.sub(
            r"## 处理记录",
            f"## 处理记录\n- [{now}] @{agent}: 完成：{conclusion}",
            content
        )
        fpath.write_text(content, encoding="utf-8")
        sync_to_async(fpath, project_root)

        write_history(project_root, agent, "issue_complete",
                      f"Issue {issue_id} completed: {conclusion}", "complete")

    out(f"Issue {issue_id} completed.", command="issue complete", issue_id=issue_id)


def cmd_issue_escalate(project_root: Path, issue_id: str):
    """
    Per §七·P2-1: Create new issue in architect-reviews-designer queue,
    filling the escalation template with original issue content.
    """
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    queue = "architect-reviews-designer"
    new_id = next_issue_id(project_root, queue)

    desc = issue.get("description", issue.get("title", ""))
    content = make_issue_content(
        issue_id=new_id,
        queue=queue,
        title=f"⚠️ [冲突升级] {issue['title']}",
        status="open",
        owner="architect",
        ref=issue_id,
        description=(
            f"## 核心分歧\n\n<由设计师/architect填写>\n\n"
            f"## 立场 A\n\n<Agent A 的主张 + 依据>\n\n"
            f"## 立场 B\n\n<Agent B 的主张 + 依据>\n\n"
            f"## 客观数据（如有）\n\n<可量化的事实>\n\n"
            f"## 原始 Issue 内容\n\n"
            f"原始 Issue：{issue_id}\n"
            f"队列：{issue.get('queue', '')}\n"
            f"描述：{desc}\n"
        ),
    )

    if not GLOBAL.dry_run:
        fpath = issue_file_path(project_root, queue, new_id)
        fpath.write_text(content, encoding="utf-8")
        sync_to_async(fpath, project_root)
        write_history(project_root, agent, "issue_escalate",
                      f"Issue {issue_id} escalated → {new_id} in {queue}", "escalated")

    out(f"Issue {issue_id} escalated → {new_id} in {queue}.",
        command="issue escalate", original_id=issue_id, new_id=new_id, queue=queue)
