"""Mai CLI - Project management module.
"""

import shutil
import os
import getpass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    find_project_root, get_mai_dir, get_async_dir,
    get_queue_sla, load_config, save_config, GLOBAL,
    DEFAULT_QUEUES, DEFAULT_AGENTS, DEFAULT_DAILY_ORDER, DEFAULT_EMOJI,
)
from .sync import sync_to_async
from .permission import check_project_permission
from .project_registry import add_project, remove_project


def ensure_mai_structure(project_root: Path):
    """Create all required .mai/ and async/ subdirectories."""
    if GLOBAL.dry_run:
        return
    mai = get_mai_dir(project_root)
    (mai / "queues").mkdir(parents=True, exist_ok=True)
    (mai / "processing").mkdir(parents=True, exist_ok=True)
    (mai / "locks").mkdir(parents=True, exist_ok=True)
    (mai / "decisions").mkdir(parents=True, exist_ok=True)
    (mai / "history").mkdir(parents=True, exist_ok=True)
    (mai / "events").mkdir(parents=True, exist_ok=True)
    (mai / "daily-summary").mkdir(parents=True, exist_ok=True)

    async_dir = get_async_dir(project_root)
    async_dir.mkdir(parents=True, exist_ok=True)

    queue_sla = get_queue_sla(project_root)
    for q in queue_sla:
        (mai / "queues" / q).mkdir(parents=True, exist_ok=True)
        (async_dir / q).mkdir(parents=True, exist_ok=True)


def cmd_project_init(project_name: str, operator: str = None):
    """Initialize a new project with Mai directory structure (v1.10.0)."""
    from .mai import out, err

    # 1. Determine project root
    if project_name == "." or isinstance(project_name, Path):
        project_root = Path(project_name).resolve()
    else:
        project_root = find_project_root(project_name)
        if project_root is None:
            projects_dir = Path.home() / ".openclaw" / "workspace" / "projects" / project_name
            if not GLOBAL.dry_run:
                projects_dir.mkdir(parents=True, exist_ok=True)
                agents_file = projects_dir / "AGENTS.md"
                if not agents_file.exists():
                    agents_file.write_text(f"# {project_name}\n\n协作项目于 {datetime.now().isoformat()} 初始化。\n")
            project_root = projects_dir

    # 2. Check Permission (Root Only)
    if not operator:
        err("Operator parameter is strictly required for project init.", 1, error="MISSING_OPERATOR")

    if not check_project_permission(project_root, operator, "init"):
        err(f"权限不足：只有 root 用户可以初始化项目。当前用户: '{operator}'", 3, error="PERMISSION_DENIED")

    # 3. Check if already initialized — check .mai/config.json existence first
    mai_dir = get_mai_dir(project_root)
    cfg_file = mai_dir / "config.json"
    if cfg_file.exists():
        existing = load_config(project_root)
        if existing.get("initialized_at"):
            err(f"项目 '{project_root}' 已经初始化，禁止重复操作。", 1, error="ALREADY_INITIALIZED")

    if GLOBAL.dry_run:
        out(f"[dry-run] Would initialize project structure in '{project_root}'", command="project init", project_root=str(project_root))
        return

    # 4. Create structure and save config
    ensure_mai_structure(project_root)

    new_config = {}
    if cfg_file.exists():
        new_config = load_config(project_root)
    new_config["name"] = project_root.name
    new_config["initialized_at"] = datetime.now().isoformat()
    new_config["queues"] = DEFAULT_QUEUES
    new_config["agents"] = DEFAULT_AGENTS
    new_config["daily_summary_order"] = DEFAULT_DAILY_ORDER
    new_config["issue_status_emoji"] = DEFAULT_EMOJI
    new_config["root"] = new_config.get("root", [])

    save_config(project_root, new_config)
    sync_to_async(cfg_file, project_root)

    # 5. Register in Global Registry
    add_project(
        name=project_root.name,
        path=str(project_root),
        description=f"Mai Project {project_root.name}",
        agents=list(new_config["agents"].keys())
    )

    out(f"Project '{project_root.name}' initialized at {project_root}.", command="project init")


def cmd_project_delete(project_name: str, operator: str = None):
    """Delete a mai project. Root only."""
    from .mai import out, err

    # Try to find by name in registry or as path
    project_root = None
    from .project_registry import list_projects
    for p in list_projects():
        if p["name"] == project_name:
            project_root = Path(p["path"])
            break

    if not project_root:
        project_root = find_project_root(project_name)

    if not project_root or not project_root.exists():
        err(f"Project '{project_name}' not found.", 1, error="NOT_FOUND")

    # Check Permission (Root Only)
    if not operator:
        err("Operator parameter is strictly required for project delete.", 1, error="MISSING_OPERATOR")

    if not check_project_permission(project_root, operator, "delete_project"):
        err(f"权限不足：只有 root 用户可以删除项目。当前用户: '{operator}'", 3, error="PERMISSION_DENIED")

    if GLOBAL.dry_run:
        out(f"[dry-run] Would delete project '{project_name}' at '{project_root}'", command="project delete")
        return

    # Delete physical first — if this fails, registry stays intact
    project_name_resolved = project_root.name
    try:
        shutil.rmtree(project_root)
    except Exception as e:
        err(f"Failed to delete project directory: {e}", 1, error="DELETE_FAILED")

    # Only unregister after successful physical delete
    remove_project(project_name_resolved)
    out(f"Project '{project_name}' deleted successfully.", command="project delete")
