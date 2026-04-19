"""Mai CLI - Bitable integration module.

v1.1.0
"""

import json
from pathlib import Path

from .config import load_config, get_mai_dir, GLOBAL


def bitable_sync_status(project_root: Path):
    """Show bitable sync status."""
    from .mai import out, out_json, GLOBAL
    config = load_config(project_root)
    bitable_dir = project_root / "bitable-sync"
    sync_state_file = bitable_dir / "sync-state.json"

    if sync_state_file.exists():
        state = json.loads(sync_state_file.read_text("utf-8"))
    else:
        state = {
            "last_sync":    "",
            "status":       "not_configured",
            "failed_items": [],
            "retry_count":  0,
            "max_retries":  3,
        }

    app_token = config.get("bitable_app_token", "")
    if app_token:
        state["bitable_app_token"] = app_token

    out(command="bitable sync-status", **state)
    if GLOBAL.format == "text":
        out(f"Bitable sync status: {state['status']}")
        out(f"Last sync: {state.get('last_sync', 'never')}")
        if state.get("failed_items"):
            out(f"Failed items: {len(state['failed_items'])}")


def bitable_retry(project_root: Path):
    """Retry failed bitable sync items."""
    from .mai import out, GLOBAL
    bitable_dir = project_root / "bitable-sync"
    sync_state_file = bitable_dir / "sync-state.json"

    if not sync_state_file.exists():
        out("No bitable sync state found.", command="bitable retry")
        return

    state = json.loads(sync_state_file.read_text("utf-8"))
    failed = state.get("failed_items", [])
    if not failed:
        out("No pending retry items.", command="bitable retry")
        return

    if not GLOBAL.dry_run:
        state["retry_count"] = state.get("retry_count", 0) + 1
        sync_state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    retry_msg = (f"Retrying {len(failed)} failed items "
                 f"(attempt {state.get('retry_count', 1)}/{state.get('max_retries', 3)})")
    from .mai import out as _out
    _out(retry_msg, command="bitable retry", failed_items=failed)
