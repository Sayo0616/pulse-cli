# Mai CLI — Developer Guide

*(Placeholder — expand with architecture notes, testing strategy, and module map.)*

## Module Map

| Module | Responsibility |
|:---|:---|
| `mai.py` | Entry point: argparse, dispatch, output helpers |
| `config.py` | Defaults, GlobalArgs, config accessors |
| `sync.py` | `.mai/` → `async/` mirror |
| `issue.py` | Issue lifecycle (new/amend/claim/complete/escalate) |
| `issue_list.py` | Issue queries (list/show) |
| `queue.py` | Queue check and blockers |
| `lock.py` | flock lock acquire/release/check + commands |
| `log.py` | Audit log read/write + commands |
| `daily_summary.py` | Event-driven daily summary (trigger/write/collect) |
| `escalation.py` | Escalation report generation |
| `bitable.py` | Bitable sync status and retry |
| `safe_exec.py` | Dangerous command pattern detection |
| `project.py` | Project init and directory structure creation |

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Adding a New Command

1. Add the command function to the appropriate module (or create a new one)
2. Add the argparse subparser in `mai.py`'s `build_parser()`
3. Add a `dispatch_<group>()` case in `dispatch()` and implement it
4. Add a test in `tests/test_mai.py`

## Code Style

PEP 8 — max line width 100. Run `flake8 src/` before committing.
