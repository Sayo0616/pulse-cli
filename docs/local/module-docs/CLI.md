> 本文档归属：CLI.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §二

## 二、指令系统（CLI）概述

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
