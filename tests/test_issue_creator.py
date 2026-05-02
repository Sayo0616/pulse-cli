import os
import tempfile
import pytest
from pathlib import Path
from mai.issue import cmd_issue_new, parse_issue_file
from mai.config import save_config, clear_config_cache

def test_issue_new_with_operator_override():
    """Verify that operator is correctly used as the primary identifier (REQ-A)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        clear_config_cache()
        (root / ".mai").mkdir()
        save_config(root, {
            "queues": {"questions": {"owner": "alice", "sla_minutes": 60}},
            "agents": {"human_sayo": {}},
            "root": "human_sayo" # Make it root so it can create
        })

        # Test 1: Provide operator via parameter
        cmd_issue_new(root, "questions", "Test override", ref=None, operator="human_sayo")
        
        queue_dir = root / ".mai" / "queues" / "questions"
        files = list(queue_dir.glob("*.md"))
        assert len(files) == 1
        
        data = parse_issue_file(files[0])
        assert any(t.get("action") == "创建" and t.get("agent") == "human_sayo" for t in data["timeline"])
def test_issue_new_default_operator(monkeypatch):
    """Verify that MAI_AGENT is used if no operator is provided (backward compatibility / fallback)."""
    # Mock environment variable
    monkeypatch.setenv("MAI_AGENT", "auto_coder")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        clear_config_cache()
        (root / ".mai").mkdir()
        save_config(root, {
            "queues": {"questions": {"owner": "alice", "sla_minutes": 60}},
            "agents": {"auto_coder": {}},
            "root": "auto_coder"
        })

        cmd_issue_new(root, "questions", "Test default", ref=None)
        
        queue_dir = root / ".mai" / "queues" / "questions"
        files = list(queue_dir.glob("*.md"))
        assert len(files) == 1
        
        data = parse_issue_file(files[0])
        assert any(t.get("action") == "创建" and t.get("agent") == "auto_coder" for t in data["timeline"])
