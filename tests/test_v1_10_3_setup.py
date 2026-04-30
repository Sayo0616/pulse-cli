import pytest
import json
import os
from io import StringIO
from unittest.mock import patch
from pathlib import Path
from mai.mai import main
from mai.config import clear_config_cache

@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    
    monkeypatch.delenv("MAI_PROJECT", raising=False)
    monkeypatch.delenv("MAI_OPERATOR", raising=False)
    
    clear_config_cache()
    
    with patch("pathlib.Path.home", return_value=home), \
         patch("os.getcwd", return_value=str(project)), \
         patch("mai.config.find_project_root", return_value=project), \
         patch("mai.mai.find_project_root", return_value=project), \
         patch("mai.project.find_project_root", return_value=project):
        yield {"home": home, "project": project}

def run_mai(args, input_str=None):
    stdout = StringIO()
    stderr = StringIO()
    with patch("sys.stdout", stdout), patch("sys.stderr", stderr), patch("sys.argv", ["mai"] + args):
        if input_str is not None:
            with patch("builtins.input", return_value=input_str):
                try:
                    main()
                except SystemExit as e:
                    return e.code == 0, stdout.getvalue() + stderr.getvalue()
        else:
            try:
                main()
            except SystemExit as e:
                return e.code == 0, stdout.getvalue() + stderr.getvalue()
    return True, stdout.getvalue() + stderr.getvalue()

def test_setup_requirement(clean_env):
    # Any command should fail if not setup
    ok, output = run_mai(["status"])
    assert not ok
    assert "Run 'mai setup' first" in output

def test_setup_interactive(clean_env):
    ok, output = run_mai(["setup"], input_str="admin, manager")
    assert ok
    assert "initialized successfully" in output
    
    # Verify config
    cfg_path = clean_env["home"] / ".mai-cli" / "config.json"
    assert cfg_path.exists()
    with open(cfg_path) as f:
        cfg = json.load(f)
        assert cfg["root"] == ["admin", "manager"]

def test_setup_flag(clean_env):
    ok, output = run_mai(["setup", "--root", "root1,root2"])
    assert ok
    
    cfg_path = clean_env["home"] / ".mai-cli" / "config.json"
    with open(cfg_path) as f:
        cfg = json.load(f)
        assert cfg["root"] == ["root1", "root2"]

def test_init_strict_operator(clean_env):
    # 1. Setup global
    run_mai(["setup", "--root", "admin"])
    
    # 2. Try init without operator - should fail at argparse level
    # Since we can't easily catch argparse Exit, we check for 'required'
    with patch("sys.stderr", StringIO()) as err:
        with pytest.raises(SystemExit):
            main_args = ["mai", "init"]
            with patch("sys.argv", main_args):
                main()
        assert "the following arguments are required: -o/--operator" in err.getvalue()

def test_init_permission_denied(clean_env):
    # 1. Setup global
    run_mai(["setup", "--root", "admin"])
    
    # 2. Try init with non-root operator
    ok, output = run_mai(["init", "-o", "user"])
    assert not ok
    assert "权限不足" in output

def test_init_success(clean_env):
    # 1. Setup global
    run_mai(["setup", "--root", "admin"])
    
    # 2. Try init with root operator
    ok, output = run_mai(["init", "-o", "admin"])
    assert ok
    assert "initialized" in output.lower()
