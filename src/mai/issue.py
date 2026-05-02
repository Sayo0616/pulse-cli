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
from .permission import check_permission, check_project_permission


def _check_permission_or_err(project_root: Path, operator: str, action: str, issue: Optional[Dict[str, Any]] = None):
    from .mai import err
    if not check_permission(project_root, operator, action, issue):
        err(f"权限不足：用户 '{operator}' 无权执行 '{action}' 操作。", 3, error="PERMISSION_DENIED")


def _ensure_not_discarded(issue: Dict[str, Any], action: str = "modify"):
    """Check that issue is not in DISCARDED terminal state."""
    from .mai import err
    if issue.get("status", "").upper() == "DISCARDED":
        err(f"无法{action}：工单 {issue['id']} 已废弃（DISCARDED），不可修改。", 1, error="ISSUE_DISCARDED")


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
    timeline: Optional[List[Dict[str, str]]] = None,
    escalated_blocker_id: str = "",
    project_root: Optional[Path] = None,
    priority: str = "P2",
    operator: str = "unknown",
) -> str:
    """Build a spec-compliant issue markdown file (v2.0.0) with structured MDX tags."""
    now = datetime.now().isoformat()
    from .config import DEFAULT_EMOJI
    if project_root:
        emoji = get_status_emoji(project_root).get(status.lower(), "❓")
    else:
        emoji = DEFAULT_EMOJI.get(status.lower(), "❓")

    priority_map = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}
    p_emoji = priority_map.get(priority.upper(), "🟢")
    priority_field = f"{p_emoji} {priority.upper()}"

    owner_sla, sla_hours = "", None
    if project_root:
        owner_sla, sla_hours = get_queue_sla(project_root).get(queue, ("", None))

    sla_deadline = ""
    if sla_hours is not None:
        sla_dt = datetime.fromisoformat(now) + timedelta(hours=sla_hours)
        sla_deadline = sla_dt.isoformat()

    owner_field = owner or owner_sla

    # Timeline structure: List[Dict[str, str]] with keys: time, agent, action, remark
    if not timeline:
        timeline = [{"time": now, "agent": operator, "action": "创建", "remark": ""}]

    timeline_xml = ["<mai_timeline>"]
    for entry in timeline:
        remark = entry.get("remark", "").strip()
        timeline_xml.append(f'<action time="{entry["time"]}" agent="{entry["agent"]}" action="{entry["action"]}">')
        if remark:
            timeline_xml.append(remark)
        timeline_xml.append("</action>")
    timeline_xml.append("</mai_timeline>")

    content = f"""# [{issue_id}] {title}

<mai_meta>
id: {issue_id}
title: {title}
status: {status}
priority: {priority}
owner: {owner_field}
queue: {queue}
created: {now}
sla_deadline: {sla_deadline}
ref: {ref}
escalated_blocker_id: {escalated_blocker_id}
</mai_meta>

**处理方：** @{owner_field} | **优先级：** {priority_field} | **状态：** {emoji} {status.upper()}

---

## 问题描述
<mai_desc>
{description or title}
</mai_desc>

## 关联上下文
<mai_context>
{f"- 关联 Issue：{ref}" if ref else ""}
</mai_context>

## 处理记录
{"".join(timeline_xml)}
"""
    return content


def parse_issue_file(path: Path) -> Dict[str, Any]:
    """Parse structured MDX issue markdown file."""
    content = path.read_text("utf-8", errors="replace")
    data = {
        "path":               str(path),
        "raw":                content,
        "id":                 "",
        "queue":              "",
        "title":              "",
        "status":             "open",
        "priority":           "P2",
        "owner":              "",
        "ref":                "",
        "escalated_blocker_id": "",
        "created":            "",
        "sla_deadline":       "",
        "description":        "",
        "context":            "",
        "timeline":           [],
    }

    # 1. Parse Meta
    meta_match = re.search(r"<mai_meta>(.*?)</mai_meta>", content, re.DOTALL)
    if meta_match:
        meta_content = meta_match.group(1).strip()
        for line in meta_content.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                key_map = {
                    "id": "id",
                    "title": "title",
                    "status": "status",
                    "priority": "priority",
                    "owner": "owner",
                    "queue": "queue",
                    "created": "created",
                    "sla_deadline": "sla_deadline",
                    "ref": "ref",
                    "escalated_blocker_id": "escalated_blocker_id"
                }
                k_clean = k.strip()
                if k_clean in key_map:
                    data[key_map[k_clean]] = v.strip()

    # 2. Parse Description
    desc_match = re.search(r"<mai_desc>(.*?)</mai_desc>", content, re.DOTALL)
    if desc_match:
        data["description"] = desc_match.group(1).strip()

    # 3. Parse Context
    ctx_match = re.search(r"<mai_context>(.*?)</mai_context>", content, re.DOTALL)
    if ctx_match:
        data["context"] = ctx_match.group(1).strip()

    # 4. Parse Timeline
    timeline_match = re.search(r"<mai_timeline>(.*?)</mai_timeline>", content, re.DOTALL)
    if timeline_match:
        tl_content = timeline_match.group(1).strip()
        # Find all <action ...>...</action> blocks
        action_matches = re.finditer(r'<action\s+([^>]+)>\s*(.*?)\s*</action>', tl_content, re.DOTALL)
        for m in action_matches:
            attr_str = m.group(1)
            remark = m.group(2).strip()
            
            # Use separate regex to find attributes (order independent)
            time_m = re.search(r'time="([^"]+)"', attr_str)
            agent_m = re.search(r'agent="([^"]+)"', attr_str)
            action_m = re.search(r'action="([^"]+)"', attr_str)
            
            data["timeline"].append({
                "time": time_m.group(1) if time_m else "",
                "agent": agent_m.group(1) if agent_m else "",
                "action": action_m.group(1) if action_m else "",
                "remark": remark
            })

    # --- Fallback for old format (v1.x) ---
    if not meta_match:
        lines = content.splitlines()
        if lines:
            # Parse ID and Title from first line: # [ID] Title
            m = re.match(r"#\s+\[([^\]]+)\]\s+(.+)", lines[0])
            if m:
                data["id"] = m.group(1)
                data["title"] = m.group(2).strip()
            
            # Parse meta lines: **Key：** Value
            for line in lines:
                m = re.match(r"\*\*([^：]+)：\*\*\s*(.+)", line)
                if m:
                    key, val = m.group(1).strip(), m.group(2).strip()
                    if val.startswith("@"): val = val[1:]
                    
                    key_map = {
                        "处理方": "owner", "优先级": "priority", "创建时间": "created",
                        "状态": "status", "SLA 截止": "sla_deadline", "队列": "queue", "关联 Issue": "ref"
                    }
                    if key in key_map:
                        data[key_map[key]] = val
                    if key == "状态":
                        parts = val.split(maxsplit=1)
                        data["status"] = (parts[1] if len(parts) > 1 else parts[0]).upper()
                    if key == "优先级":
                        parts = val.split(maxsplit=1)
                        data["priority"] = parts[1] if len(parts) > 1 else parts[0]

            # Parse Description (everything between ## 问题描述 and next ## or end)
            desc_part = re.search(r"## 问题描述\s+(.*?)(?=\n##|$)", content, re.DOTALL)
            if desc_part: data["description"] = desc_part.group(1).strip()
            
            # Parse Context
            ctx_part = re.search(r"## 关联上下文\s+(.*?)(?=\n##|$)", content, re.DOTALL)
            if ctx_part: data["context"] = ctx_part.group(1).strip()

            # Parse Timeline (Old style list)
            tl_part = re.search(r"## 处理记录\s+(.*)", content, re.DOTALL)
            if tl_part:
                for line in tl_part.group(1).splitlines():
                    tm = re.match(r"^\s*-\s*\[([^\]]+)\]\s+@([^:]+):\s*(.*)", line)
                    if tm:
                        data["timeline"].append({
                            "time": tm.group(1),
                            "agent": tm.group(2).strip(),
                            "action": tm.group(3).strip().split("：", 1)[0],
                            "remark": tm.group(3).strip().split("：", 1)[1] if "：" in tm.group(3) else ""
                        })
    # --------------------------------------

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


def _update_issue_file(project_root: Path, data: Dict[str, Any], status: str, remark: Optional[str] = None, new_owner: Optional[str] = None, operator: Optional[str] = None):
    """Helper to update issue file status, timeline and optionally owner (v2.0.0)."""
    if GLOBAL.dry_run:
        return

    now = datetime.now().isoformat()
    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    if agent.startswith("@"):
        agent = agent[1:]
    emoji = get_status_emoji(project_root).get(status.lower(), "❓")

    fpath = Path(data["path"])
    content = fpath.read_text("utf-8")

    # --- Migration: If old format, re-write as new format ---
    if "<mai_meta>" not in content:
        # data already contains parsed info from parse_issue_file (via read_issue)
        # We need to make sure we use the most recent status and remark
        # First, ensure timeline is updated in data dict
        if "timeline" not in data:
            data["timeline"] = []
        
        if remark:
            data["timeline"].append({"time": now, "agent": agent, "action": status.upper(), "remark": remark})
        else:
            data["timeline"].append({"time": now, "agent": agent, "action": status.upper(), "remark": ""})
        
        # Build new content
        new_content = make_issue_content(
            issue_id=data["id"],
            queue=data.get("queue", "unknown"),
            title=data.get("title", "Untitled"),            status=status,
            owner=new_owner or data.get("owner", ""),
            ref=data.get("ref", ""),
            description=data.get("description", ""),
            timeline=data["timeline"],
            escalated_blocker_id=data.get("escalated_blocker_id", ""),
            project_root=project_root,
            priority=data.get("priority", "P2"),
            operator=agent
        )
        fpath.write_text(new_content, encoding="utf-8")
        sync_to_async(fpath, project_root)
        write_history(project_root, agent, f"issue_{status.lower()}",
                    f"Issue {data['id']} status changed to {status} (migrated to v2)", status.lower())
        return
    # -----------------------------------------------------

    # 1. Update status in meta
    content = re.sub(r"(<mai_meta>.*?status:)\s*[^\n]+", r"\1 " + status, content, flags=re.DOTALL)
    # 2. Update owner in meta if provided
    if new_owner is not None:
        if new_owner.startswith("@"):
            new_owner = new_owner[1:]
        content = re.sub(r"(<mai_meta>.*?owner:)\s*[^\n]+", r"\1 " + new_owner, content, flags=re.DOTALL)

    # 3. Update human-readable status line
    content = re.sub(r"\*\*状态：\*\*\s*[^\n]+", f"**状态：** {emoji} {status.upper()}", content)
    if new_owner is not None:
        content = re.sub(r"\*\*处理方：\*\*\s*[^\n]+", f"**处理方：** @{new_owner}", content)

    # 4. Append to timeline
    remark_text = f"\n{remark.strip()}\n" if remark and remark.strip() else ""
    new_action = f'<action time="{now}" agent="{agent}" action="{status.upper()}">{remark_text}</action>'
    
    # Inject before </mai_timeline>
    content = re.sub(r"(</mai_timeline>)", f"{new_action}\n\\1", content)

    fpath.write_text(content, encoding="utf-8")
    sync_to_async(fpath, project_root)
    write_history(project_root, agent, f"issue_{status.lower()}",
                  f"Issue {data['id']} status changed to {status}", status.lower())

# ─────────────────────────────────────────────
# Issue Commands
# ─────────────────────────────────────────────

def cmd_issue_new(project_root: Path, queue: str, title: str, ref: Optional[str], priority: str = "P2", operator: Optional[str] = None):
    from .mai import out, err, suggest
    from .project import ensure_mai_structure
    queue_sla = get_queue_sla(project_root)
    if queue not in queue_sla:
        hint = suggest(queue, list(queue_sla.keys()), "mai queue check")
        err(f"Unknown queue: {queue}.", 1, error="INVALID_QUEUE", hint=hint)

    # REQ-A/B: Resolve operator if not provided (for direct function calls in tests)
    if operator is None:
        import os
        operator = os.environ.get("MAI_OPERATOR") or os.environ.get("MAI_AGENT") or os.environ.get("AGENT_NAME")

    # REQ-B: Permission check for create
    _check_permission_or_err(project_root, operator, "create", issue={"queue": queue})

    ensure_mai_structure(project_root)
    issue_id = next_issue_id(project_root, queue)
    owner, _ = queue_sla[queue]
    agent = operator or "unknown"
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
        priority=priority,
        operator=agent,
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


def cmd_issue_claim(project_root: Path, issue_id: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))

    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check for claim
    _check_permission_or_err(project_root, agent, "claim", issue=issue)
    _ensure_not_discarded(issue, "认领")

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

    _update_issue_file(project_root, issue, "IN_PROGRESS", new_owner=agent, operator=agent)
    out(f"Issue {issue_id} claimed by {agent} (Status: IN_PROGRESS).",
        command="issue claim", issue_id=issue_id, holder=agent)


def cmd_issue_block(project_root: Path, issue_id: str, reason: str, operator: Optional[str] = None):
    """REQ-008: Mark issue as BLOCKED."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, operator, "block", issue=issue)
    _ensure_not_discarded(issue, "阻塞")

    _update_issue_file(project_root, issue, "BLOCKED", remark=reason, operator=operator)
    out(f"Issue {issue_id} is now BLOCKED: {reason}", command="issue block", issue_id=issue_id)


def cmd_issue_unblock(project_root: Path, issue_id: str, operator: Optional[str] = None):
    """REQ-008: Restore issue from BLOCKED to IN_PROGRESS."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, operator, "unblock", issue=issue)

    if issue["status"].upper() != "BLOCKED":
        out(f"Issue {issue_id} is not blocked (Current: {issue['status']}).", command="issue unblock", idempotent=True)
        return

    _update_issue_file(project_root, issue, "IN_PROGRESS", operator=operator)
    out(f"Issue {issue_id} unblocked (Status: IN_PROGRESS).", command="issue unblock", issue_id=issue_id)


def cmd_issue_complete(project_root: Path, issue_id: str, conclusion: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, agent, "complete", issue=issue)
    _ensure_not_discarded(issue, "完成")

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

        _update_issue_file(project_root, issue, "COMPLETED", remark=conclusion or "已确认完成", operator=agent)

    out(f"Issue {issue_id} completed.", command="issue complete", issue_id=issue_id, dry_run=GLOBAL.dry_run)


def cmd_issue_reopen(project_root: Path, issue_id: str, reason: str, operator: Optional[str] = None) -> None:
    """REQ-017: Reopen a COMPLETED issue."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, operator, "reopen", issue=issue)
    _ensure_not_discarded(issue, "重新打开")

    if issue["status"].upper() == "OPEN":
        out(f"Issue {issue_id} is already OPEN.", command="issue reopen", idempotent=True)
        return

    _update_issue_file(project_root, issue, "OPEN", remark=f"重新打开：{reason}", operator=operator)
    out(f"Issue {issue_id} reopened (Status: OPEN).", command="issue reopen", issue_id=issue_id, dry_run=GLOBAL.dry_run)


def cmd_issue_status(project_root: Path, issue_id: str) -> None:
    """REQ-008: Show issue status history (v2.0.0)."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    out(f"Status History for {issue_id}:")
    for entry in issue.get("timeline", []):
        if isinstance(entry, dict):
            out(f"  [{entry.get('time', '')}] @{entry.get('agent', '')}: {entry.get('action', '')}")
            remark = entry.get("remark", "").strip()
            if remark:
                for rline in remark.splitlines():
                    out(f"    {rline}")
        else:
            out(f"  {entry}")


def cmd_issue_amend(project_root: Path, issue_id: str, remark: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, operator, "amend", issue=issue)
    _ensure_not_discarded(issue, "修改")

    _update_issue_file(project_root, issue, "AMENDED", remark=remark, operator=operator)
    out(f"Issue {issue_id} amended.", command="issue amend", issue_id=issue_id)


def cmd_issue_escalate(project_root: Path, issue_id: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, operator, "escalate", issue=issue)
    _ensure_not_discarded(issue, "升级")

    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
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
        priority="P0",
        operator=agent,
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


def cmd_issue_transfer(project_root: Path, issue_id: str, next_handler: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, agent, "transfer", issue=issue)
    _ensure_not_discarded(issue, "转交")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Reopen it first if needed.", 1, error="ALREADY_COMPLETED")

    _check_lock_for_action(project_root, issue_id, agent)

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "OPEN", remark=f"转交给 @{next_handler}", new_owner=next_handler, operator=agent)

    out(f"Issue {issue_id} transferred to {next_handler}.", command="issue transfer", issue_id=issue_id, next_handler=next_handler)


def cmd_issue_confirm(project_root: Path, issue_id: str, operator: Optional[str] = None) -> None:
    # REQ-E: confirm is alias to complete
    cmd_issue_complete(project_root, issue_id, conclusion="已确认完成", operator=operator)


def cmd_issue_reject(project_root: Path, issue_id: str, reason: str, operator: Optional[str] = None) -> None:
    from .mai import out, err
    agent = operator or os.environ.get("MAI_AGENT", os.environ.get("AGENT_NAME", "unknown"))
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found", 1, error="NOT_FOUND")

    # REQ-B: Permission check
    _check_permission_or_err(project_root, agent, "reject", issue=issue)
    _ensure_not_discarded(issue, "退回")

    if issue["status"].upper() == "COMPLETED":
        err(f"Issue {issue_id} is already COMPLETED. Use 'issue reopen' instead.", 1, error="ALREADY_COMPLETED")

    _check_lock_for_action(project_root, issue_id, agent)

    # Find previous owner from timeline (last agent who is not current user)
    # If not found, fallback to queue owner
    queue_sla = get_queue_sla(project_root)
    previous_owner, _ = queue_sla.get(issue.get("queue", ""), ("unknown", None))
    
    timeline = issue.get("timeline", [])
    for entry in reversed(timeline):
        if isinstance(entry, dict):
            entry_agent = entry.get("agent", "").strip()
            if entry_agent and entry_agent != agent:
                previous_owner = entry_agent
                break

    if not GLOBAL.dry_run:
        release_lock(project_root, issue_id)
        _update_issue_file(project_root, issue, "OPEN", remark=f"退回重做：{reason}", new_owner=previous_owner, operator=agent)

    out(f"Issue {issue_id} rejected: {reason}", command="issue reject", issue_id=issue_id, reason=reason)

def cmd_issue_discard(project_root: Path, issue_id: str, reason: str, operator: Optional[str] = None) -> None:
    """New in v1.10.0: Discard an issue. Action for root/owner."""
    from .mai import out, err
    issue = read_issue(project_root, issue_id)
    if not issue:
        err(f"Issue {issue_id} not found.", 1, error="NOT_FOUND")

    agent = operator or os.environ.get("MAI_AGENT", "unknown")
    _check_permission_or_err(project_root, agent, "discard", issue=issue)

    if issue["status"].upper() == "DISCARDED":
        out(f"Issue {issue_id} is already DISCARDED.", command="issue discard", idempotent=True)
        return

    if not GLOBAL.dry_run:
        try:
            release_lock(project_root, issue_id)
        except Exception:
            pass
        _update_issue_file(project_root, issue, "DISCARDED", remark=f"废弃工单：{reason}", operator=agent)

    out(f"Issue {issue_id} discarded: {reason}", command="issue discard", issue_id=issue_id, status="DISCARDED")
