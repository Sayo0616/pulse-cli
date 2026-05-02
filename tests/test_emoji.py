import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# Ensure the package is importable from src/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_emoji_initial_creation():
    from mai.issue import make_issue_content
    from mai.config import DEFAULT_EMOJI
    
    # 1. Test OPEN status emoji
    content = make_issue_content(
        issue_id="REQ-001",
        queue="questions",
        title="Test",
        status="OPEN"
    )
    # ⭕ is the new emoji for open
    assert "⭕ OPEN" in content

def test_emoji_update_status():
    from mai.issue import _update_issue_file, parse_issue_file
    from mai.config import DEFAULT_EMOJI
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".mai" / "queues" / "questions").mkdir(parents=True)
        f = root / ".mai" / "queues" / "questions" / "REQ-001.md"
        f.write_text("# [REQ-001] Test\n**状态：** ⭕ OPEN\n## 处理记录\n", encoding="utf-8")
        
        data = {"path": str(f), "id": "REQ-001"}
        
        # Change to IN_PROGRESS
        _update_issue_file(root, data, "IN_PROGRESS")
        content = f.read_text("utf-8")
        assert "🔄 IN_PROGRESS" in content
        
        # Change to COMPLETED
        _update_issue_file(root, data, "COMPLETED")
        content = f.read_text("utf-8")
        assert "✅ COMPLETED" in content

def test_emoji_overdue_logic():
    from mai.issue_list import list_issues_in_queue
    from mai.config import save_config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".mai" / "queues" / "questions").mkdir(parents=True)
        save_config(root, {
            "queues": {"questions": {"handler": "alice", "sla_minutes": 60}}
        })
        
        # Create an overdue issue (created 2 hours ago)
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        f = root / ".mai" / "queues" / "questions" / "REQ-001.md"
        f.write_text(f"""# [REQ-001] Old Issue
<mai_meta>
id: REQ-001
status: OPEN
created: {old_time}
queue: questions
owner: alice
</mai_meta>
""", encoding="utf-8")
        
        issues = list_issues_in_queue(root, "questions")
        assert len(issues) == 1
        iss = issues[0]
        assert iss["sla_expired"] is True
        # Should have both OPEN emoji and OVERDUE emoji
        assert "⭕" in iss["status_emoji"]
        assert "⏱️" in iss["status_emoji"]
        assert iss["status_emoji"] == "⭕⏱️"

def test_emoji_parsing_robustness():
    from mai.issue import parse_issue_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "test.md"
        
        # Case 1: Standard meta
        f.write_text("<mai_meta>\nstatus: OPEN\n</mai_meta>", encoding="utf-8")
        assert parse_issue_file(f)["status"] == "OPEN"
        
        # Case 2: Multi-line meta
        f.write_text("<mai_meta>\nid: X\nstatus: IN_PROGRESS\n</mai_meta>", encoding="utf-8")
        assert parse_issue_file(f)["status"] == "IN_PROGRESS"
