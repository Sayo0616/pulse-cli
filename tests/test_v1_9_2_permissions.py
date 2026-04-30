import tempfile
import pytest
from pathlib import Path
import shutil
import getpass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def setup_project(root: Path, roots=None):
    from mai.config import save_config, clear_config_cache
    clear_config_cache()
    mai_dir = root / ".mai"
    if not mai_dir.exists():
        mai_dir.mkdir()
    config = {
        "queues": {
            "questions": {"handler": "alice", "sla_minutes": 60},
        },
        "agents": {
            "alice": {"heartbeat_minutes": 30},
            "bob": {"heartbeat_minutes": 30},
        },
        "initialized_at": "2026-04-28T10:00:00"
    }
    if roots:
        config["root"] = roots
    save_config(root, config)

def test_init_permission(monkeypatch, capsys):
    from mai.project import cmd_project_init
    from mai.config import clear_config_cache
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Mock CWD to the tmpdir
        monkeypatch.chdir(root)
        
        # 1. Initialize project with admin as root
        setup_project(root, roots=["admin"])
        clear_config_cache()
        
        # 2. Try to init as 'alice' (who is owner but not root)
        monkeypatch.setenv("MAI_OPERATOR", "alice")
        
        # We need to pass the operator if we want it to use 'alice' 
        # because cmd_project_init uses operator parameter or getpass.getuser().
        # In our test, we'll pass it.
        with pytest.raises(SystemExit) as excinfo:
            cmd_project_init(".", operator="alice")
        
        assert excinfo.value.code == 3 # PERMISSION_DENIED code

def test_init_success_for_os_user(monkeypatch, capsys):
    from mai.project import cmd_project_init
    from mai.config import clear_config_cache
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monkeypatch.chdir(root)
        clear_config_cache()
        
        # Should succeed because there's no config, so current OS user is root
        current_user = getpass.getuser()
        cmd_project_init(".", operator=current_user)
        out = capsys.readouterr().out
        assert "initialized at" in out
