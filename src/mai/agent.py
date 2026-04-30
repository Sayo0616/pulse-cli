"""Mai CLI - Agent management module.

"""

import re
from pathlib import Path
from .config import load_config, save_config, get_mai_dir, GLOBAL
from .project import ensure_mai_structure

def cmd_agent_add(project_root: Path, name: str, heartbeat_minutes: int = 30):
    """Register a new agent and create its default task queue.
    
    REQ-004:
    - Name normalization (lower, space -> -)
    - Regex validation (a-z, 0-9, -)
    - Default queue: <name>-tasks
    """
    from .mai import out, err

    # 1. Normalize and Validate Name
    normalized_name = name.lower().strip().replace(" ", "-")
    if not normalized_name:
        err("Agent name cannot be empty.", 1, error="INVALID_NAME")

    if not re.match(r"^[a-z0-9-]+$", normalized_name):
        err(f"Invalid agent name: '{normalized_name}'. Only a-z, 0-9, and '-' are allowed.", 1, error="INVALID_NAME")
    
    if len(normalized_name) > 32:
        err("Agent name too long (max 32 chars).", 1, error="NAME_TOO_LONG")

    # 2. Load Config and Check Duplicate
    config = load_config(project_root)
    agents = config.get("agents", {})
    if normalized_name in agents:
        err(f"Agent '{normalized_name}' already exists.", 1, error="ALREADY_EXISTS", hint="Run 'mai agent list' to see all registered agents.")

    # 3. Register Agent
    agents[normalized_name] = {"heartbeat_minutes": heartbeat_minutes}
    config["agents"] = agents

    # 4. Create Default Queue
    queues = config.get("queues", {})
    q_name = normalized_name

    # Generate id_prefix: first 3 chars upper, or all if < 3
    prefix = normalized_name[:3].upper()    
    queues[q_name] = {
        "handler": normalized_name,
        "sla_minutes": None,
        "id_prefix": prefix
    }
    config["queues"] = queues

    # 5. Save and Ensure Structure
    if GLOBAL.dry_run:
        out(f"[dry-run] Would register agent '{normalized_name}' and create queue '{q_name}'", 
            command="agent add", agent=normalized_name, queue=q_name)
        return

    save_config(project_root, config)
    ensure_mai_structure(project_root)

    # 6. Update Global Registry
    from .project_registry import add_project
    add_project(
        name=project_root.name,
        path=str(project_root.resolve()),
        description=f"Mai Project {project_root.name}",
        agents=list(config["agents"].keys())
    )

    out(f"Agent '{normalized_name}' registered successfully.", command="agent add", agent=normalized_name)
    out(f"Default queue created: {q_name} (Prefix: {prefix})")


def cmd_agent_list(project_root: Path):
    """3a: List all registered agents."""
    from .mai import out, out_json
    config = load_config(project_root)
    agents = config.get("agents", {})

    if GLOBAL.format == "json":
        out_json({"ok": True, "command": "agent list", "agents": agents})
    else:
        out(f"\n## Registered Agents")
        if not agents:
            out("  (no agents registered)")
        for name, info in agents.items():
            hb = info.get("heartbeat_minutes", 30)
            out(f"  - {name:15} (Heartbeat: {hb}m)")
