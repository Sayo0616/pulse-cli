# Team Agent 命令行系统设计文档

> 文档版本：v1.0（2026-04-19）
> 基于：`AGENTS_COLLAB_DESIGN.md` v1.3
> 目标：为 Sakamichi 游戏开发团队的五个 Agent 提供标准化 CLI 工具，封装协作流程中的高频操作。

---

## 一、设计目标与约束

### 1.1 核心目标

- **降低协作摩擦**：把文档中定义的标准操作（Issue 生命周期、队列扫描、锁管理）封装为可验证、可脚本化的命令
- **消除人工失误**：SLA 计算、ID 生成、文件路径拼接等操作由程序保证一致性
- **可被 Agent 调用**：命令可在 exec 中运行，输出格式支持机器解析（JSON），也支持人类可读（彩色富文本）

### 1.2 设计约束

| 约束 | 说明 |
|:---|:---|
| **单文件入口** | 尽量单一可执行文件，减少部署复杂度 |
| **幂等优先** | 所有写操作尽量幂等，重复执行不破坏状态 |
| **Source of Truth** | `projects/<项目名>/async/` 是唯一真实数据源，命令不维护独立状态 |
| **禁止重定向语法** | exec 相关命令不使用 `2>&1` `>/dev/null` 等 |
| **最小依赖** | 仅使用 Python 3 标准库 + 已有 feishu plugin tools |

---

## 二、系统架构

### 2.1 命令结构

```
mai [全局选项] <子命令> [参数] [选项]
```

**全局选项：**
```
--project <项目名>      # 指定项目（默认从环境变量或当前目录推断）
--format <json|text>    # 输出格式，json | text（默认 text）
--dry-run               # 只展示将执行的操作，不实际修改文件
--help
```

### 2.2 子命令树

```
mai
├── issue
│   ├── new <queue> <title>          # 创建 Issue
│   ├── claim <issue-id>             # 认领 Issue（持锁）
│   ├── complete <issue-id> <结论>   # 完成 Issue（归档 + 解锁）
│   ├── list [queue]                 # 列出 Issue，默认全部
│   └── show <issue-id>             # 显示 Issue 详情
├── queue
│   ├── check [queue]                # 扫描队列状态（超时 / 积压）
│   └── blockers                      # 合并输出所有 designer-blockers
├── lock
│   ├── check <issue-id>             # 检查锁状态
│   └── force-release <issue-id>     # 超时强制释放锁
├── log
│   └── write <agent> <type> <摘要> <状态>  # 写入标准化工作记录
├── escalation
│   └── gen <issue-id>              # 从模板生成冲突升级报告
├── bitable
│   ├── sync-status                 # 查看同步状态
│   └── retry                        # 重试失败的同步项
└── exec
    └── safe-check <cmd>             # 检查命令是否在白名单中
```

### 2.3 模块结构（内部）

```
mai.py          # 入口文件（单一可执行脚本）
scripts/
├── issue_ops.py       # Issue 生命周期逻辑
├── queue_ops.py       # 队列扫描逻辑
├── lock_ops.py        # 原子锁操作
├── log_ops.py         # 工作记录写入
├── escalation_ops.py  # 冲突升级模板生成
├── bitable_ops.py     # bitable 同步状态查询
└── safe_exec.py       # exec 白名单检查
config/
├── queues.yaml         # 队列定义 + SLA 配置
└── project.template.yaml  # 项目配置模板
templates/
└── escalation-template.md  # 冲突升级模板（复制自 AGENTS_COLLAB_DESIGN.md §七·P2-1）
```

> **文件位置**：放在 `~/.openclaw/workspace/agents/shared-workspace/scripts/` 下，作为团队共享工具，不属于任一特定项目。

---

## 三、命令详解

### 3.1 `issue` 子命令组

#### `issue new <queue> <title>`

**功能：** 在指定队列中创建新 Issue，自动分配 ID，写入 `async/<queue>/REQ-XXX.md`。

**参数：**
| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `queue` | string | 队列名（见下表） |
| `title` | string | Issue 标题 |

**支持的队列与 SLA：**

| queue 值 | 处理方 | SLA |
|:---|:---|:---|
| `programmer-questions` | designer | 2h |
| `architect-decisions` | architect | 2h |
| `techartist-reviews` | designer | 4h |
| `narrative-reports` | designer | 4h |
| `architect-reviews-designer` | designer | 2h |
| `quick-fix-requests` | programmer | 1h |

**自动行为：**
- ID 自增：从 `async/<queue>/` 中找最大编号，+1
- SLA 截止时间：`now + SLA`
- 写入状态：`🔄 进行中`

**输出示例（text 模式）：**
```
✅ Issue 创建成功
   ID:    REQ-003
   Queue: architect-decisions
   SLA:   2026-04-19 16:36 +0800
   Path:   projects/game-developing-team/async/architect-decisions/REQ-003.md
```

---

#### `issue claim <issue-id>`

**功能：** 认领 Issue，启动原子锁协议。

**参数：**
| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `issue-id` | string | Issue ID，格式 `REQ-XXX` |

**原子锁协议步骤：**
1. 检查 `locks/<issue-id>.lock` 是否存在
   - 存在 → 检查 timestamp 是否超时（> 心跳间隔 × 1.5）
     - 超时 → 强制删除旧锁，继续
     - 未超时 → 报错退出
2. 创建 `locks/<issue-id>.lock`，内容：`echo "<agent>|<timestamp>"`
3. 创建 `async/processing/<issue-id>.md`（持锁标记文件）
4. 将原 Issue 文件标记为"已认领"（在文件头部加 `**认领方：** @<agent>`）

**输出示例：**
```
🔒 Issue 认领成功
    ID:    REQ-003
    Lock:  locks/REQ-003.lock
    直到:  2026-04-19 15:xx +0800（超时时间）
```

---

#### `issue complete <issue-id> <结论文件>`

**功能：** 完成 Issue，归档到 `decisions/`，清理锁文件。

**参数：**
| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `issue-id` | string | Issue ID |
| `结论` | string | 结论描述（直接写入 `decisions/<issue-id>.md` 的摘要） |

**步骤：**
1. 验证锁是否存在（自己持有或已超时）
2. 将 Issue 结论写入 `decisions/<issue-id>.md`
3. 删除 `locks/<issue-id>.lock`
4. 删除 `async/processing/<issue-id>.md`
5. 删除原 `async/<queue>/<issue-id>.md`
6. 追加审计日志到 `async/history/YYYY-MM-DD.log`

**输出示例：**
```
✅ Issue 完成
    ID:     REQ-003
    归档至: decisions/REQ-003.md
    锁已释放
```

---

#### `issue list [queue]`

**功能：** 列出 Issue，默认全部队列，支持 `--status` 过滤。

**选项：**
| 选项 | 说明 |
|:---|:---|
| `--queue <queue>` | 只显示指定队列 |
| `--status <status>` | 过滤状态：`🔄进行中` `✅完成` `⚠️阻塞` `⏱️超时` |
| `--overdue` | 只显示超过 SLA 的 Issue |

---

#### `issue show <issue-id>`

**功能：** 显示 Issue 完整内容，包含处理记录时间线。

---

### 3.2 `queue` 子命令组

#### `queue check [queue]`

**功能：** 扫描队列，返回汇总状态。

**输出格式：**
```
队列                    | 待认领 | 进行中 | 超时    | 积压风险
:---------------------- | -----: | -----: | ------: | --------
programmer-questions    |      2 |      1 |  1 (2h) | ⚠️
architect-decisions     |      0 |      3 |  0      | —
techartist-reviews      |      1 |      0 |  0      | —
quick-fix-requests      |      0 |      1 |  0      | —
```

**超时判定规则：**
- 读取 `SLA 截止` 字段，与当前时间比较
- 超时 → 状态显示 `⏱️超时` + 超时时长
- SLA 剩余 < 30min → 标注 `⚠️即将超时`

---

#### `queue blockers`

**功能：** 合并输出所有 `designer-blockers/` 下的积压 Issue。

**输出格式：**
```
🚧 当前 Blockers（合并报告）
─────────────────────────────────────────────
[BLK-001] architect-decisions 超时 2h（REQ-003 技术方案）
[BLK-002] quick-fix-requests 超时 1h（FIX-001 拼写错误）
─────────────────────────────────────────────
共 2 项 blocker，建议介入。
```

---

### 3.3 `lock` 子命令组

#### `lock check <issue-id>`

**功能：** 检查锁文件状态。

**输出：**
```
锁状态检查: REQ-003
  文件:    locks/REQ-003.lock
  存在:    ✅ 是
  持有者:  architect
  创建于:  2026-04-19 14:40 +0800
  超时:    ⚠️ 超时（超过 43min × 1.5 = 64min）
  操作:    可强制释放
```

---

#### `lock force-release <issue-id>`

**功能：** 强制删除超时锁文件。

**安全约束：**
- 仅在锁文件 age > 心跳间隔 × 1.5 时可执行
- 正常锁不可强制释放（报错）

---

### 3.4 `log write` 命令

**参数：**
| 参数 | 说明 |
|:---|:---|
| `agent` | Agent 名（designer/architect/programmer/narrative/techartist） |
| `type` | 任务类型（heartbeat/cron/issue 处理/报告） |
| `摘要` | 简短描述 |
| `status` | `完成` `阻塞` `进行中` `超时` |

**输出格式（标准化 Markdown）：**
```markdown
## [2026-04-19 14:40] architect - 技术方案审查

**摘要：** REQ-003 渲染管线方案审查通过
**状态：** ✅ 完成
**关联方：** @designer
**下一步：** 通知 programmer 开始实现
```

---

### 3.5 `escalation gen <issue-id>` 命令

**功能：** 读取 Issue 内容，输出填充好的冲突升级模板（不写入文件，只打印）。

**输出：** 直接打印 `templates/escalation-template.md` 格式，方便 Agent 复制到 `async/architect-reviews-designer/` 创建新 Issue。

---

### 3.6 `bitable sync-status` 命令

**功能：** 读取 `projects/<项目名>/bitable-sync/sync-state.json`，格式化输出。

**输出示例：**
```
Bitable 同步状态
  上次同步:  2026-04-19 14:30 +0800
  状态:     ✅ ok
  失败项:   无
  重试次数: 0/3
```

---

### 3.7 `exec safe-check <cmd>` 命令

**功能：** 检查给定命令是否命中白名单（`safe-exec-list.json`）。

**输出：**
```
命令: git diff
白名单命中: ✅ risk=none（git diff）
执行结果: 可直接放行，无需审批
```

---

## 四、文件格式规范

### 4.1 Issue 文件格式

所有 Issue 文件使用以下统一头部：

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

### 4.2 锁文件格式

```
<agent>|<timestamp>
```

示例：`architect|1745049600000`

### 4.3 审计日志格式

每行一条，append-only：

```
[<timestamp>] <agent>@<操作类型> → async/<queue>/<issue-id> [<操作>][<详情>]
```

---

## 五、项目配置

### 5.1 项目配置文件

每个项目在 `projects/<项目名>/project.config.json` 中配置（继承自 AGENTS_COLLAB_DESIGN.md §八·P1-5），CLI 工具直接读取此文件获取：

- `source_root`：真实项目路径（只读）
- `async_root`：`projects/<项目名>/async/`
- `decisions_root`：`projects/<项目名>/decisions/`
- `locks_root`：`projects/<项目名>/locks/`
- 心跳间隔（用于锁超时计算）

### 5.2 默认项目推断顺序

```
1. --project 全局选项
2. 环境变量 AGENTS_PROJECT
3. 当前工作目录（向上查找 projects/*/project.config.json）
4. 报错要求指定
```

---

## 六、错误处理

| 错误类型 | 处理方式 |
|:---|:---|
| 队列不存在 | 报错退出，提示可用队列列表 |
| Issue ID 不存在 | 报错退出 |
| 锁已被持有（未超时） | 报错退出，显示持有者和超时时间 |
| 文件写入冲突 | 原子操作：先写 `.tmp`，再 rename |
| 超时参数不合法 | 报错退出 |
| 项目配置不存在 | 报错退出，提示初始化 |

---

## 七、部署与使用

### 7.1 安装

```bash
# 复制到 PATH 中
cp mai.py /usr/local/bin/mai
chmod +x /usr/local/bin/mai

# 或者创建别名
alias mai='python3 ~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py'
```

### 7.2 Agent 调用示例

在 Agent 的心跳 Skill 中调用：

```bash
# 创建 Issue
mai issue new architect-decisions "渲染管线技术方案评审"

# 检查超时
mai queue check programmer-questions --overdue

# 认领 Issue（由持有锁的 Agent 执行）
mai issue claim REQ-003

# 完成 Issue
mai issue complete REQ-003 "方案通过，同意实现"
```

### 7.3 依赖

- Python 3.8+
- PyYAML（用于读取队列配置 `queues.yaml`）
- 标准库：`json`, `pathlib`, `datetime`, `re`, `typing`

---

## 八、待定项（实现前确认）

| 项 | 问题 |
|:---|:---|
| **Python vs Shell** | 用 Python 实现（可维护性更强）还是纯 Shell（零依赖）？ |
| **queues.yaml 维护者** | 队列 SLA 变更是否需要版本控制？谁负责更新？ |
| **project.config.json 依赖** | 是否强制要求此文件存在？部分旧项目可能缺失 |
| **JSON 输出格式** | 是否需要严格定义 JSON schema？供哪些下游消费？ |
| **Agent 调用认证** | 命令是否需要携带调用者身份（如 `--agent architect`）？如何防止冒充？ |

---

## 九、优先级排序

实现按以下顺序分阶段进行：

| 阶段 | 命令 | 理由 |
|:---|:---|:---|
| **Phase 1** | `issue new` `issue list` `queue check` | 最高频、最独立 |
| **Phase 2** | `issue claim` `issue complete` `lock check` | 依赖锁协议，并行实现 |
| **Phase 3** | `queue blockers` `log write` `escalation gen` | 辅助功能 |
| **Phase 4** | `bitable sync-status` `exec safe-check` | 依赖外部状态 |

---
