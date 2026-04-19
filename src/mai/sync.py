"""Mai CLI - Async mirror sync module.

v1.1.0
"""

import shutil
from pathlib import Path

from .config import get_mai_dir, get_async_dir, get_queue_sla, GLOBAL


def sync_to_async(src_path: Path, project_root: Path, target_queue: str = ""):
    """Sync a .mai file to the async mirror.

    Special handling:
    - processing/ files → async/<queue>/ (resolve via processing filename)
    - locks/ files → skip (internal only)
    - events/ files → skip (internal only)
    - decisions/ files → async/decisions/
    - queues/ files → async/<queue>/
    """
    if GLOBAL.dry_run:
        return
    mai = get_mai_dir(project_root)
    async_dir = get_async_dir(project_root)

    try:
        rel = src_path.relative_to(mai)
    except ValueError:
        rel = Path(src_path.name)

    parts = rel.parts
    top = parts[0] if parts else ""

    # Skip internal-only directories
    if top in ("locks", "events"):
        return

    if top == "processing":
        issue_id = src_path.stem
        if target_queue:
            dst = async_dir / target_queue / src_path.name
        else:
            found_queue = None
            queue_sla = get_queue_sla(project_root)
            for q in queue_sla:
                q_path = mai / "queues" / q / f"{issue_id}.md"
                if q_path.exists():
                    found_queue = q
                    break
            if found_queue:
                dst = async_dir / found_queue / src_path.name
            else:
                dst = async_dir / "processing" / src_path.name
    elif top == "decisions":
        dst = async_dir / "decisions" / src_path.name
    elif top == "queues":
        queue_name = parts[1] if len(parts) > 1 else ""
        dst = async_dir / queue_name / src_path.name if queue_name else async_dir / src_path.name
    else:
        dst = async_dir / rel

    dst.parent.mkdir(parents=True, exist_ok=True)
    if src_path.is_file():
        shutil.copy2(src_path, dst)
