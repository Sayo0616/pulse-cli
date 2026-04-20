# Mai CLI 团队协作部署指南

本文档面向 Agent，说明如何将任意多个 AI Agent 组建为协作团队。所有 Agent 共享一个 `mai-cli` 工作区，通过 issue 队列和 flock 锁协调工作。

**文档结构：**
- 第一至二阶段为 Agent-agnostic（所有 Agent 平台通用）
- 第三阶段按平台分开说明（OpenClaw 示例，其他平台可扩展）
- 第四阶段所有平台共用

---

## 概念定义

| 概念 | 说明 |
|---|---|
| **共享工作区** | 团队成员共享的 mai-cli 项目目录，存放所有 issue/lock/daily-summary 数据。位于各 Agent 都能访问的共享路径下。 |
| **团队成员** | 参与协作的 Agent，按角色划分，每个角色对应一个 handler。 |
| **Handler** | 负责处理特定队列的 Agent 名称。队列的 `handler` 即处理该队列的 Agent 名称。 |
| **Deployer** | 负责初始化的 Agent，执行第一至二阶段。任意 Agent 均可，可以不是团队成员。 |
| **平台** | Agent 的运行时环境（如 `openclaw`、`hermes`）。不同平台的心跳/cron/exec 机制不同，部署时分开处理。 |

---

## 占位符说明

| 占位符 | 含义 | 示例 |
|---|---|---|
| `<SHARED_WORKSPACE_PATH>` | 共享 mai-cli 项目根目录，各 Agent 都能访问的路径 | `/workspace/team-shared` |
| `<AGENT_WORKSPACE>` | 配置的 Agent 的工作空间根目录 | `/openclaw/agents/<AGENT_NAME>` |
| `<AGENT_NAME>` | 当前 Agent 的名称（团队成员之一） | `coder` / `reviewer` |
| `<AGENT_PLATFORM>` | 当前 Agent 的运行时平台 | `openclaw` / `hermes` |
| `<HANDLER_X>` | 具体 handler 名称（`A`/`B`/...，非固定名称） | `coder` / `designer` |
| `<MAI_PATTERN>` | 本地 mai 可执行文件的 pattern | `/home/user/.local/bin/mai` |
| `<LOCK_INTERVAL>` | 锁检查间隔（分钟），建议 `heartbeat_minutes × 1.5` | `25`（当 heartbeat=17 时） |

---

## 第一阶段：初始化共享工作区（Deployer 执行，一次）

> 选择团队共享的工作区路径。执行后共享工作区配置对所有团队成员生效。

### 步骤 1.1：初始化 mai-cli 项目

```bash
mai init <PROJECT_NAME>
```

> 注意：这里传入的是**项目名称**，而非完整路径。mai-cli 会在 `~/.openclaw/workspace/projects/<PROJECT_NAME>/` 下创建项目目录。

### 步骤 1.2：注册团队成员

```bash
mai agent add alice --heartbeat-minutes 30
mai agent add bob --heartbeat-minutes 30
```

> 此命令会自动在 `config.json` 中注册 Agent，并创建对应的 `<name>-tasks` 任务队列。

### 步骤 1.3：配置 config.json (可选高级配置)

**字段说明：**

| 字段 | 说明 |
|---|---|
| `queues.<name>.handler` | 处理该队列的 Agent 名称（必须与 `agents` 中的 key 一致） |
| `queues.<name>.sla_minutes` | SLA 超时（分钟），超时后 issue 标记为 overdue |
| `queues.<name>.id_prefix` | issue ID 前缀，如 `"CODE"` 生成 `CODE-001` |
| `agents.<name>.heartbeat_minutes` | Agent 心跳间隔，锁在 `heartbeat × 1.5` 分钟后自动释放 |
| `daily_summary_order` | 每日摘要轮转顺序，Agent 按此顺序执行 `daily-summary write` |

### 步骤 1.3：验证初始化成功

```bash
mai --project <SHARED_WORKSPACE_PATH> queue check
```

输出应显示所有配置的队列，均为空。

---

## 第二阶段：平台无关 Skill 分发（各 Agent 执行）

> Skill 文件随 mai-cli 包分发。每个 Agent 将 Skill 复制到自己的工作区。

### 步骤 2.1：定位 Skill 位置

Skill 目录位于 mai-cli 包内：
- 路径：`{pip_prefix}/openclaw/skills/mai-cli/`
- 或项目源码：`/projects/mai-cli/skills/mai-cli/`
- 若为 `.skill` 文件，先解压

### 步骤 2.2：复制到 Agent workspace

```bash
mkdir -p <AGENT_WORKSPACE>/skills/
cp -r <SKILL_PATH>/mai-cli <AGENT_WORKSPACE>/skills/
```

Skill 触发条件：Agent 被要求创建/认领/完成 issue、查看队列、触发每日摘要、强制释放锁、escalate。

---

## 第三阶段：配置 Agent 平台（各 Agent 执行各自的平台配置）

### 平台配置清单

| 平台 | 配置内容 |
|---|---|
| **OpenClaw** | exec 权限 + HEARTBEAT.md 心跳任务 + cron 守护 |
| **Hermes** |（预留）|
| **其他平台** |（按需扩展） |

---

### 3.1 OpenClaw Agent 配置

#### 3.1.1 添加 exec 权限

在 OpenClaw exec 权限配置中添加 mai 命令白名单：

```json
"allowlist": [
   {
      "id": "mai-cli-<AGENT_NAME>",
      "pattern": "<MAI_PATTERN>",
      "source": "allow-always"
   }
]
```

**最小权限版本**（仅限本 Agent 队列，推荐）：

| Agent（Handler） | 最小权限命令 |
|---|---|
| `alice` | `mai --project <PATH> issue *` + `queue check alice-tasks` + `daily-summary write/read` |
| `bob` | `mai --project <PATH> issue *` + `queue check bob-tasks` + `daily-summary write/read` |

#### 3.1.2 配置 HEARTBEAT.md 心跳任务

在 Agent workspace 的 `HEARTBEAT.md` 中添加队列监护任务。每个 Handler 只需监护自己的队列：

**队列监护（每心跳周期执行）：**

```markdown
## Mai CLI — <HANDLER_X> 队列监护

1. 检查 <HANDLER_X> 队列是否有待处理 issue：
   mai --project <SHARED_WORKSPACE_PATH> queue check <HANDLER_X>-questions --overdue

2. 若有待认领 issue，认领并处理：
   mai --project <SHARED_WORKSPACE_PATH> issue claim <issue-id>
   # [执行处理工作] ...
   mai --project <SHARED_WORKSPACE_PATH> issue complete <issue-id> <处理结论>
```

**每日摘要轮转（按 daily_summary_order 顺序）：**

完整流程：trigger → 各 Agent 按顺序 write（trigger 无需判断轮次，由 write 内部判断）

```markdown
## 每日摘要

1. 触发每日汇报（由 Deployer 或排在首位的 Agent 执行一次）：
   mai --project <SHARED_WORKSPACE_PATH> daily-summary trigger

2. 各 Agent 按 `daily_summary_order` 顺序写入自己的摘要（write 会自动判断轮次）：
   mai --project <SHARED_WORKSPACE_PATH> daily-summary write <AGENT_NAME> <汇报内容...>

3. 查看当前所有 Agent 的汇报状态：
   mai --project <SHARED_WORKSPACE_PATH> daily-summary read .

4. 汇总报告（由任意 Agent 在所有人写完后执行）：
   mai --project <SHARED_WORKSPACE_PATH> daily-summary read --all
```

#### 3.1.3 配置锁监护 cron

`lock guardian` 是长时间运行的守护进程，建议通过 cron 定期触发一个检查-退出的一-shot 命令，或在独立进程中持续运行。

**OpenClaw cron 格式（每 `<LOCK_INTERVAL>` 分钟触发）：**

```json
{
  "id": "<uuid>",
  "name": "mai-cli:lock-guardian",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "*/<LOCK_INTERVAL> * * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "<GUARDIAN_AGENT_SESSION>",
  "wakeMode": "now",
  "payload": {
    "kind": "systemEvent",
    "text": "mai --project <SHARED_WORKSPACE_PATH> lock guardian"
  }
}
```

**说明：**
- `sessionTarget` 填写承担锁监护的 Agent 的 session 名称
- `lock guardian` 收到触发后执行锁检查与释放，然后继续等待下一次触发
- cron 频率应与团队的 `heartbeat_minutes` 匹配（建议 `heartbeat × 1.5` 分钟以内）

---

### 3.2 Hermes Agent 配置（预留）

> 欢迎社区补充 Hermes 平台的配置方式。

---

## 第四阶段：验证部署

### 步骤 4.1：创建测试 issue

```bash
mai --project <SHARED_WORKSPACE_PATH> issue new \
  <HANDLER_A>-questions "部署验证测试" --ref TEST-001
```

### 步骤 4.2：验证认领与完成

```bash
# 列出队列，确认 issue 出现
mai --project <SHARED_WORKSPACE_PATH> issue list <HANDLER_A>-questions

# 认领
mai --project <SHARED_WORKSPACE_PATH> issue claim <ISSUE-ID>

# 完成
mai --project <SHARED_WORKSPACE_PATH> issue complete <ISSUE-ID> "验证通过"
```

### 步骤 4.3：验证每日摘要

```bash
# 触发轮转
mai --project <SHARED_WORKSPACE_PATH> daily-summary trigger

# 检查当前状态（每人按顺序执行 read）
mai --project <SHARED_WORKSPACE_PATH> daily-summary read <AGENT_NAME>

# 轮到时写入摘要
mai --project <SHARED_WORKSPACE_PATH> daily-summary write <AGENT_NAME> "验证摘要"

# 确认写入成功
mai --project <SHARED_WORKSPACE_PATH> daily-summary read <AGENT_NAME>
```

## 附录：mai-cli 核心命令参考

```
# Project / Agent
mai init <PROJECT_NAME>
mai agent add <name> [--heartbeat-minutes 30]

# Issue
mai --project <PATH> issue new <queue> <title> [--ref <ref-id>]
...
```

mai --project <PATH> issue claim <issue-id>
mai --project <PATH> issue complete <issue-id> <conclusion>
mai --project <PATH> issue amend <issue-id> [<remark>]
mai --project <PATH> issue list [queue]
mai --project <PATH> issue show <issue-id>
mai --project <PATH> issue escalate <issue-id>

# Queue
mai --project <PATH> queue check [queue] [--overdue]
mai --project <PATH> queue blockers

# Lock
mai --project <PATH> lock check <issue-id>
mai --project <PATH> lock force-release <issue-id>
mai --project <PATH> lock guardian

# Daily Summary
mai --project <PATH> daily-summary trigger
mai --project <PATH> daily-summary read [<agent>|.|--all]
mai --project <PATH> daily-summary write <agent> <content...>

# Log
mai --project <PATH> log history [--date <YYYY-MM-DD>] [--agent <agent>]
mai --project <PATH> log write <agent> <type> <summary> [<status>]

# Exec
mai --project <PATH> exec safe-check <cmd>

# Escalation
mai --project <PATH> escalation gen <issue-id>
```

详细命令说明见 Skill `references/commands.md`。
