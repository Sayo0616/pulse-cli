"""Mai CLI - Global Configuration module.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

DEFAULT_GLOBAL_CONFIG = {
    "root": [],
}

def get_global_config_dir() -> Path:
    """Return ~/.mai-cli/ path, creating it if it doesn't exist with 0700 permissions."""
    config_dir = Path.home() / ".mai-cli"
    if not config_dir.exists():
        config_dir.mkdir(parents=True, mode=0o700)
    else:
        # Ensure correct permissions even if it exists
        if os.name != 'nt':  # chmod not fully applicable on Windows
            os.chmod(config_dir, 0o700)
    return config_dir

def get_global_config_path() -> Path:
    """Return path to global config.json."""
    return get_global_config_dir() / "config.json"

def get_global_config() -> Dict[str, Any]:
    """Read ~/.mai-cli/config.json, returning default if not exists."""
    cfg_file = get_global_config_path()
    if not cfg_file.exists():
        return DEFAULT_GLOBAL_CONFIG.copy()
    
    try:
        return json.loads(cfg_file.read_text("utf-8"))
    except Exception:
        return DEFAULT_GLOBAL_CONFIG.copy()

def save_global_config(config: Dict[str, Any]) -> None:
    """Atomically write global config (temp file -> rename)."""
    config_dir = get_global_config_dir()
    cfg_file = config_dir / "config.json"
    
    # Ensure initialized_at if not present
    if "initialized_at" not in config:
        config["initialized_at"] = datetime.now().isoformat()

    # Use a temporary file in the same directory to ensure atomic rename
    fd, temp_path = tempfile.mkstemp(dir=str(config_dir), prefix="config.json.tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        os.replace(temp_path, cfg_file)
        
        # Set file permissions to 0600
        if os.name != 'nt':
            os.chmod(cfg_file, 0o600)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def get_global_roots() -> List[str]:
    """Read root list from global config."""
    config = get_global_config()
    roots = config.get("root", [])
    if isinstance(roots, str):
        return [roots]
    return roots
