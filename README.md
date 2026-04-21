# Mai CLI

**English** | [简体中文](./README_zh.md)

**Multi-Agent Collaboration CLI — flock-based coordination, event-driven workflow, zero overhead.**

Mai is a command-line tool that coordinates multiple AI agents working on a shared project. It provides atomic locking, queue-based issue routing, per-agent heartbeat timeouts, and an automated daily summary loop — all backed by a simple file-based store.

---

## Features

- **Atomic flock locks** — race-condition-free claim/complete cycles via POSIX `fcntl`
- **Queue-based routing** — issues route to the right agent with configurable SLA per queue
- **Heartbeat-aware guardian** — stale locks auto-release after `heartbeat × 1.5` minutes
- **Event-driven daily summary** — ordered turn-taking with idempotent trigger/collect
- **Async mirror** — `.mai/` internal store syncs to `async/` for human visibility
- **Configurable via JSON** — all rules externalized to `config.json`; no code changes needed
- **Dual output format** — `--format json` for machine consumption, text for humans
- **Dry-run mode** — `--dry-run` previews every mutation without side effects

---

## Installation

```bash
pip install mai-cli
```

Or install from source:

```bash
git clone https://github.com/yourname/mai-cli.git
cd mai-cli
pip install -e .
```

---

## Quick Start

**Step 1 — Initialize a project**

```bash
mai init
```

**Step 2 — Register an agent**

```bash
mai --project MyProject agent add alice --heartbeat-minutes 30
```

**Step 3 — Create an issue**

```bash
mai --project MyProject issue new questions "How should we handle input buffering?"
```

**Step 4 — Have the assigned agent claim it**

```bash
mai --project MyProject issue claim REQ-001
```

**Step 5 — Mark it done**

```bash
mai --project MyProject issue complete REQ-001 "Decision: ring buffer, 60Hz polling"
```

**Step 6 — Inspect queues**

```bash
mai --project MyProject queue check
```

---

## Architecture

```
.mai/                        async/
├── queues/<queue>/  Issue files  <queue>/  Human-visible mirror
├── locks/           flock files  (internal only)
├── processing/      Active issues  <queue>/
├── decisions/       Conclusion logs  decisions/
├── history/         Audit logs  history/
├── events/          Daily-summary triggers  (internal only)
└── config.json      All collaboration rules
```

**Lock protocol**: When an agent claims an issue, Mai acquires an `flock(2)`-based file lock. The lock expires after `heartbeat × 1.5` minutes if the agent fails to heartbeat. The `lock guardian` cron command automatically releases stale locks.

**Daily summary flow**: `trigger` → each agent `write` in order → `collect` merges all summaries into a single report.

---

## Command Reference

### Global Options
```
mai [-v|--version] [--project <path>] [--format json|text] [--dry-run] <subcommand>
```

### Issue
```
mai issue new <queue> <title> [--ref REQ-XXX]
mai issue claim <issue-id>
mai issue block <issue-id> <reason>
mai issue unblock <issue-id>
mai issue complete <issue-id> <conclusion>
mai issue reopen <issue-id> <reason>
mai issue status <issue-id>
mai issue amend <issue-id> <remark>
mai issue list [queue]
mai issue show <issue-id>
mai issue escalate <issue-id>
```

### Queue
```
mai queue check [queue] [--overdue]
mai queue blockers
mai queue create <queue> --owner <agent> [--sla <hours>]
```

### Lock
```
mai lock check <issue-id>
mai lock release <issue-id> [--force] [--yes]
mai lock guardian
```

### Log
```
mai log history [--date YYYY-MM-DD] [--agent NAME]
mai log undo
mai log write <agent> <type> <summary> [status]
```

### Daily Summary
```
mai daily-summary trigger
mai daily-summary status
mai daily-summary reset
mai daily-summary write <agent> <content...>  # Protected by flock
mai daily-summary read [<agent>|.|--all]
```

### Escalation
```
mai escalation gen <issue-id>
```

### Exec
```
mai exec safe-check <command>
```

### Project / Agent
```
mai init                      # 在当前目录初始化（不接受参数）
mai project init [project-name]  # 在指定路径初始化，name 可省略
mai agent list
mai agent add <name> [--heartbeat-minutes 30]

### Status
```
mai status [--verbose]
```


---

## Configuration

Edit `.mai/config.json` in your project root:

```json
{
  "queues": {
    "questions": {
      "handler": "alice",
      "sla_minutes": 120,
      "id_prefix": "REQ"
    }
  },
  "agents": {
    "alice": { "heartbeat_minutes": 30 }
  },
  "daily_summary_order": ["alice", "bob"]
}
```

### Legacy field compatibility
`owner` → `handler`, `sla_hours` → `sla_minutes` are automatically converted.

---

## Supported Platforms

- **OS**: Linux / macOS (POSIX required for `flock`)
- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12

---

## License

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

MIT License — see [LICENSE](LICENSE) for the full text.

---

*Mai CLI v1.5.0*
