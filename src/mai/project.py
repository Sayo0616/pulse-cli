"""Mai CLI - Project init module.

"""

from datetime import datetime
from pathlib import Path

from .config import (
    find_project_root, get_mai_dir, get_async_dir,
    get_queue_sla, load_config, save_config, GLOBAL,
    DEFAULT_QUEUES, DEFAULT_AGENTS, DEFAULT_DAILY_ORDER, DEFAULT_EMOJI,
)
from .sync import sync_to_async


def ensure_mai_structure(project_root: Path):
    """Create all required .mai/ and async/ subdirectories."""
    mai = get_mai_dir(project_root)
    (mai / "queues").mkdir(parents=True, exist_ok=True)
    (mai / "processing").mkdir(parents=True, exist_ok=True)
    (mai / "locks").mkdir(parents=True, exist_ok=True)
    (mai / "decisions").mkdir(parents=True, exist_ok=True)
    (mai / "history").mkdir(parents=True, exist_ok=True)
    (mai / "events").mkdir(parents=True, exist_ok=True)

    async_dir = get_async_dir(project_root)
    async_dir.mkdir(parents=True, exist_ok=True)

    queue_sla = get_queue_sla(project_root)
    for q in queue_sla:
        (mai / "queues" / q).mkdir(parents=True, exist_ok=True)
        (async_dir / q).mkdir(parents=True, exist_ok=True)


def cmd_project_init(project_name: str, operator: str = None):
    """Initialize a new project with Mai directory structure."""
    if project_name == "." or isinstance(project_name, Path):
        project_root = Path(project_name).resolve()
    else:
        project_root = find_project_root(project_name)
        if project_root is None:
            projects_dir = Path.home() / ".openclaw" / "workspace" / "projects" / project_name
            if not GLOBAL.dry_run:
                projects_dir.mkdir(parents=True, exist_ok=True)
                (projects_dir / "AGENTS.md").write_text(
                    f"# {project_name}\n\n协作项目于 {datetime.now().isoformat()} 初始化。\n"
                )
            project_root = projects_dir

    if not GLOBAL.dry_run:
        # REQ-1.9.2: Check permission for project init
        from .issue import _check_permission_or_err
        from .config import get_roots
        import getpass
        
        # If no operator provided, fallback to OS user for the check
        check_op = operator or getpass.getuser()
        _check_permission_or_err(project_root, check_op, "init")

    ensure_mai_structure(project_root)

    base_config = load_config(project_root)

    if base_config.get("initialized_at"):
        from .mai import out
        out(f"Project '{project_root.name}' already initialized.", command="project init", idempotent=True)
        return

    if GLOBAL.dry_run:
        from .mai import out
        out(f"[dry-run] Would initialize project structure in '{project_root}'", command="project init", project_root=str(project_root))
        return

    if not GLOBAL.dry_run:
        new_config = dict(base_config)
        new_config["name"] = project_root.name
        new_config["initialized_at"] = datetime.now().isoformat()
        new_config["queues"] = DEFAULT_QUEUES
        new_config["agents"] = DEFAULT_AGENTS
        new_config["daily_summary_order"] = DEFAULT_DAILY_ORDER
        new_config["issue_status_emoji"] = DEFAULT_EMOJI
        save_config(project_root, new_config)
        cfg_file = get_mai_dir(project_root) / "config.json"
        sync_to_async(cfg_file, project_root)

    from .mai import out
    out(f"Project '{project_root.name}' initialized at {project_root}.", command="project init")
