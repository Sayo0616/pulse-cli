"""Mai CLI - Issue commands module.

"""

import os
import re
import uuid
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
    
    while True:
        short_hash = uuid.uuid4().hex[:6].upper()
        candidate_id = f"{prefix}-{short_hash}"
        # Ensure ID is globally unique across all queues
        exists = False
        queue_base = get_mai_dir(project_root) / "queues"
        for q_dir in queue_base.iterdir():
            if q_dir.is_dir() and (q_dir / f"{candidate_id}.md").exists():
                exists = True
                break
        if not exists:
            return candidate_id


# ─────────────────────────────────────────────
# Issue File Format
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
    creator: str = "",
) -> str:
    """Build a spec-compliant issue markdown file."""
    now = datetime.now().isoformat()
    from .config import DEFAULT_EMOJI
    if project_root:
        emoji = get_status_emoji(project_root).get(status.lower(), "❓")
    else:
        emoji = DEFAULT_EMOJI.get(status.lower(), "❓")

    owner_sla, sla_hours = "", None
    if project_root:
        owner_sla, sla_hours = get_queue_sla(project_root).get(queue, ("", None))

    sla_deadline = ""
    if sla_hours is not None:
        sla_dt = datetime.fromisoformat(now) + timedelta(hours=sla_hours)
        sla_deadline = sla_dt.isoformat()

    owner_field = owner or owner_sla
    creator_field = creator or owner_field

    lines = [
        f"# [{issue_id}] {title}",
        "",
        f"**发起方：** @{creator_field}",
        f"**处理方：** @{owner_field}",
        f"**创建时间：** {now}",
        f"**状态：** {emoji} {status}",
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
    # Add initial creation entry if timeline is empty
    if not timeline:
        timeline.append(f"[{now}] @{creator_field}: 创建")

    for entry in timeline:
        if entry.startswith("- "):
            lines.append(entry)
        else:
            lines.append(f"- {entry}")

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
        "creator":            "",
        "ref":                "",
        "escalated_blocker_id": "",
        "created":            "",
        "sla_deadline":       "",
        "description":        "",
        "context":            "",
        "timeline":           [],
    }

    lines = content.splitlines()
    if not lines:
        return data

    first_line = lines[0]
    m = re.match(r"#\s+\[([^\]]+)\]\s+(.+)", first_line)
    if m:
        data["id"] = m.group(1)
        data["title"] = m.group(2).strip()

    for line in lines:
        m = re.match(r"\*\*([^：]+)：\*\*\s*(.+)", line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            # Clean @ prefix if exists
            if val.startswith("@"):
                val = val[1:]

            key_map = {
                "发起方":            "creator",
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
                # Extract text after emoji if present. E.g. "⭕ OPEN" -> "OPEN"
                parts = val.split(maxsplit=1)
                data["status"] = parts[1] if len(parts) > 1 else parts[0]

    sections = {}
    current = None
    body_lines = []
    for line in lines[1:]:
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
    
    timeline = []
    current_entry = []
    for line in timeline_str.splitlines():
        if line.strip().startswith("- ["):
            if current_entry:
                timeline.append("\n".join(current_entry))
            current_entry = [line.strip("- ")]
        elif line.strip() and current_entry:
            current_entry.append(line.strip())
    if current_entry:
        timeline.append("\n".join(current_entry))
    data["timeline"] = timeline

    return data


def read_issue(project_root: Path, issue_id: str) -> Optional[Dict[str, Any]]:
    """Find and read issue by its ID across all queues."""
    mai = get_mai_dir(project_root)
    queues_dir = mai / "queues"
    if not queues_dir.exists():
        return None
    for queue_dir in queues_dir.iterdir():
        if not queue_dir.is_dir():
            continue
        clean_id = issue_id.strip()
        f = queue_dir / f"{clean_id}.md"
        if f.exists():
            data = parse_issue_file(f)
            data["queue"] = queue_dir.name
            return data
    return None


def issue_file_path(project_root: Path, queue: str, issue_id: str) -> Path:
    return get_mai_dir(project_root) / "queues" / queue / f"{issue_id}.md"


def _update_issue_file(project_root: Path, data: Dict[str, Any], status: str, remark: Optional[str] = None, new_owner: Optional[str] = None):
    """Helper to update issue file status, timeline and optionally owner."""
    if GLOBAL.dry_run:
        return

    now = datetime.now().isoformat()
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    emoji = get_status_emoji(project_root).get(status.lower(), "❓")

    fpath = Path(data["path"])
    content = fpath.read_text("utf-8")

    # Update status
    content = re.sub(r"^\s*\*\*状态[：:].*", f"**状态：** {emoji} {status}", content, flags=re.MULTILINE)

    # Update owner if provided
    if new_owner is not None:
        if new_owner.startswith("@"):
            new_owner = new_owner[1:]
        content = re.sub(r"^\s*\*\*处理方[：:].*", f"**处理方：** @{new_owner}", content, flags=re.MULTILINE)

    # Update timeline
    timeline_entry = f"[{now}] @{agent}: {status}"
    if remark:
        timeline_entry += f"：{remark}"

    content = re.sub(
        r"## 处理记录",
        f"## 处理记录\n- {timeline_entry}",
        content
    )

    fpath.write_text(content, encoding="utf-8")
    sync_to_async(fpath, project_root)
    write_history(project_root, agent, f"issue_{status.lower()}",
                  f"Issue {data['id']} status changed to {status}", status.lower())

# ─────────────────────────────────────────────
# Issue Commands
# ─────────────────────────────────────────────

def cmd_issue_new(project_root: Path, queue: str, title: str, ref: Optional[str], creator: Optional[str] = None):
    from .mai import out, err, ensure_mai_structure, suggest
    queue_sla = get_queue_sla(project_root)
    if queue not in queue_sla:
        hint = suggest(queue, list(queue_sla.keys()), "mai queue check")
        err(f"Unknown queue: {queue}.", 1, error="INVALID_QUEUE", hint=hint)

    ensure_mai_structure(project_root)
    issue_id = next_issue_id(project_root, queue)
    owner, _ = queue_sla[queue]
    agent = creator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    if agent.startswith("@"):
        agent = agent[1:]

    content = make_issue_content(
        issue_id=issue_id,
        queue=queue,
        title=title,
        status="OPEN",
        owner=owner,
        ref=ref or "",
        project_root=project_root,
        creator=agent,
    )

    if GLOBAL.dry_run:
        out(f"[dry-run] Would create Issue {issue_id} in queue '{queue}'",
            command="issue new", issue_id=issue_id, queue=queue, owner=owner)
        return

    fpath = issue_file_path(project_root, queue, issue_id)
    fpath.write_text(content, encoding="utf-8")
    sync_to_async(fpath, project_root)
    write_history(project_root, agent, "issue_new",
                  f"Issue {issue_id} created in {queue}: {title}", "open")

    out(f"Issue {issue_id} created in queue '{queue}'",
        command="issue new", issue_id=issue_id, queue=queue, owner=owner)


def cmd_issue_claim(project_root: Path, issue_id: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Reopen it first if needed.", 1, error="ALREADY_COMPLETED")

    lock_info = check_lock(project_root, issue_id)
    if lock_info and lock_info["holder"] == agent and not lock_info["stale"]:
        out(f"Issue {issue_id} already claimed by you.",
            command="issue claim", issue_id=issue_id, holder=agent)
        return

    if not acquire_lock(project_root, issue_id, agent):
        lock_info = check_lock(project_root, issue_id)
        ttl = round((lock_info["threshold_seconds"] - lock_info["age_seconds"]) / 60, 1) if lock_info else 0
        err(f"Issue {issue_id} is locked by {lock_info['holder'] if lock_info else 'unknown'} (TTL: {ttl} min).",
            2, error="LOCK_HELD", holder=lock_info["holder"] if lock_info else "unknown", ttl_minutes=ttl)

    _update_issue_file(project_root, issue, "IN_PROGRESS")
    out(f"Issue {issue_id} claimed by {agent} (Status: IN_PROGRESS).",
        command="issue claim", issue_id=issue_id, holder=agent)


def cmd_issue_block(project_root: Path, issue_id: str, reason: str):
    """REQ-008: Mark issue as BLOCKED."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    _update_issue_file(project_root, issue, "BLOCKED", remark=reason)
    out(f"Issue {issue_id} is now BLOCKED: {reason}", command="issue block", issue_id=issue_id)


def cmd_issue_unblock(project_root: Path, issue_id: str):
    """REQ-008: Restore issue from BLOCKED to IN_PROGRESS."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() != "BLOCKED":
        out(f"Issue {issue_id} is not blocked (Current: {issue['status']}).", command="issue unblock", idempotent=True)
        return

    _update_issue_file(project_root, issue, "IN_PROGRESS")
    out(f"Issue {issue_id} unblocked (Status: IN_PROGRESS).", command="issue unblock", issue_id=issue_id)


def cmd_issue_complete(project_root: Path, issue_id: str, conclusion: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        out(f"Issue {issue_id} is already COMPLETED.", command="issue complete", idempotent=True)
        return

    _check_lock_for_action(project_root, issue_id, agent)

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)

        mai = get_mai_dir(project_root)
        dec_dir = mai / "decisions"
        dec_dir.mkdir(parents=True, exist_ok=True)
        dec_file = dec_dir / f"{issue_id}.md"
        now = datetime.now().isoformat()
        complete_entry = f"\n## 结论 @ {now}\n\n**结论：** {conclusion}\n**处理人：** {agent}\n"
        
        if dec_file.exists():
            dec_file.write_text(dec_file.read_text("utf-8") + complete_entry)
        else:
            dec_file.write_text(f"# 结论 - Issue {issue_id}\n{complete_entry}")
        sync_to_async(dec_file, project_root)

        _update_issue_file(project_root, issue, "COMPLETED", remark=f"完成：{conclusion}")

    out(f"Issue {issue_id} completed.", command="issue complete", issue_id=issue_id, dry_run=GLOBAL.dry_run)


def cmd_issue_reopen(project_root: Path, issue_id: str, reason: str) -> None:
    """REQ-017: Reopen a COMPLETED issue."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "OPEN":
        out(f"Issue {issue_id} is already OPEN.", command="issue reopen", idempotent=True)
        return

    _update_issue_file(project_root, issue, "OPEN", remark=f"重新打开：{reason}")
    out(f"Issue {issue_id} reopened (Status: OPEN).", command="issue reopen", issue_id=issue_id, dry_run=GLOBAL.dry_run)


def cmd_issue_status(project_root: Path, issue_id: str) -> None:
    """REQ-008: Show issue status history."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    out(f"Status History for {issue_id}:")
    for entry in issue.get("timeline", []):
        out(f"  {entry}")


def cmd_issue_amend(project_root: Path, issue_id: str, remark: str) -> None:
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    _update_issue_file(project_root, issue, "AMENDED", remark=remark)
    out(f"Issue {issue_id} amended.", command="issue amend", issue_id=issue_id)


def cmd_issue_escalate(project_root: Path, issue_id: str) -> None:
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
        status="OPEN",
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
        project_root=project_root,
    )

    if not GLOBAL.dry_run:
        fpath = issue_file_path(project_root, queue, new_id)
        fpath.write_text(content, encoding="utf-8")
        sync_to_async(fpath, project_root)
        write_history(project_root, agent, "issue_escalate",
                      f"Issue {issue_id} escalated → {new_id} in {queue}", "escalated")

    out(f"Issue {issue_id} escalated → {new_id} in {queue}.",
        command="issue escalate", original_id=issue_id, new_id=new_id, queue=queue)

def _check_lock_for_action(project_root: Path, issue_id: str, agent: str) -> None:
    """Ensure current agent holds the lock or it is unlocked/stale before action."""
    from .mai import err
    li = check_lock(project_root, issue_id)
    if li and li["holder"] != agent and not li["stale"]:
        err(f"Issue {issue_id} is locked by {li['holder']}. Action denied.", 2, error="LOCK_HELD")


def cmd_issue_transfer(project_root: Path, issue_id: str, next_handler: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Reopen it first if needed.", 1, error="ALREADY_COMPLETED")

    _check_lock_for_action(project_root, issue_id, agent)

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "OPEN", remark=f"转交给 @{next_handler}", new_owner=next_handler)

    out(f"Issue {issue_id} transferred to {next_handler}.", command="issue transfer", issue_id=issue_id, next_handler=next_handler)


def cmd_issue_submit_to_creator(project_root: Path, issue_id: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Reopen it first if needed.", 1, error="ALREADY_COMPLETED")

    _check_lock_for_action(project_root, issue_id, agent)

    creator = issue.get("creator")
    if not creator:
        # Robust fallback: find creator from last timeline entry (oldest)
        timeline = issue.get("timeline", [])
        if timeline:
            first_entry = timeline[-1]
            m = re.match(r"^\[.*?\]\s+@([^:]+):", first_entry)
            if m:
                creator = m.group(1).strip()
    
    creator = creator or "unknown"

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "OPEN", remark=f"提交给创建人 @{creator} 确认", new_owner=creator)

    out(f"Issue {issue_id} submitted to creator {creator}.", command="issue submit-to-creator", issue_id=issue_id, creator=creator)


def cmd_issue_confirm(project_root: Path, issue_id: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        out(f"Issue {issue_id} is already COMPLETED.", command="issue confirm", idempotent=True)
        return

    _check_lock_for_action(project_root, issue_id, agent)

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "COMPLETED", remark="已由创建人确认完成")

    out(f"Issue {issue_id} confirmed completed.", command="issue confirm", issue_id=issue_id)


def cmd_issue_reject(project_root: Path, issue_id: str, reason: str) -> None:
    from .mai import out, err
    agent = os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Use 'issue reopen' instead.", 1, error="ALREADY_COMPLETED")

    _check_lock_for_action(project_root, issue_id, agent)

    # Find previous owner from timeline (last agent who is not the creator or current user)
    previous_owner = "unknown"
    creator = issue.get("creator")
    timeline = issue.get("timeline", [])
    for entry in reversed(timeline):
        m = re.match(r"^\[.*?\]\s+@([^:]+):", entry)
        if m:
            entry_agent = m.group(1).strip()
            if entry_agent != agent and entry_agent != creator:
                previous_owner = entry_agent
                break

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "OPEN", remark=f"退回重做：{reason}", new_owner=previous_owner)

    out(f"Issue {issue_id} rejected: {reason}", command="issue reject", issue_id=issue_id, reason=reason)
