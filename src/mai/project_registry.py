"""Mai CLI - Project Registry module.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
try:
    import fcntl
except ImportError:
    fcntl = None

from .global_config import get_global_config_dir

def get_registry_path() -> Path:
    """Return path to global registry.json."""
    return get_global_config_dir() / "registry.json"

def get_registry_lock_path() -> Path:
    """Return path to registry.lock."""
    return get_global_config_dir() / "registry.lock"

def load_registry() -> Dict[str, Any]:
    """Read project registry, returning default if not exists."""
    reg_file = get_registry_path()
    if not reg_file.exists():
        return {"projects": []}
    
    try:
        # We don't necessarily need a lock just for reading, 
        # but let's be safe if we want consistent reads during writes.
        return json.loads(reg_file.read_text("utf-8"))
    except Exception:
        return {"projects": []}

def save_registry(registry: Dict[str, Any]) -> None:
    """Atomically write project registry with cross-platform file locking."""
    config_dir = get_global_config_dir()
    reg_file = get_registry_path()
    lock_file = get_registry_lock_path()

    # Use a separate lock file to coordinate access
    lock_fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        
        # Use a temporary file in the same directory for atomic rename
        fd, temp_path = tempfile.mkstemp(dir=str(config_dir), prefix="registry.json.tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_path, reg_file)
            
            # Set file permissions to 0600
            if os.name != 'nt':
                os.chmod(reg_file, 0o600)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    finally:
        if fcntl:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

def add_project(name: str, path: str, description: str, agents: List[str]) -> None:
    """Register a new project or update existing one."""
    registry = load_registry()
    projects = registry.setdefault("projects", [])
    
    # Update if exists, else append
    for p in projects:
        if p["name"] == name:
            p["path"] = str(Path(path).resolve())
            p["description"] = description
            p["agents"] = list(set(agents))
            p["updated_at"] = datetime.now().isoformat()
            break
    else:
        projects.append({
            "name": name,
            "path": str(Path(path).resolve()),
            "description": description,
            "agents": agents,
            "created_at": datetime.now().isoformat()
        })
    
    save_registry(registry)

def remove_project(name: str) -> None:
    """Remove project from registry by name."""
    registry = load_registry()
    projects = registry.get("projects", [])
    registry["projects"] = [p for p in projects if p["name"] != name]
    save_registry(registry)

def list_projects() -> List[Dict[str, Any]]:
    """Return all registered projects."""
    return load_registry().get("projects", [])

def list_projects_by_agent(agent: str) -> List[Dict[str, Any]]:
    """Return projects where the agent is participating."""
    projects = list_projects()
    return [p for p in projects if agent in p.get("agents", [])]
