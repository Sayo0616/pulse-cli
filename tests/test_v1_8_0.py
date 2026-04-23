import os
import tempfile
import pytest
import time
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def setup_project(root: Path):
    from mai.config import save_config
    (root / ".mai").mkdir()
    save_config(root, {
        "queues": {
            "questions": {"handler": "alice", "sla_minutes": 60},
            "dev": {"handler": "bob", "sla_minutes": 120}
        },
        "status_emoji": {
            "open": "⭕",
            "in_progress": "🔄",
            "completed": "✅"
        }
    })

def test_priority_creation():
    from mai.issue import cmd_issue_new, parse_issue_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        
        # Default priority (P2)
        cmd_issue_new(root, "questions", "Default Priority", ref=None)
        # P0 priority
        cmd_issue_new(root, "questions", "High Priority", ref=None, priority="P0")
        
        queue_dir = root / ".mai" / "queues" / "questions"
        files = list(queue_dir.glob("*.md"))
        assert len(files) == 2
        
        p2_file = next(f for f in files if "Default Priority" in f.read_text())
        p0_file = next(f for f in files if "High Priority" in f.read_text())
        
        data_p2 = parse_issue_file(p2_file)
        data_p0 = parse_issue_file(p0_file)
        
        assert data_p2["priority"] == "P2"
        assert "**优先级：** 🟢 P2" in data_p2["raw"]
        
        assert data_p0["priority"] == "P0"
        assert "**优先级：** 🔴 P0" in data_p0["raw"]

def test_priority_sorting():
    from mai.issue import cmd_issue_new
    from mai.issue_list import list_issues_in_queue
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        
        # Create in reverse order of priority and time
        cmd_issue_new(root, "questions", "P2-Old", ref=None, priority="P2")
        time.sleep(0.1)
        cmd_issue_new(root, "questions", "P1", ref=None, priority="P1")
        time.sleep(0.1)
        cmd_issue_new(root, "questions", "P0-Old", ref=None, priority="P0")
        time.sleep(0.1)
        cmd_issue_new(root, "questions", "P0-New", ref=None, priority="P0")
        
        issues = list_issues_in_queue(root, "questions")
        
        titles = [iss["title"] for iss in issues]
        # Expected order: P0-Old, P0-New, P1, P2-Old
        assert titles == ["P0-Old", "P0-New", "P1", "P2-Old"]

def test_queue_check_handler_formatting(capsys, monkeypatch):
    from mai.issue import cmd_issue_new
    from mai.queue import cmd_queue_check
    from mai.mai import GLOBAL
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        GLOBAL.format = "text"
        
        cmd_issue_new(root, "questions", "Issue for Alice", ref=None, creator="bob")
        # Ensure owner is @alice (default for questions queue is alice)
        
        # Test 1: Full check (shows headers)
        cmd_queue_check(root, queue=None, overdue=False)
        out, _ = capsys.readouterr()
        assert "## Queue: questions" in out
        
        # Test 2: Handler check (no headers, custom format)
        cmd_queue_check(root, queue=None, overdue=False, handler="alice")
        out, _ = capsys.readouterr()
        assert "## Queue: questions" not in out
        assert "[REQ-" in out
        assert "(owner: alice, created:" in out

def test_handler_matching_with_at_prefix(capsys):
    from mai.issue import cmd_issue_new
    from mai.queue import cmd_queue_check
    from mai.mai import GLOBAL
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        GLOBAL.format = "text"
        
        # Create issue with owner explicitly set to @alice (if we could, but cmd_issue_new uses queue default)
        # Actually cmd_issue_new in my implementation strips @ from agent/creator but make_issue_content adds @ to output.
        # Let's verify our matching logic in cmd_queue_check handles both.
        
        cmd_issue_new(root, "questions", "Alice's Issue", ref=None)
        
        # Match with 'alice'
        cmd_queue_check(root, queue=None, overdue=False, handler="alice")
        out1, _ = capsys.readouterr()
        assert "Alice's Issue" in out1
        
        # Match with '@alice'
        cmd_queue_check(root, queue=None, overdue=False, handler="@alice")
        out2, _ = capsys.readouterr()
        assert "Alice's Issue" in out2

def test_queue_check_json_total_count(monkeypatch):
    from mai.issue import cmd_issue_new
    from mai.queue import cmd_queue_check
    from mai.mai import GLOBAL
    import json
    import io
    from contextlib import redirect_stdout
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        GLOBAL.format = "json"
        
        cmd_issue_new(root, "questions", "Alice 1", ref=None)
        cmd_issue_new(root, "questions", "Alice 2", ref=None)
        cmd_issue_new(root, "dev", "Bob 1", ref=None) # Questions default is alice, dev default is bob
        
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_queue_check(root, queue=None, overdue=False, handler="alice")
        
        data = json.loads(f.getvalue())
        # 'questions' should have 2, 'dev' should have 0
        assert data["queues"]["questions"]["total"] == 2
        assert len(data["queues"]["questions"]["issues"]) == 2
        assert data["queues"]["dev"]["total"] == 0
        assert len(data["queues"]["dev"]["issues"]) == 0

def test_issue_escalate_priority():
    from mai.issue import cmd_issue_new, cmd_issue_escalate, parse_issue_file
    from mai.config import save_config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        setup_project(root)
        # Add architect queue
        cfg = (root / ".mai" / "config.json")
        import json
        data = json.loads(cfg.read_text())
        data["queues"]["architect-reviews-designer"] = {"handler": "architect", "sla_minutes": 60}
        cfg.write_text(json.dumps(data))
        
        cmd_issue_new(root, "questions", "Base Issue", ref=None)
        issue_id = next((root / ".mai" / "queues" / "questions").glob("*.md")).stem
        
        cmd_issue_escalate(root, issue_id)
        
        # Find escalated issue
        esc_file = next((root / ".mai" / "queues" / "architect-reviews-designer").glob("*.md"))
        data = parse_issue_file(esc_file)
        assert data["priority"] == "P0"
        assert "**优先级：** 🔴 P0" in data["raw"]
