# Multi-Agent 协同工作设计方案（Mai 指令系统版）

> 本文档定义 designer / architect / programmer / narrative / techartist 五个 Agent 的心跳任务、定时任务、Skill 配置及文件存储规范。
> **指令系统版**：所有协作元数据（队列/锁/审计）通过 `mai` 命令管理，`.mai` 目录对 Agent 隐藏，Agent 不可直接读写协作文件，只调用命令。
> 版本：v3.0（命名：Mai）（2026-04-19）｜终审修复：daily-summary命令补全+心跳第6步
> 模块化拆分版本参照 docs/README.md

---

## 一、协作架构总览

```
designer（体验终裁）
    ↑ 体验验收 / 否决
architect（技术终裁）
    ↑ 技术方案审批 / 否决
    ↑ 事后否决降级 → architect-reviews-designer 队列（见 §七·P0-2）
programmer（实现）
    ↑ 发现逻辑漏洞 → @designer 重评
    ↑ 技术风险 → @architect 确认
narrative（文本一致性）
    → strings.json / 剧本 / UI 文本审查
    → 客观错误 → 快通道直接通知 programmer（见 §七·P1-4）
techartist（美术 + 性能）
    → 渲染代码审查 / 性能基准测试
    → 客观错误 → 快通道直接通知 programmer（见 §七·P1-4）
```

**三条红线：**
1. **designer 否决 = 停工** — 体验不通过，architect 不能批准技术方案
2. **architect 否决 = 停实现** — 技术不可行，programmer 不得绕过
3. **architect 事后否决（designer 通过后）** → 触发 architect-reviews-designer 队列，由 designer 重审，不直接覆盖已通过决策

**用户接触规则：**
- 用户（Sayo）不介入日常决策，只接收**终裁结论性汇报**（带 `[REPORT_TO_USER]` 标记）
- 所有 Agent 必须进行**工作记录**，通过 `mai log write` 写入，作为团队透明度的唯一来源
- **exec 权限统一由用户管理**，审批被拒时通过飞书 channel 申请
- **安全命令免审批**（见 §四·P0-3 `safe-exec-list.json`）

---

## 二、指令系统（CLI）概述

### 2.1 安装与入口

```bash
# Agent 启动时自动加载（通过环境变量或 Profile）
alias mai='python3 ~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py'
```

### 2.2 命令结构

```
mai [全局选项] <子命令> [参数] [选项]

全局选项：
  --project <项目名>      指定项目（默认从环境变量 AGENTS_PROJECT 推断）
  --format <json|text>    输出格式（默认 text）
  --dry-run               只展示操作，不实际执行

子命令：
  mai issue new <queue> <标题> [--ref <issue-id>]  创建 Issue（--ref 用于 blocker 超时关联原始 Issue）
  mai issue amend <issue-id> <备注>           修订已归档结论（在 decisions/ 条目追加修订记录）
    # 调用权限：仅限原 Issue 处理方或被撤销方（如 architect 撤销自己批准的方案）
    # 约束：architect 不得撤销 designer 已终裁的体验决策；designer 不得撤销 architect 已终裁的技术决策
    # 效果：在原 decisions/<issue-id>.md 末尾追加修订记录（时间戳 + agent + 备注 + 状态→已修订）
    # 用例（§七·P0-2）：architect 事后否决 → issue amend REQ-XXX "TECH_BLOCKER: <原因>"
  mai issue claim <issue-id>            认领 Issue（原子锁）
  mai issue complete <issue-id> <结论>  完成 Issue（归档 + 解锁）
  mai issue list [queue]                列出 Issue
  mai issue show <issue-id>             显示 Issue 详情
    # 参数：<issue-id> 必填
    # 效果：打印 Issue 完整内容（头部元数据 + 问题描述 + 处理记录时间线）
  mai issue escalate <issue-id>         将 Issue 升级为冲突（直接写入 architect-reviews-designer 队列）

  mai queue check [queue] [--overdue]   扫描队列状态
    # 不指定 queue：全局扫描所有队列，返回超时 Issue 列表
    # 指定 queue：扫描该队列所有 Issue，返回超时 Issue 列表
    # --overdue：仅返回已超时的 Issue（不超时的不返回）
  mai queue blockers                    合并输出所有 designer-blockers

  mai lock check <issue-id>             检查锁状态
  mai lock force-release <issue-id>     超时强制释放锁（仅 age > 心跳间隔×1.5 时可执行）
  mai lock guardian                      守护进程：扫描所有锁，超时则强制释放（cron 每5分钟触发）

  mai log history [--date YYYY-MM-DD] [--agent <agent>]  查询审计历史
    # 参数：--date/--agent 均为可选，不指定则返回全量
    # 输出：append-only 历史日志，按时间倒序
  mai log write <agent> <type> <摘要> [状态]  写入标准化工作记录
    # 参数：<agent> <type> <摘要> 均为必填，状态可选（默认"进行中"）
    # 状态可选值：进行中 / 完成 / 阻塞 / 超时
    # 示例：mai log write architect heartbeat "正常" "进行中"
    #       mai log write programmer heartbeat "巡检发现 REQ-003 超时" "阻塞"

  mai daily-summary trigger                 触发每日汇总（仅 cron 使用，创建汇总事件标志）
  mai daily-summary write <agent> <内容>   Agent 心跳写入当日状态摘要（各 Agent 调用）
  mai daily-summary collect                 designer 收集所有摘要并生成最终汇总（designer 专用）

  mai escalation gen <issue-id>         生成冲突升级模板（打印到 stdout）
  mai bitable sync-status                查看同步状态
  mai bitable retry                     重试失败同步项
  mai exec safe-check <cmd>             检查命令是否在白名单
  mai project init <项目名>             初始化新项目（幂等：已存在则跳过）
```

### 2.3 命令执行约定

**退出码规范：**
| 退出码 | 含义 |
|:---:|:---|
| 0 | 成功 |
| 1 | 一般错误（参数错误、文件不存在等） |
| 2 | 锁被占用（其他进程持有锁，未超时） |
| 3 | 权限不足 |
| 4 | 项目未初始化（需先运行 `mai project init`） |

**输出格式：**
- `--format text`（默认）：人类可读富文本，带 emoji 和颜色提示
- `--format json`：机器可解析结构（所有 text 输出均有对应 json 结构）

**JSON 输出格式（约定）：**
```json
{
  "ok": true,
  "command": "issue claim",
  "issue_id": "REQ-003",
  "lock": {
    "path": ".mai/locks/REQ-003.lock",
    "holder": "architect",
    "created_at": "2026-04-19T14:30:00+08:00"
  }
}
```

**错误时输出：**
```json
{
  "ok": false,
  "error": "LOCK_HELD",
  "message": "锁被 architect 持有，剩余 12 分钟",
  "lock": {
    "path": ".mai/locks/REQ-003.lock",
    "holder": "architect",
    "ttl_minutes": 12
  }
}
```

**幂等性约定：**
- 所有写操作幂等：`issue new` 重复创建同名 Issue → 报错而不是重复创建
- `project init` 对已存在项目 → 检测后跳过，不报错

---

### 2.4 `daily-summary` 命令详解（事件驱动模型）

**核心设计原则：** `mai` 是命令行工具，不是 Agent 调度器。Cron 只负责设事件标志，各 Agent 在自己的心跳轮次中处理汇总写入。

**三个子命令：**

#### `daily-summary trigger`（Cron 调用）
```
mai daily-summary trigger
```
- 在 `.mai/events/.daily-summary-event` 创建事件标志（内容：`{"triggered_at": "<timestamp>", "next_agent": "programmer"}`）
- 若事件已存在（当日已触发）→ 幂等跳过，不报错
- 这是 Cron 18:00 的唯一操作，不涉及任何 LLM 调用

#### `daily-summary write <agent> <内容>`（各 Agent 心跳调用）
```
mai daily-summary write programmer "本日巡检 3 项，无超时"
```

**触发条件（各 Agent 心跳第 6 步）：**
```
mai daily-summary write <agent> "<当日状态摘要>"
# 系统内部逻辑：
# Step 1: 检查 .mai/events/.daily-summary-event 是否存在
#          → 不存在 → 跳过（今日未触发汇总）
# Step 2: 检查 .mai/locks/.daily-lock
#          → 存在且未超时 → 跳过（前面的 Agent 还在写）
#          → 存在但已超时 → 强制释放，继续
# Step 3: 检查事件中的 next_agent 是否为本 Agent
#          → 不是 → 跳过（等待轮到自己的心跳）
#          → 是 → 继续
# Step 4: 创建 .mai/locks/.daily-lock，内容：<agent>|<timestamp>
# Step 5: 写入 .mai/history/daily-YYYY-MM-DD/<agent>.md
# Step 6: 更新 .mai/events/.daily-summary-event，next_agent 指向下一个
# Step 7: 删除 .mai/locks/.daily-lock
```

**顺序强制：** `next_agent` 字段确保各 Agent 只能按 `programmer → narrative → techartist → architect → designer` 顺序写入，不得跳跃。

| Agent | 写入内容 | 期望摘要 |
|:---|:---|:---|
| programmer | 本日代码逻辑巡检结果 + 发现的 Issue 数 + 解决的 Issue 数 | 本日巡检 N 项，超时 M 项 |
| narrative | 本日 strings.json 扫描结果 + 快通道处理数 | 扫描 N 个文件，发现 M 处问题 |
| techartist | 本日性能基准测试结果 + 快通道处理数 | FPS N，DrawCall M |
| architect | 本日技术方案审批数 + 否决数 + 事后否决数 | 审批 N 项，通过/否决 M 项 |
| designer | **最终汇总**：收集各 Agent 摘要 + 所有积压 blocker + 需要用户介入的事项 | 各 Agent 状态 + blockers + 上报 |

#### `daily-summary collect`（designer 心跳专用）
```
mai daily-summary collect
# 当 next_agent 流转到 designer 时，designer 心跳调用此命令
# 读取 .mai/history/daily-YYYY-MM-DD/*.md（所有 Agent 的摘要）
# 生成最终汇总报告
# 保存至 projects/<项目名>/reports/daily-YYYY-MM-DD-summary.md
# 删除 .mai/events/.daily-summary-event（汇总完成）
```

**幂等性：**
- `trigger`：幂等，已存在则跳过
- `write`：幂等，同 Agent 同日多次调用只有第一次写入生效
- `collect`：幂等，已存在当日汇总文件则跳过

**守护机制（独立于心跳）：**
- `lock guardian` 同样负责 `.daily-lock` 超时释放（见 §2.2）
- 额外：`events/` 下的超时事件（age > 24h）由 guardian 清理

**Cron 配置：**
```
# 每日18:00：触发每日汇总事件
0 18 * * * mai daily-summary trigger

# 每5分钟：守护进程（清理孤儿锁和超时事件）
*/5 * * * * mai lock guardian
```

---

### 2.5 指令系统设计原则

| 原则 | 说明 |
|:---|:---|
| **元数据命令化** | 所有协作元数据（Issue、锁、队列、审计日志）只能通过 `mai` 命令操作 |
| **.mai 对 Agent 隐藏** | Agent 不可直接读写 `.mai` 目录，只能通过命令 |
| **async/ 仅供人类观察** | `projects/<项目名>/async/` 是对 Sayo 开放的可视化镜像，Agent 不得直接读取 |
| **幂等优先** | 所有写操作幂等，重复执行不破坏状态 |
| **信息获取必须通过命令** | Agent 获取任何协作状态（Issue 详情、队列内容、锁状态）必须使用 `mai` 命令，不得使用 cat/read 直读文件 |

---

## 三、工作区结构

### 3.1 目录分工

| 路径 | 用途 | 性质 |
|:---|:---|:---|
| `<workspace>/memory/` | Agent 记忆、长期知识、过往日志 | 个人/系统记忆，不可作为工作交付 |
| `~/.openclaw/workspace/agents/shared-workspace/` | 跨 Agent 共享的非特定项目文件 | 团队日常交流入口，不包含项目内容 |
| `~/.openclaw/workspace/projects/` | 跨 Agent 共享的工作文件、队列、日志 | 团队项目协作入口，source of truth |
| **`.mai`** | **指令系统内部存储（Agent 不可直接读写）** | **协作元数据存储，对 Agent 隐藏** |
| 真实项目地址（见 §八·P1-5 `project.config.json`） | 实际开发产物（代码、资源、配置） | 版本控制，本地存储 |

**严格约束：`memory/` 不得作为任何 Agent 的工作交付目录。**

### 3.2 内部存储：`.mai` 目录（Agent 不可见）

```
.mai                              # 指令系统内部存储（通过 mai 管理）
├── config.json                    # 项目配置（SLA / 心跳间隔 / 队列定义）
├── queues/                        # Issue 队列数据（替代 async/<queue>/）
│   ├── programmer-questions/
│   ├── architect-decisions/
│   ├── techartist-reviews/
│   ├── narrative-reports/
│   ├── architect-reviews-designer/
│   ├── quick-fix-requests/
│   └── designer-blockers/
├── processing/                    # 持锁中的 Issue（原子锁协议）
├── locks/                        # 锁文件
├── decisions/                     # 归档结论
└── history/                      # 审计日志（append-only）
```

### 3.3 对外工作区：`projects/<项目名>/`（Agent 可读）

```
~/.openclaw/workspace/projects/<项目名>/
├── async/                         # 供人类（Sayo）观察的可视化镜像（Agent 禁止直读）
│   ├── programmer-questions/
│   ├── architect-decisions/
│   ├── techartist-reviews/
│   ├── narrative-reports/
│   ├── architect-reviews-designer/
│   ├── quick-fix-requests/
│   ├── processing/
│   ├── designer-blockers/
│   └── history/
│       └── YYYY-MM-DD.log
├── decisions/                     # 终裁决策记录（终稿）
├── reports/                       # 各 Agent 产出的报告
│   └── daily-YYYY-MM-DD-summary.md
├── bitable-sync/                  # bitable API 同步状态（含容错，见 §十·P1-2）
│   └── sync-state.json
├── locks/                         # 锁文件（含超时，见 §七·P1-3）
│   └── .daily-lock
├── templates/                     # 标准化模板
│   └── escalation-template.md
└── project.config.json            # 项目配置（对外可见：真实路径等）
```

**指令系统行为：**
- Agent 通过 `mai` 写入 `.mai` 时，命令**自动同步**到 `projects/<项目名>/async/`（镜像层）
- `async/` 是供 **Sayo 观察系统运行状态**的可视化镜像，Agent 不得直接读取
- Agent 获取任何协作状态必须通过 `mai` 命令（`issue show/list`、`queue check`、`lock check` 等）
- 二者不一致时，以 `.mai`（指令系统）为 Source of Truth

### 3.4 团队文件柜（`~/.openclaw/workspace/agents/shared-workspace/`）

```
~/.openclaw/workspace/agents/shared-workspace/
├── agents-group-protocol/          # 群聊协作规范
├── scripts/                        # 指令系统代码（Agent 不可修改）
│   └── mai.py
├── exec-auth-log.md               # exec 授权记录（各 Agent 申请授权的流水）
├── safe-exec-list.json            # 安全命令白名单（免审批）
└── agent-info/                    # 各 Agent 元信息（能力描述、联系方式）
```

---

## 四、exec 权限管理

### P0-3 安全命令白名单

**所有 exec 权限归用户（Sayo）所有，但无害命令免审批。**

在 `~/.openclaw/workspace/agents/shared-workspace/safe-exec-list.json` 维护白名单：

```json
{
  "safe_commands": [
    { "cmd": "npm run test",          "agent": "programmer", "risk": "none" },
    { "cmd": "pytest",                "agent": "programmer", "risk": "none" },
    { "cmd": "git status",            "agent": "*",          "risk": "none" },
    { "cmd": "git diff",              "agent": "*",          "risk": "none" },
    { "cmd": "tsc --noEmit",          "agent": "programmer", "risk": "none" },
    { "cmd": "eslint",                "agent": "programmer", "risk": "none" },
    { "cmd": "python3 -m py_compile", "agent": "programmer", "risk": "none" },
    { "cmd": "ls",                    "agent": "*",          "risk": "none" },
    { "cmd": "cat",                   "agent": "*",          "risk": "none" }
  ],
  "high_risk_patterns": [
    "rm -rf", "chmod 777", "curl.*|bash.*pipe",
    "systemctl", "mkfs", "dd if="
  ]
}
```

### P0-3 审批被拒时的处理流程

```
1. 分析评估其他方式
2. 无法通过其他方式完成任务，主动暂停执行
3. 通过飞书 IM（私聊或群聊 channel）向用户发送权限申请
4. 申请内容必须包含：
   - 执行的具体命令或操作
   - 当前上下文和目的
   - 之前的重试次数（若有）
5. 等待用户授权，不得绕过
6. 用户授权后，Agent 将授权结论追加写入
   ~/.openclaw/workspace/agents/shared-workspace/exec-auth-log.md
```

### P0-3 禁止行为

- ❌ 不得在审批被拒后切换命令写法重新尝试
- ❌ 不得将 exec 任务拆解为多个"看起来无害"的子命令绕过审批
- ❌ 不得在未经用户授权的情况下变更操作方向
- ❌ 不得修改 `safe-exec-list.json`（该文件由用户专属维护）

---

## 五、心跳任务设计

### P2-2 心跳间隔设计

各 Agent 心跳**错开时间**，避免同一时刻竞争共享文件。使用质数间隔，避免最小公倍数陷阱：

| Agent | 心跳频率 | 核心巡逻内容 | 使用命令 |
|:---|:---|:---|:---|
| **programmer** | 每 17 分钟 | 检查 architect 批准方案；执行 diff 自审；检测逻辑漏洞 | `mai queue check architect-decisions --overdue` |
| **designer** | 每 29 分钟 | 处理 programmer 上报 Issue；检查 quick-fix 确认；检查 narrative 文本报告 | `mai queue blockers` |
| **architect** | 每 43 分钟 | 处理 designer 通过的新需求；处理 programmer 技术问题上报；处理 architect-reviews-designer 队列 | `mai queue check architect-decisions --overdue` |
| **techartist** | 每 47 分钟 | 检查渲染代码提交；运行性能基准；处理 quick-fix 反馈 | `mai queue check techartist-reviews` |
| **narrative** | 每 61 分钟 | 扫描 strings.json 与剧本一致性；处理 quick-fix 反馈 | `mai queue check narrative-reports` |

**心跳写入目标：**
- 通过 `mai log write` 写入审计历史
- 通过 `mai issue` 系列命令管理 Issue 生命周期

---

## 六、定时任务（Cron）

| 调度频率 | 任务 | 执行者 | 使用命令 |
|:---|:---|:---|:---|
| 每 1 小时 | 体验抽查 | designer | `mai queue check <queue> --overdue`（由 designer 心跳处理，无需独立 cron） |
| 每 2 小时 | 技术方案整理 | architect | `mai queue check architect-decisions` |
| 每 4 小时 | 代码逻辑巡检 | programmer | `mai queue check --overdue` |
| 每 6 小时 | strings.json 一致性扫描 | narrative | `mai queue check narrative-reports` |
| 每日 14:00 | 性能报告 | techartist | `mai queue check techartist-reviews` |
| 每日 18:00 | 协同状态汇总 | 全员顺序写入 | `mai daily-summary trigger`（Cron 仅触发事件，Agent 在心跳中写入） |

### 6.1 `mai daily-summary` 每日汇总

详细协议见 §2.4。

**Cron 触发：**
```bash
0 18 * * * mai daily-summary trigger
```

**流程：** Cron 触发 `trigger` → 各 Agent 心跳检查 `.daily-summary-event` 并调用 `write` → designer 调用 `collect` 生成汇总。

---

## 七、异步队列与并发控制（核心重构）

### P0-1 指令系统替代直接文件操作

**Agent 不得直接读写 `projects/<项目名>/async/` 下的任何队列文件，必须通过 `mai` 命令操作。**

指令系统内部维护 `.mai` 作为 Source of Truth，自动同步到 `async/` 镜像层。

#### Issue 文件格式（由 `mai` 管理，Agent 通过命令读写）

```markdown
# [REQ-003] <标题>

**发起方：** @<agent>
**处理方：** @<agent>
**创建时间：** <ISO 8601>
**状态：** 🔄 进行中 / ✅ 完成 / ⚠️ 阻塞 / ⏱️ 超时
**SLA 截止：** <ISO 8601>
**队列：** <queue>

---

## 问题描述

## 关联上下文

## 处理记录
- [<timestamp>] @<agent>: 创建
```

#### Agent 协作流程示例

```
# programmer 发现技术风险，创建 Issue
mai issue new architect-decisions "渲染管线方案技术评审"

# architect 心跳扫描到，认领 Issue
mai issue claim REQ-003

# architect 处理完成，发布结论
mai issue complete REQ-003 "技术方案可行，同意实现"

# designer 心跳检查队列状态
mai queue check architect-decisions

# programmer 查询是否有积压
mai queue blockers
```

#### 队列生命周期（4 步，通过命令执行）

```
1. 创建：发起方 → mai issue new <queue> <title>
                          → .mai/queues/<queue>/REQ-XXX.md 创建
                          → 自动同步到 async/<queue>/REQ-XXX.md
2. 认领：处理方 → mai issue claim <issue-id>
                          → .mai/locks/<issue-id>.lock 创建（原子锁）
                          → async/processing/<issue-id>.md 创建
3. 处理：处理方在 processing/ 目录下写入结论（通过 mai 读写）
4. 完成：mai issue complete <issue-id> <结论>
                → 结论归档至 .mai/decisions/<issue-id>.md
                → async/processing/ 下的文件彻底删除
```

#### 原子锁协议（`mai` 命令内部处理）

**设计原则：锁是协作资源，不是文件。** 使用 POSIX 文件锁（`flock(2)`）保证原子性，不依赖 `mkdir`/`rename` 等文件系统原子性假设。

```
# mai issue claim <issue-id> 执行时：
Step 1: 尝试对 .mai/locks/<issue-id>.lock 文件加 flock(LOCK_EX| LOCK_NB)
        → 加锁成功 → 继续 Step 2
        → 加锁失败（EWOULDBLOCK）→ 检查锁文件 age
           → age > 心跳间隔 × 1.5 → 强制关闭对方锁（LOCK.force_release），重试 Step 1
           → age ≤ 心跳间隔 × 1.5 → 报错退出（锁被其他进程持有）
Step 2: 在锁文件中写入 <agent>|<timestamp>
Step 3: 创建 .mai/processing/<issue-id>.md（持锁标记）
Step 4: 自动同步到 async/processing/<issue-id>.md
# 注意：flock 在进程退出时自动释放，无需手动 unlock
```

**持锁标记文件（processing/）的作用：**
- 标识该 Issue 正被处理，供其他 Agent 通过 `queue check` 查询
- flock 锁在进程结束时自动释放，但 processing/ 标记文件由 `issue complete` 命令显式删除
- 二者共同构成完整的锁状态表示

**锁超时强制释放（guardian 触发或 `mai lock force-release`）：**
```
mai lock force-release <issue-id>
# 检查锁文件 age：
#   age ≤ 心跳间隔 × 1.5 → 拒绝释放，报错（锁仍在有效期内）
#   age > 心跳间隔 × 1.5 → 强制删除锁文件 + processing/<issue-id>.md，强制关闭任何残留 flock
# guardian 进程扫描时，同样判定 age 超时后才释放
```

---

### P0-2 architect 事后否决降级路径

designer 通过方案后，若 architect 事后发现技术不可行：

```
designer 通过 → architect 审查通过 → 实现中
                            ↓
              architect 发现技术问题（事后）
                            ↓
              mai issue new architect-reviews-designer "<标题>"
              状态=⚠️降级申请，标记"TECH_BLOCKER"
                            ↓
              designer 心跳检测到（mai queue check architect-reviews-designer）
                            ↓
              若 designer 坚持 → [REPORT_TO_USER] 通知用户裁决
              若 designer 接受 → architect 撤销原批准，programmer 停实现
```

**时效限制（CRITICAL）：**
- architect 事后否决仅在**实现完成前**触发降级流程
- 实现完成后发现的技术问题，转为 **bug 处理流程**（不触发 architect-reviews-designer 队列）
- bug 由 programmer 评估优先级，architect 提供技术指导意见，不走终裁链

**撤销原批准操作路径：**
```
mai issue amend <issue-id> "architect 事后否决：<原因>"
# 在原 decisions/ 条目中追加修订记录，标记为"已撤销"
# 新 Issue 归档至 decisions/<new-id>.md
# 触发 programmer 停实现
```

**清理规则：**
- designer 认领时：`mai issue claim <issue-id>`（指令系统自动处理锁 + 同步）
- 流程完成后：`mai issue complete <issue-id> <结论>`（指令系统自动归档 + 清理）
- **不得留下「已认领但未归档」的残留文件**

---

### P1-1 超时通知合并机制

超时后**不立即通知用户**，先汇聚到 `designer-blockers/`，由 designer 心跳**合并为一条飞书消息**后发送。

#### P1-1 队列 SLA 定义（配置在 `.mai/config.json`）

| 队列 | 处理方 | SLA | 超时判定 |
|:---|:---|:---|:---|
| `programmer-questions/` | designer | 2h | 超过 SLA 截止时间即触发 |
| `architect-decisions/` | architect | 2h | 超过 SLA 截止时间即触发 |
| `techartist-reviews/` | designer | 4h | 超过 SLA 截止时间即触发 |
| `narrative-reports/` | designer | 4h | 超过 SLA 截止时间即触发 |
| `architect-reviews-designer/` | designer | 2h | 超过 SLA 截止时间即触发 |
| `quick-fix-requests/` | programmer | 1h | 超过 SLA 截止时间即触发 |

#### P1-1 超时检测与上报（由检测方通过命令处理）

**触发机制：超时检测是心跳 Skill 的第 3 步（见 §9.4）。** 每次心跳执行 `queue check <queue> --overdue` 时，若返回超时项，立即触发以下命令：

```
# 每次心跳的 queue check --overdue 返回超时项时，执行：
mai issue new designer-blockers "<超时描述>" --ref <issue-id>
# --ref：将原始超时 Issue 的链接和 SLA 信息附加到 blocker 内容中
# 模板：
#   [BLK-<编号>] <原始队列> 超时 <超时时长>（<原始Issue-ID> <标题>）
#   SLA：<原始SLA截止时间>
#   超时：<超时时长>
```

**心跳 Skill 中的超时处理（§9.4 每位 Agent 已包含）：**
- 第 3 步：`queue check <queue> --overdue` 返回超时项
- 第 4 步（超时处理）：对每个超时项执行 `mai issue new designer-blockers "..." --ref <id>`
- 第 5 步：`queue blockers`（检查是否有积压需上报用户）

**示例（architect 心跳检测 architect-decisions 超时）：**
```
$ mai queue check architect-decisions --overdue
# 返回：REQ-003（超时 2h）

$ mai issue new designer-blockers \
    "architect-decisions 超时 2h（REQ-003 渲染管线技术方案）" \
    --ref REQ-003
# 创建 BLK-001，状态=🔄进行中，队列=designer-blockers
# 超时 Issue REQ-003 保留在原队列，不移动
```

**去重规则：** 同一个 Issue 首次超时时创建 BLK；BLK 状态变为「已上报」后不再重复创建。

**写入权限（通过 `mai` 命令保证）：**
- `architect-decisions/` 超时 → **architect** 执行 `mai issue new designer-blockers ...`
- `programmer-questions/` 超时 → **designer** 执行 `mai issue new designer-blockers ...`
- `quick-fix-requests/` 超时 → **designer** 执行 `mai issue new designer-blockers ...`
- `techartist-reviews/` / `narrative-reports/` 超时 → **designer** 执行 `mai issue new designer-blockers ...`

#### P1-1 designer 心跳汇总（合并发送）

```
designer 心跳 → mai queue blockers
  → 若有积压 → 生成合并报告 → 一次性飞书发送
  → 若无积压 → 不发送任何消息
```

**合并报告格式：**

```
🤖 [Sakamichi] 协同超时汇总 | 2026-04-19 14:00

⚠️ architect-decisions: 超时 2h（REQ-003 技术方案）
⚠️ techartist-reviews: 超时 4h（渲染管线审查）

请介入：[链接到 designer-blockers/]
```

**去重规则 + 防止风暴机制：**

```
# queue check --overdue 内部逻辑（Issue 级标记）：
Step A: 读取 Issue 元数据，检查是否已有 escalated_blocker_id 字段
         → 已有字段 → 该 Issue 已上报过 Blocker，静默跳过（不再重复创建）
         → 无字段 → 继续 Step B
Step B: 创建 BLK-XXX
Step C: 在原始 Issue 元数据中写入 escalated_blocker_id: "BLK-XXX"
Step D: 下次 queue check --overdue 再次扫描到该 Issue 时，Step A 直接跳过
```

**解除标记条件（Issue 状态发生实质性转变时清除）：**
- Issue 被 `issue complete` → 标记清除（Issue 已解决，不再需要上报）
- Issue 被 `issue claim` → 标记清除（Issue 被处理中，超时状态已变化）

**效果：** Issue 超时 → 创建 Blocker → 持续超时不重复创建 Blocker → Issue 被处理/完成 → 标记清除 → 若再次超时则重新创建。彻底杜绝 Blocker 风暴。

**BLK 存储位置说明：**
- `designer-blockers/` 是普通 Issue 队列（可完成、可删除）
- `async/history/` 是 append-only 审计日志（不可删除、不可覆盖）
- 二者性质不同，BLK 完成操作不影响 history/ 的 append-only 约束

---

### P1-4 客观错误快通道

**分级处理原则：** 客观错误（可量化）走快通道，主观争议走标准终裁链。

| 类型 | 定义示例 | 处理路径 | SLA |
|:---|:---|:---|:---|
| **客观错误** | strings.json 拼写错误、DrawCall 超标、帧率低于阈值、资产路径失效 | narrative/techartist → 直接通知 programmer，抄送 designer | **1 小时** |
| **主观争议** | 体验感受、氛围风格、情感表达 | 走标准 designer 终裁链 | 2-4 小时 |

#### P1-4 快通道判定规则

**客观错误必须走快通道（不得走标准终裁链）：**
- narrative：strings.json 键值对不匹配、缺失必含键、JSON 语法错误、剧本关键场景缺失
- techartist：帧率 < 30FPS、DrawCall > 5000、显存超预算 10%、资产路径断裂

**快通道例外（不适用）：** 若客观错误由 designer 主动决策引起（如明确要求某特效无视性能），则视为 designer 已知的 trade-off，不触发快通道。

**凭证要求（CRITICAL）：** designer 已知 trade-off 必须以 Issue 记录为凭证，口头说明无效。具体要求：
- narrative/techartist 发现问题时，若怀疑为例外，必须先确认是否存在相关 designer 签字确认的 Issue
- 若无 Issue 记录 → **不得**判定为例外，必须走快通道
- 若有 Issue 记录 → 记录至报告，附上 Issue 链接，走标准链

#### P1-4 快通道流程（通过命令执行）

```
narrative/techartist 发现问题
  → 判定：是否为例外（designer 已知 trade-off）？
      → 是：记录至报告，走标准链
      → 否：继续快通道

  → mai issue new quick-fix-requests "<描述>"
  → 同时通知 programmer（执行修复）和 designer（知晓，不审批）
  → programmer 修复完成 → mai issue complete <issue-id> <结论>
  → 结论归档至 .mai/decisions/<issue-id>.md
  → 若 1 小时无响应 → mai issue new designer-blockers "<超时描述>"
```

#### P1-4 禁止行为

- ❌ 快通道不得用于主观争议（体验/风格/氛围）
- ❌ narrative/techartist 不得以快通道为名绕过 designer 做体验决策
- ❌ programmer 不得以「快通道修复」为由自行变更实现方案

---

### P2-1 冲突升级标准化模板

讨论 3 轮无果后，使用 `issue escalate` 命令将冲突升级写入 `architect-reviews-designer` 队列：

```
mai issue escalate <issue-id>
# 将原始 Issue 内容填充到冲突升级模板，直接创建 architect-reviews-designer Issue
# 原始 Issue 的所有字段（发起方、冲突对象、问题描述、处理记录）自动填充到模板
# 状态初始为 🔄 进行中，标记 TECH_BLOCKER
```

**执行步骤（原子化，无需手动复制）：**
1. `mai issue escalate <issue-id>` 读取原 Issue 内容
2. 填充冲突升级模板，生成 architect-reviews-designer Issue
3. 直接写入 `.mai/queues/architect-reviews-designer/`
4. 输出新 Issue ID（如 REQ-010）和状态

**`escalation gen` 命令（仍保留，仅用于查看模板内容）：**
```
mai escalation gen <issue-id>
# 打印填充好的冲突升级模板到 stdout，不写入文件
# 用途：在创建前确认模板内容是否符合预期
```

**冲突升级 Issue 内容模板：**

```markdown
# [REQ-010] ⚠️ [冲突升级] <类型>

**发起方：** @<Agent>
**冲突对象：** @<Agent>
**原始 Issue：** @<原始issue-id>
**创建时间：** <ISO 8601>
**状态：** 🔄 进行中
**标记：** TECH_BLOCKER

## 核心分歧
<一句话描述>

## 立场 A
<Agent A 的主张 + 依据>

## 立场 B
<Agent B 的主张 + 依据>

## 客观数据（如有）
<可量化的事实>

## 建议选项
- [A] <选项描述>
- [B] <选项描述>

**请用户 (Sayo) 裁决：** [A] / [B]
```

---

## 八、文件存储规范

### P1-5 真实项目地址配置化

在 `projects/<项目名>/project.config.json` 中配置：

```json
{
  "project_name": "Sakamichi",
  "source_root": "/mnt/d/Unity/Projects/Sakamichi",
  "artifacts": {
    "strings": "/mnt/d/Unity/Projects/Sakamichi/Assets/Localization/strings.json",
    "scripts": "/mnt/d/Unity/Projects/Sakamichi/Assets/Scripts",
    "scenes": "/mnt/d/Unity/Projects/Sakamichi/Assets/Scenes",
    "config": "/mnt/d/Unity/Projects/Sakamichi/ProjectSettings"
  },
  "readonly": true,
  "vcs": "git"
}
```

**约束：除非 exec 权限经用户审批通过，否则不得向 `source_root` 写入任何文件。**

### 存储分层

| 存储位置 | 内容 | 性质 |
|:---|:---|:---|
| **飞书云文档** | 周报、决策记录、知识库、架构文档、设计规范 | 团队知识沉淀，面向人类可读 |
| **`project.config.json` 定义的真实项目地址** | 源代码、游戏资源、strings.json、配置文件 | 实际开发材料，版本控制，本地存储 |
| **`.mai`** | 协作元数据（Issue、锁、队列、审计日志） | 指令系统内部存储，Source of Truth |
| **`projects/<项目名>/`** | 团队协作产生的工作文件（队列镜像、报告、日志、锁镜像） | 对外通信协议，Source of Truth 镜像 |

### 强制约束

```
❌ 禁止将源代码、strings.json、游戏资源等开发产物上传到飞书
❌ 禁止将报告/文档等知识资料当作代码交付物使用
❌ 禁止将工作文件写入 memory/（memory 仅用于 Agent 记忆）
❌ 禁止将项目协作文件写入 agents/shared-workspace/（该目录不含项目内容）
❌ Agent 不得直接读写 projects/<项目名>/async/ 下的队列文件（必须通过 mai 命令）
```

---

## 九、Skill 配置矩阵

### 9.1 共享 Skill（所有 Agent 必须加载）

- `agents-group-protocol` — 群聊协作规范
- `mai` — 协作命令工具（所有 Issue/队列/锁操作必须通过此 Skill）

### 9.2 各 Agent 专属 Skill

| Agent | 专属 Skill | 职责边界 |
|:---|:---|:---|
| **designer** | `requirement-analysis` | 解析体验需求，输出可评审的体验标准 |
| | `user-document-writing` | 维护体验验收清单（acceptance checklist） |
| **architect** | `architecture-designing` | 技术方案设计、系统边界分析 |
| | `system-boundary-analysis` | 外部依赖和接口契约梳理 |
| **programmer** | `software-dev-autopilot` | 端到端开发流程（需求→实现） |
| | `development-document-writing` | 维护实现文档和代码注释规范 |
| **narrative** | `blackbox-analysis` | 从 strings.json / 剧本提取文本实体关系 |
| | *(自建一致性 Skill）* | strings.json ↔ 剧本双向比对；含客观错误检测（快通道触发） |
| **techartist** | `video-frames` | 截取渲染画面进行美术评审 |
| | `blackbox-analysis` | 提取渲染管线外部 API 表面 |
| | *(自建性能 Skill）* | 帧率 / DrawCall / 显存监控；含客观错误阈值检测（快通道触发） |

### 9.3 禁止越权 Skill（deny list）

```yaml
# programmer/SKILL.md
skills:
  deny:
    - requirement-analysis    # 体验标准不由 programmer 解释
    - architecture-designing   # 技术方案否决权归 architect

# architect/SKILL.md
skills:
  deny:
    - user-document-writing   # 体验文档归 designer
    - software-dev-autopilot   # 实现推进归 programmer

# narrative/SKILL.md
skills:
  deny:
    - requirement-analysis    # 体验判断权归 designer

# techartist/SKILL.md
skills:
  deny:
    - architecture-designing  # 技术方案归 architect
```

### 9.4 Agent 命令使用规范（新增）

所有 Agent 的 Skill 配置中必须写入以下命令使用约束：

**programmer 心跳 Skill 必须包含：**
```yaml
# 每次心跳必须执行（6 步标准化流程）：
- mai log write programmer heartbeat "正常" "进行中"
- mai queue check architect-decisions --overdue  # 检查是否有待处理技术决策超时
- mai queue check quick-fix-requests --overdue    # 检查快通道修复状态
- mai queue check programmer-questions --overdue  # 检查自身队列超时项（其他人向 programmer 提交的 Issue）
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue blockers                              # 检查是否有积压需要上报
- mai daily-summary write programmer "<当日状态摘要>"  # 检查 .daily-summary-event，若轮到自己则写入
```

**designer 心跳 Skill 必须包含：**
```yaml
# 每次心跳必须执行（6 步标准化流程）：
- mai log write designer heartbeat "正常" "进行中"
- mai queue blockers                             # 合并检查所有 blocker（包含自己上轮写入的）
- mai queue check programmer-questions --overdue  # 检查 programmer 上报问题的超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue check architect-reviews-designer --overdue  # 检查事后否决通道超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai daily-summary write designer "<当日状态摘要>"  # 检查 .daily-summary-event，若轮到自己则写入
```

**architect 心跳 Skill 必须包含：**
```yaml
# 每次心跳必须执行（6 步标准化流程）：
- mai log write architect heartbeat "正常" "进行中"
- mai queue check architect-decisions --overdue  # 检查技术方案审批超时项
- mai queue check architect-reviews-designer --overdue  # 处理事后否决通道
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue blockers                              # 检查是否有积压需要上报
- mai daily-summary write architect "<当日状态摘要>"  # 检查 .daily-summary-event，若轮到自己则写入
```

**narrative 心跳 Skill 必须包含：**
```yaml
# 每次心跳必须执行（6 步标准化流程）：
- mai log write narrative heartbeat "正常" "进行中"
- mai queue check narrative-reports --overdue    # 检查文本审查报告超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue check quick-fix-requests --overdue   # 检查快通道反馈超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue blockers                             # 检查是否有积压需要上报
- mai daily-summary write narrative "<当日状态摘要>"  # 检查 .daily-summary-event，若轮到自己则写入
```

**techartist 心跳 Skill 必须包含：**
```yaml
# 每次心跳必须执行（6 步标准化流程）：
- mai log write techartist heartbeat "正常" "进行中"
- mai queue check techartist-reviews --overdue   # 检查渲染代码审查超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue check quick-fix-requests --overdue   # 检查快通道反馈超时项
# 超时处理（若有超时项 → 写入 designer-blockers）：
#   mai issue new designer-blockers "超时描述" --ref <issue-id>
- mai queue blockers                             # 检查是否有积压需要上报
- mai daily-summary write techartist "<当日状态摘要>"  # 检查 .daily-summary-event，若轮到自己则写入
```

### 9.5 Agent 信息获取强制约束

**获取 Issue 信息：**
```yaml
# 禁止：
- cat projects/<项目名>/async/programmer-questions/REQ-001.md

# 必须：
- mai issue show REQ-001
- mai issue list programmer-questions
- mai queue check architect-decisions --overdue
```

**获取队列状态：**
```yaml
# 禁止：
- ls projects/<项目名>/async/quick-fix-requests/

# 必须：
- mai queue check quick-fix-requests
- mai queue blockers
```

**获取锁状态：**
```yaml
# 禁止：
- cat projects/<项目名>/locks/REQ-003.lock

# 必须：
- mai lock check REQ-003
```

**Rationale：** `async/` 是对 Sayo 开放的可视化镜像，内容可能与 `.mai` 存在同步延迟。Agent 必须通过 `mai` 命令从 `.mai` 获取实时数据，禁止直接读取 `async/` 下的任何文件。

---

## 十、Bitable 待办管理

通过飞书多维表格组织维护所有 Agent 待处理项，**自动同步而非人工维护**：

```
Agent 心跳 → mai issue new/list/complete 等命令
          → 指令系统写入 .mai
          → 自动同步到 bitable（通过 feishu_bitable_app_table_record API）
```

### P1-2 bitable 同步容错

在 `bitable-sync/` 下维护 `sync-state.json`（由 `mai` 命令自动更新）：

```json
{
  "last_sync": "2026-04-19T13:45:00+08:00",
  "status": "ok",
  "failed_items": [],
  "retry_count": 0,
  "max_retries": 3
}
```

**`failed_items` 格式定义：**
```json
[
  {
    "issue_id": "REQ-003",
    "operation": "create|update|delete",
    "error": "rate_limit_exceeded|network_error|permission_denied",
    "attempted_at": "2026-04-19T13:44:00+08:00"
  }
]
```

**查询命令：**
```
mai bitable sync-status
```

**容错逻辑：**
- API 调用失败 → `status: failed`，记录 `failed_items`，重试 +1
- 重试 3 次仍失败 → `status: stuck`，**停止重试**，在 `designer-blockers/` 写入告警 Issue，同时**通知相关 Agent**：
  - 若对应的 Issue 在 `quick-fix-requests/` → 同时通知 programmer（已修复但同步失败）
  - 其他队列 → 只通知 designer（由 designer 决定处理方式）
- `status: ok` 后清除 `failed_items` 和 `retry_count`

**数据一致性原则：** `.mai` 是 Source of Truth；bitable 是可视化层面副本；二者不一致时以 `.mai` 为准。

---

## 十一、安全与审计

### 11.1 最小权限访问控制（通过命令保证）

| 目录 | 允许写入 | 允许读取 | 通过命令 |
|:---|:---|:---|:---|
| `.mai/queues/<queue>/` | 指令系统内部 | 指令系统内部 | `mai issue new` |
| `async/<queue>/` | **Agent 不可直接写入** | 仅 Sayo 可读（可视化镜像） | 通过命令同步（Agent 使用 `issue show/list` 获取信息） |
| `.mai/processing/` | 指令系统内部 | 指令系统内部 | `mai issue claim` |
| `.mai/locks/` | 指令系统内部 | 所有 Agent（通过 `mai lock check`） | `mai lock *` |
| `.mai/decisions/` | 指令系统内部 | 所有 Agent（只读） | `mai issue complete` |
| `async/history/` | 无（append-only） | 所有人 | `mai log write` |

### 11.2 锁文件访问

| 文件 | 允许操作 |
|:---|:---|
| `.mai/locks/*.lock` | 创建/删除由 `mai` 命令处理（持锁方或超时强制） |
| 查询锁状态 | `mai lock check <issue-id>`（所有 Agent） |

### 11.3 审计日志

每次通过命令操作协作数据时，自动追加到 `.mai/history/YYYY-MM-DD.log`（append-only）：

```
[2026-04-19 11:35] programmer@heartbeat → architect-decisions/REQ-001.md [创建]
[2026-04-19 11:52] architect@heartbeat → architect-decisions/REQ-001.md [认领]
[2026-04-19 12:10] architect@heartbeat → architect-decisions/REQ-001.md [完成]
```

**Agent 可通过以下命令查看审计历史：**
```
mai log history [--date YYYY-MM-DD] [--agent <agent>]
```

---

## 附录 A：Agent 协作标准流程（命令版）

### A.1 典型 programmer 工作流

```
1. 心跳启动
   $ mai queue check architect-decisions --overdue
   $ mai log write programmer heartbeat "正常" "进行中"

2. 发现逻辑漏洞
   $ mai issue new programmer-questions "AI 路径在边缘情况出错"
   # 或走快通道（如果可量化）
   $ mai issue new quick-fix-requests "strings.json 拼写错误：bananer → banana"

3. 收到快通道修复请求
   $ mai issue list quick-fix-requests
   $ mai issue claim FIX-001
   # 执行修复
   $ mai issue complete FIX-001 "已修复拼写错误"
```

### A.2 典型 architect 工作流

```
1. 心跳启动
   $ mai queue check architect-decisions
   $ mai log write architect heartbeat "正常" "进行中"

2. 处理技术方案审批
   $ mai queue check architect-decisions
   $ mai issue claim REQ-003
   # 审查方案
   $ mai issue complete REQ-003 "技术方案可行，同意实现"

3. 事后发现技术问题
   $ mai issue new architect-reviews-designer "渲染管线事后否决：DX12 支持问题"
```

### A.3 典型 designer 工作流

```
1. 心跳启动
   $ mai queue blockers  # 合并检查 blocker
   $ mai log write designer heartbeat "正常" "进行中"

2. 处理 programmer 上报问题
   $ mai queue check programmer-questions
   $ mai issue list programmer-questions
   # 认领并处理
   $ mai issue claim REQ-005
   $ mai issue complete REQ-005 "体验标准通过，同意实现"

3. 处理超时积压
   $ mai queue blockers
   # 若有积压 → 生成合并报告 → 飞书通知用户
```

### A.4 每日定时任务（cron）

```
# 每5分钟：守护进程，释放过期的 .daily-lock
*/5 * * * * mai lock guardian

# 每日18:00：触发每日汇总事件
0 18 * * * mai daily-summary trigger
```

**Agent 心跳汇总处理（第 6 步）：**
- 各 Agent 心跳第 6 步执行 `mai daily-summary write <agent> "<当日摘要>"`
- 命令内部自动检查 `.daily-summary-event` 是否存在、是否轮到本 Agent；若不符合条件则幂等跳过
- designer 在最后执行 `mai daily-summary collect` 生成最终汇总

> 注：体验抽查（每1小时）由 designer 心跳轮次处理，无需独立 cron。

---

## 附录 B：指令系统文件清单

| 文件 | 位置 | 说明 |
|:---|:---|:---|
| `mai.py` | `~/.openclaw/workspace/agents/shared-workspace/scripts/` | 主入口脚本 |
| `mai SKILL.md` | `~/.openclaw/workspace/agents/shared-workspace/scripts/` | Skill 配置 |
| `queues.yaml` → 取消 | `.mai/config.json` 内嵌 | 队列配置移入项目内部配置 |
| `safe-exec-list.json` | `~/.openclaw/workspace/agents/shared-workspace/` | exec 白名单（用户维护） |
| `exec-auth-log.md` | `~/.openclaw/workspace/agents/shared-workspace/` | exec 授权记录 |
| `project.config.json` | `projects/<项目名>/` | 对外项目配置 |
| `.mai/config.json` | `projects/<项目名>/.mai/` | 内部协作配置（SLA、心跳间隔） |
