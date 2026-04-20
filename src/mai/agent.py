"""Mai CLI - Agent management module.

"""

import re
from pathlib import Path
from .config import load_config, save_config, get_mai_dir
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
        err(f"Agent '{normalized_name}' already exists.", 1, error="ALREADY_EXISTS")

    # 3. Register Agent
    agents[normalized_name] = {"heartbeat_minutes": heartbeat_minutes}
    config["agents"] = agents

    # 4. Create Default Queue
    queues = config.get("queues", {})
    q_name = f"{normalized_name}-tasks"
    
    # Generate id_prefix: first 3 chars upper, or all if < 3
    prefix = normalized_name[:3].upper()
    
    queues[q_name] = {
        "handler": normalized_name,
        "sla_minutes": None,
        "id_prefix": prefix
    }
    config["queues"] = queues

    # 5. Save and Ensure Structure
    save_config(project_root, config)
    ensure_mai_structure(project_root)

    out(f"Agent '{normalized_name}' registered successfully.", command="agent add", agent=normalized_name)
    out(f"Default queue created: {q_name} (Prefix: {prefix})")
