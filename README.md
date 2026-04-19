# Agent Pulse

**Multi-Agent Collaboration CLI — flock-based coordination, event-driven workflow, zero overhead.**

Pulse is a command-line tool that coordinates multiple AI agents working on a shared project. It provides atomic locking, queue-based issue routing, per-agent heartbeat timeouts, and an automated daily summary loop — all backed by a simple file-based store.

---

## Features

- **Atomic flock locks** — race-condition-free claim/complete cycles via POSIX `fcntl`
- **Queue-based routing** — issues route to the right agent with configurable SLA per queue
- **Heartbeat-aware guardian** — stale locks auto-release after `heartbeat × 1.5` minutes
- **Event-driven daily summary** — ordered turn-taking with idempotent trigger/collect
- **Async mirror** — `.pulse/` internal store syncs to `async/` for human visibility
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
pulse project init MyProject
```

**Step 2 — Create an issue**

```bash
pulse --project MyProject issue new programmer-questions "How should we handle input buffering?"
```

**Step 3 — Have the assigned agent claim it**

```bash
pulse --project MyProject issue claim REQ-001
```

**Step 4 — Mark it done**

```bash
pulse --project MyProject issue complete REQ-001 "Decision: ring buffer, 60Hz polling"
```

**Step 5 — Inspect queues**

```bash
pulse --project MyProject queue check
```

---

## Architecture

```
.pulse/                        async/
├── queues/<queue>/  Issue files  <queue>/  Human-visible mirror
├── locks/           flock files  (internal only)
├── processing/      Active issues  <queue>/
├── decisions/       Conclusion logs  decisions/
├── history/         Audit logs  history/
├── events/          Daily-summary triggers  (internal only)
└── config.json      All collaboration rules
```

**Lock protocol**: When an agent claims an issue, Pulse acquires an `flock(2)`-based file lock. The lock expires after `heartbeat × 1.5` minutes if the agent fails to heartbeat. The `lock guardian` cron command automatically releases stale locks.

**Daily summary flow**: `trigger` → each agent `write` in order → `collect` merges all summaries into a single report.

---

## Command Reference

### Issue
```
pulse issue new <queue> <title> [--ref REQ-XXX]
pulse issue amend <issue-id> <remark>
pulse issue claim <issue-id>
pulse issue complete <issue-id> <conclusion>
pulse issue list [queue]
pulse issue show <issue-id>
pulse issue escalate <issue-id>
```

### Queue
```
pulse queue check [queue] [--overdue]
pulse queue blockers
```

### Lock
```
pulse lock check <issue-id>
pulse lock force-release <issue-id>
pulse lock guardian
```

### Log
```
pulse log history [--date YYYY-MM-DD] [--agent NAME]
pulse log write <agent> <type> <summary> [status]
```

### Daily Summary
```
pulse daily-summary trigger
pulse daily-summary write <agent> <content...>
pulse daily-summary collect
```

### Escalation
```
pulse escalation gen <issue-id>
```

### Bitable
```
pulse bitable sync-status
pulse bitable retry
```

### Project
```
pulse project init <project-name>
```

---

## Configuration

Edit `.pulse/config.json` in your project root:

```json
{
  "queues": {
    "programmer-questions": {
      "handler": "designer",
      "sla_minutes": 120,
      "id_prefix": "REQ"
    }
  },
  "agents": {
    "programmer": { "heartbeat_minutes": 17 },
    "designer":   { "heartbeat_minutes": 29 }
  },
  "daily_summary_order": ["programmer", "designer", "architect", "narrative", "techartist"]
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
