"""Mai CLI - Configuration module.

"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────
# Default Configuration (Fallbacks)
# ─────────────────────────────────────────────

LEGACY_QUEUES = {
    "programmer-questions":       {"handler": "designer",      "sla_minutes": 120,  "id_prefix": "REQ"},
    "architect-decisions":        {"handler": "architect",     "sla_minutes": 120,  "id_prefix": "REQ"},
    "techartist-reviews":        {"handler": "designer",      "sla_minutes": 240,  "id_prefix": "REQ"},
    "narrative-reports":         {"handler": "designer",      "sla_minutes": 240,  "id_prefix": "REQ"},
    "architect-reviews-designer":{"handler": "designer",      "sla_minutes": 120,  "id_prefix": "REQ"},
    "quick-fix-requests":         {"handler": "programmer",    "sla_minutes": 60,   "id_prefix": "FIX"},
    "designer-blockers":         {"handler": "designer",      "sla_minutes": None, "id_prefix": "BLK"},
}

DEFAULT_QUEUES = {
    "questions":  {"handler": "default", "sla_minutes": 120, "id_prefix": "REQ"},
    "decisions":  {"handler": "default", "sla_minutes": 120, "id_prefix": "REQ"},
    "reviews":    {"handler": "default", "sla_minutes": 240, "id_prefix": "REQ"},
    "reports":    {"handler": "default", "sla_minutes": 240, "id_prefix": "REQ"},
    "requests":   {"handler": "default", "sla_minutes": 60,  "id_prefix": "FIX"},
    "blockers":   {"handler": "default", "sla_minutes": None, "id_prefix": "BLK"},
}

DEFAULT_AGENTS = {
    "default": {"heartbeat_minutes": 30},
}

DEFAULT_DAILY_ORDER = []

DEFAULT_EMOJI = {
    "open":       "🔓",
    "claimed":    "🔄",
    "complete":   "✅",
    "escalated":  "⚠️",
    "blocked":    "⚠️",
    "overdue":    "⏱️",
}

# Deprecated: use DEFAULT_DAILY_ORDER
DAILY_SUMMARY_ORDER = DEFAULT_DAILY_ORDER


# ─────────────────────────────────────────────
# Global State & Config Cache
# ─────────────────────────────────────────────

class GlobalArgs:
    project: Optional[str] = None
    format: str = "text"
    dry_run: bool = False
    _config_cache: Dict[str, Dict[str, Any]] = {}

GLOBAL = GlobalArgs()


def get_config(project_root: Path) -> Dict[str, Any]:
    """Load config from .mai/config.json, merged with defaults. Keyed by project_root."""
    root_key = str(project_root.resolve())
    if root_key in GLOBAL._config_cache:
        return GLOBAL._config_cache[root_key]

    mai_dir = project_root / ".mai"
    cfg_file = mai_dir / "config.json"

    base = {}
    if cfg_file.exists():
        try:
            base = json.loads(cfg_file.read_text("utf-8"))
        except Exception:
            pass

    # Safer merge for queues to handle old format (owner/sla_hours)
    merged_queues = {}
    base_queues = base.get("queues", {})

    # 1. Start with all from config.json
    for q_name, ovr in base_queues.items():
        # Fallback to generic default_val if q_name is not in DEFAULT_QUEUES
        # REQ-003: preserve legacy handler for old queues if missing
        default_val = DEFAULT_QUEUES.get(
            q_name,
            LEGACY_QUEUES.get(q_name, {"handler": "default", "sla_minutes": None, "id_prefix": "REQ"})
        )
        merged_queues[q_name] = {
            "handler":      ovr.get("handler", ovr.get("owner", default_val["handler"])),
            "sla_minutes":  ovr.get("sla_minutes",
                                    (ovr.get("sla_hours") * 60)
                                    if ovr.get("sla_hours") is not None
                                    else default_val["sla_minutes"]),
            "id_prefix":    ovr.get("id_prefix", default_val["id_prefix"]),
        }

    # 2. Add defaults if not present
    for q_name, default_val in DEFAULT_QUEUES.items():
        if q_name not in merged_queues:
            merged_queues[q_name] = default_val

    cfg = {
        "queues":                 merged_queues,
        "agents":                 {**DEFAULT_AGENTS, **base.get("agents", {})},
        "daily_summary_order":    base.get("daily_summary_order") or DEFAULT_DAILY_ORDER,
        "issue_status_emoji":      {**DEFAULT_EMOJI, **base.get("issue_status_emoji", {})},
        "raw":                    base,
    }
    GLOBAL._config_cache[root_key] = cfg
    return cfg


def get_heartbeat_intervals(project_root: Path) -> Dict[str, int]:
    agents = get_config(project_root)["agents"]
    return {k: v["heartbeat_minutes"] for k, v in agents.items()}


def get_queue_sla(project_root: Path) -> Dict[str, tuple]:
    queues = get_config(project_root)["queues"]
    return {k: (v["handler"], v["sla_minutes"] / 60 if v["sla_minutes"] else None)
            for k, v in queues.items()}


def get_queue_id_prefix(project_root: Path) -> Dict[str, str]:
    queues = get_config(project_root)["queues"]
    return {k: v["id_prefix"] for k, v in queues.items()}


def get_status_emoji(project_root: Path) -> Dict[str, str]:
    return get_config(project_root)["issue_status_emoji"]


def get_blockers_queue(project_root: Path) -> str:
    raw = get_config(project_root).get("raw", {})
    return raw.get("blockers_queue", "blockers")


def get_daily_order(project_root: Path) -> List[str]:
    return get_config(project_root)["daily_summary_order"]

def load_config(project_root: Path) -> Dict[str, Any]:
    cfg_file = get_mai_dir(project_root) / "config.json"
    if cfg_file.exists():
        return json.loads(cfg_file.read_text())
    return {}


def save_config(project_root: Path, config: Dict[str, Any]):
    if GLOBAL.dry_run:
        return
    cfg_file = get_mai_dir(project_root) / "config.json"
    cfg_file.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    # Sync is handled by caller


def find_project_root(project_name: Optional[str] = None) -> Optional[Path]:
    if project_name:
        for env_var in ["AGENTS_PROJECT", "MAI_PROJECT"]:
            val = os.environ.get(env_var)
            if val:
                p = Path(val)
                if p.name == project_name or str(p) == project_name:
                    if p.exists():
                        return p
        wp = Path.home() / ".openclaw" / "workspace" / "projects" / project_name
        if wp.exists():
            return wp
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if parent.name == project_name and (parent / "AGENTS.md").exists():
                return parent
        return None

    for env_var in ["AGENTS_PROJECT", "MAI_PROJECT"]:
        val = os.environ.get(env_var)
        if val:
            p = Path(val)
            if p.exists():
                return p

    projects_dir = Path.home() / ".openclaw" / "workspace" / "projects"
    if projects_dir.exists():
        dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
        if len(dirs) == 1:
            return dirs[0]

    return None


def get_mai_dir(project_root: Path) -> Path:
    return project_root / ".mai"


def get_async_dir(project_root: Path) -> Path:
    return project_root / "async"
