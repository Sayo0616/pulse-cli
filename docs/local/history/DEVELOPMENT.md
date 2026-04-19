# Mai CLI 开发文档

> 文档版本：v1.0（2026-04-19）
> 源码：`~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py`
> 依赖：Python 3 标准库（argparse / pathlib / datetime / fcntl / json / shutil / re / os / sys）

---

## 一、系统概述

`mai` 是游戏开发团队五个 Agent（designer / architect / programmer / narrative / techartist）的协作指令系统。它将所有协作元数据（Issue 队列、锁状态、审计日志、每日汇总）封装为 CLI 命令，Agent 不得直接读写 `.mai/` 目录，只能通过 `mai` 命令操作。

### 设计原则

| 原则 | 说明 |
|:---|:---|
| **元数据命令化** | 所有协作状态只能通过 CLI 命令操作，禁止直读 `.mai/` |
| **Source of Truth vs 镜像** | `.mai/` 是内部真实数据源；`projects/<proj>/async/` 是供人类观察的可视化镜像 |
| **幂等优先** | 所有写操作可重复执行而不破坏状态 |
| **flock 原子锁** | 使用 POSIX `fcntl.flock()` 而非文件存在检测，支持进程崩溃自动释放 |
| **零外部依赖** | 仅用 Python 3 标准库，部署简单 |

---

## 二、目录结构

### 2.1 部署位置

```
~/.openclaw/workspace/agents/shared-workspace/
├── scripts/
│   ├── mai.py              # 主入口（~1,300 行，所有命令实现）
│   ├── __init__.py
│   ├── issue_ops.py          # 骨架占位（mai.py 内联实现）
│   ├── queue_ops.py          # 骨架占位
│   ├── lock_ops.py           # 骨架占位
│   ├── log_ops.py            # 骨架占位
│   ├── daily_summary_ops.py  # 骨架占位
│   ├── escalation_ops.py     # 骨架占位
│   ├── bitable_ops.py        # 骨架占位
│   ├── safe_exec.py          # 骨架占位
│   ├── project_ops.py        # 骨架占位
│   └── mai_skills/
│       └── SKILL.md          # Agent Skill 使用说明
├── templates/
│   └── escalation-template.md
└── safe-exec-list.json
```

### 2.2 项目内部结构（每个项目独立）

```
projects/<项目名>/
├── .mai/                        # 内部真实数据源（对 Agent 隐藏）
│   ├── config.json                # 项目配置（队列 SLA / 心跳间隔）
│   ├── queues/
│   │   ├── programmer-questions/  # REQ-001.md ...
│   │   ├── architect-decisions/
│   │   ├── techartist-reviews/
│   │   ├── narrative-reports/
│   │   ├── architect-reviews-designer/
│   │   ├── designer-blockers/
│   │   └── quick-fix-requests/    # FIX-001.md ...
│   ├── processing/                # 持锁中的 Issue（REQ-001.md）
│   ├── locks/                     # flock 锁文件（REQ-001.lock）
│   │   └── .daily-lock            # 每日汇总顺序锁
│   ├── decisions/                  # 归档结论（REQ-001.md）
│   ├── history/
│   │   ├── YYYY-MM-DD.log         # append-only 审计日志
│   │   └── daily-YYYY-MM-DD/      # 每日汇总各 Agent 摘要
│   │       ├── programmer.md
│   │       └── ...
│   └── events/
│       └── .daily-summary-event    # 每日汇总触发标志
├── async/                         # 人类可视化镜像（Agent 禁止直读）
│   ├── programmer-questions/       # .mai/queues/ 的镜像
│   ├── architect-decisions/
│   ├── ...（队列目录，同上）
│   ├── processing/                # 处理中 Issue 镜像
│   ├── history/
│   │   └── YYYY-MM-DD.log         # 审计日志镜像
│   └── decisions/                  # 归档结论镜像
├── reports/
│   └── daily-YYYY-MM-DD-summary.md # 最终汇总报告（designer collect 生成）
├── project.config.json             # 项目元配置
└── templates/
    └── escalation-template.md
```

---

## 三、命令参考

### 3.1 全局选项

```
mai [--project <项目名>] [--format json|text] [--dry-run] <子命令>
```

| 选项 | 说明 |
|:---|:---|
| `--project` | 指定项目（默认从 `AGENTS_PROJECT`/`MAI_PROJECT` 环境变量推断） |
| `--format json` | 结构化 JSON 输出（适合程序消费） |
| `--dry-run` | 只展示操作，不实际修改文件 |
| `--help` | 显示帮助 |

### 3.2 子命令总表（26 个）

#### `issue` — Issue 生命周期管理

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai issue new <queue> <标题> [--ref <issue-id>]` | 创建新 Issue，自动分配 ID | 0/1 |
| `mai issue amend <issue-id> <备注>` | 在已归档 Issue 的 `decisions/` 中追加修订记录 | 0/1 |
| `mai issue claim <issue-id>` | 认领 Issue（获取 flock 锁） | 0/1/2 |
| `mai issue complete <issue-id> <结论>` | 完成 Issue（归档结论 + 释放锁） | 0/1 |
| `mai issue list [queue]` | 列出队列中的 Issue | 0 |
| `mai issue show <issue-id>` | 显示 Issue 完整内容 | 0/1 |
| `mai issue escalate <issue-id>` | 将 Issue 升级为冲突（写入 `architect-reviews-designer`） | 0/1 |

#### `queue` — 队列扫描

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai queue check [queue] [--overdue]` | 扫描队列，报告 Issue 数量和超期项 | 0 |
| `mai queue blockers` | 合并输出所有 `designer-blockers` | 0 |

#### `lock` — 原子锁管理

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai lock check <issue-id>` | 检查锁状态（持有者/年龄/是否过期） | 0 |
| `mai lock force-release <issue-id>` | 强制释放过期锁（age > 心跳间隔×1.5） | 0/2 |
| `mai lock guardian` | 全局锁守护：扫描所有锁，释放过期者 | 0 |

#### `log` — 审计日志

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai log history [--date YYYY-MM-DD] [--agent <agent>]` | 查询审计历史 | 0 |
| `mai log write <agent> <type> <摘要> [状态]` | 写入标准化工作记录 | 0 |

#### `daily-summary` — 每日汇总（事件驱动）

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai daily-summary trigger` | Cron 调用：创建每日汇总事件标志（幂等） | 0 |
| `mai daily-summary write <agent> <内容>` | 各 Agent 心跳调用：写入当日摘要 | 0 |
| `mai daily-summary collect` | designer 专用：收集所有摘要，生成最终报告 | 0 |

#### 其他

| 子命令 | 说明 | Exit |
|:---|:---|:---:|
| `mai escalation gen <issue-id>` | 打印冲突升级模板（不写入文件） | 0/1 |
| `mai bitable sync-status` | 查看 Bitable 同步状态 | 0 |
| `mai bitable retry` | 重试失败的同步项 | 0 |
| `mai exec safe-check <cmd>` | 检查命令是否在危险命令黑名单 | 0/2 |
| `mai project init <项目名>` | 初始化新项目（幂等） | 0/4 |

### 3.3 退出码

| 退出码 | 含义 |
|:---:|:---|
| 0 | 成功 |
| 1 | 一般错误（参数错误、文件不存在、Issue 未找到等） |
| 2 | 锁被占用（其他进程持有锁，未超时） |
| 3 | 权限不足 |
| 4 | 项目未初始化（需先运行 `mai project init`） |

---

## 四、核心实现细节

### 4.1 项目根检测优先级

```
1. --project 全局选项
2. AGENTS_PROJECT / MAI_PROJECT 环境变量（值可以是项目名或完整路径）
3. ~/.openclaw/workspace/projects/<name>（根据名称查找）
4. 向上查找 cwd 父目录（寻找与项目名匹配的 AGENTS.md）
5. 若 projects/ 下仅有一个项目，返回该目录
```

### 4.2 Issue ID 格式

格式：`{PREFIX}-{NNN}`，前导零补 3 位（`REQ-001`、`FIX-017`、`BLK-003`）。

| 队列 | ID 前缀 |
|:---|:---|
| programmer-questions | `REQ` |
| architect-decisions | `REQ` |
| techartist-reviews | `REQ` |
| narrative-reports | `REQ` |
| architect-reviews-designer | `REQ` |
| quick-fix-requests | `FIX` |
| designer-blockers | `BLK` |

ID 自增逻辑：扫描 `queues/<queue>/` 下所有 `.md` 文件，用正则 `^{PREFIX}-(\d+)\.md$` 提取编号，取最大值 +1。

### 4.3 flock 原子锁协议

```
acquire_lock(issue_id, agent):
    Step 1: flock(LOCK_EX | LOCK_NB) on .mai/locks/<issue_id>.lock
            → EWOULDBLOCK（锁被占用）→ 检查锁文件 age
               → age > 心跳间隔×1.5 → 强制删除旧锁，重试 Step 1
               → age ≤ 心跳间隔×1.5 → 返回 False（锁仍有效）
            → 加锁成功 → 继续 Step 2
    Step 2: 写入 <agent>|<ISO timestamp> 到锁文件
    Step 3: 创建 .mai/processing/<issue_id>.md（持锁标记）
    Step 4: 同步到 async/processing/
    注意：flock 在进程退出时由 OS 自动释放，无需手动 unlock
```

**锁超时阈值（心跳间隔 × 1.5）：**

| Agent | 心跳间隔 | 锁超时阈值 |
|:---|:---:|:---:|
| programmer | 17 min | 25.5 min |
| designer | 29 min | 43.5 min |
| architect | 43 min | 64.5 min |
| techartist | 47 min | 70.5 min |
| narrative | 61 min | 91.5 min |

### 4.4 每日汇总顺序写入

```
Cron 18:00:
  mai daily-summary trigger
  → 创建 .mai/events/.daily-summary-event（内容: {"next_agent": "programmer"}）

各 Agent 心跳（mai daily-summary write）：
  Step 1: 检查事件标志是否存在 → 不存在则跳过
  Step 2: 检查 .daily-lock 是否被占用（未超时则跳过）
  Step 3: 检查 next_agent == 本 Agent → 不是则跳过
  Step 4: 创建 .daily-lock（flock）
  Step 5: 写入 .mai/history/daily-YYYY-MM-DD/<agent>.md
  Step 6: 更新 next_agent 指向下一个
  Step 7: 删除 .daily-lock

顺序：programmer → narrative → techartist → architect → designer
```

### 4.5 镜像同步策略（`.mai/` → `async/`）

| 源路径（.mai/） | 目标路径（async/） | 说明 |
|:---|:---|:---|
| `queues/<queue>/REQ-001.md` | `async/<queue>/REQ-001.md` | 镜像同步 |
| `processing/REQ-001.md` | `async/<queue>/REQ-001.md` | 解析 Issue ID 找到对应队列 |
| `decisions/REQ-001.md` | `async/decisions/REQ-001.md` | 归档结论镜像 |
| `locks/*.lock` | **不同步** | Agent 不可见 |
| `events/.daily-summary-event` | **不同步** | 内部事件 |
| `history/YYYY-MM-DD.log` | `async/history/YYYY-MM-DD.log` | 审计日志镜像 |

`locks/` 和 `events/` 对 Agent 完全隐藏，不同步到 `async/`。

### 4.6 Issue 文件格式

```markdown
# [REQ-001] <标题>

**发起方：** @<owner>
**处理方：** @<owner>
**创建时间：** <ISO 8601>
**状态：** 🔓 open / 🔄 进行中 / ✅ 完成 / ⚠️ 已修订
**SLA 截止：** <ISO 8601>
**队列：** architect-decisions

**关联 Issue：** [REQ-000](#)
** escalated_blocker_id：** BLK-001

---

## 问题描述
<正文>

## 关联上下文
- 关联 Issue：REQ-000

## 处理记录
- [2026-04-19T14:00:00+08:00] @architect: 创建
```

---

## 五、配置常量

### 5.1 队列 SLA

| 队列 | 处理方 | SLA | 超时后果 |
|:---|:---|:---:|:---|
| `programmer-questions` | designer | 2h | → `designer-blockers` |
| `architect-decisions` | architect | 2h | → `designer-blockers` |
| `techartist-reviews` | designer | 4h | → `designer-blockers` |
| `narrative-reports` | designer | 4h | → `designer-blockers` |
| `architect-reviews-designer` | designer | 2h | → `designer-blockers` |
| `quick-fix-requests` | programmer | 1h | → `designer-blockers` |
| `designer-blockers` | designer | 无 SLA | 直接通知用户 |

### 5.2 Agent 心跳间隔

| Agent | 间隔 | 锁超时阈值 |
|:---|:---:|:---:|
| programmer | 17 min | 25.5 min |
| designer | 29 min | 43.5 min |
| architect | 43 min | 64.5 min |
| techartist | 47 min | 70.5 min |
| narrative | 61 min | 91.5 min |

---

## 六、已知限制与待改进项

### 6.1 已修复 Bug（v1.0）

- ✅ Issue ID 前导零（`REQ-1` → `REQ-001`）
- ✅ `--dry-run` 真正生效（提前 return，不写文件）
- ✅ `exec safe-check` 危险命令 exit 2（而非 exit 0）
- ✅ 镜像同步路径正确分类（locks/events 跳过，queues/decisions/processing 正确路由）

### 6.2 待改进项（计划 v1.1+）

| 项 | 说明 |
|:---|:---|
| **Issue 跨队列迁移** | 当前 Issue 只能在单一队列中，迁移需要手动操作 |
| **Agent 身份识别** | `mai issue claim` 的 agent 来自 `MAI_AGENT`/`AGENT_NAME` 环境变量，需在 Skill 中正确配置 |
| **Bitable 真实同步** | 当前 `bitable sync-status/retry` 仅为存根，需接入 `feishu_bitable_*` 工具实现真实同步 |
| **锁文件残留清理** | 如果进程被 SIGKILL 强制杀死，flock 会释放但 processing 文件可能残留；guardian 进程下次扫描会清理 |
| **竞态条件（claim vs complete）** | 两个进程同时 claim 同一 Issue 时，第二个会在 flock 阶段失败并 exit 2，属于预期行为 |
| **配置外部化** | `QUEUE_SLA`、`HEARTBEAT_INTERVALS` 等常量硬编码在脚本中，修改需直接编辑源码 |

### 6.3 安全注意事项

- `safe_exec.py` 的危险命令黑名单为内存实现（不在 `safe-exec-list.json` 中读取），修改后需同步更新两处
- `mai.py` 本身不受 `safe-exec-list.json` 限制，Agent 通过 exec 调用时遵守白名单约束

---

## 七、测试方法

### 7.1 快速功能验证

```bash
cd ~/.openclaw/workspace/agents/shared-workspace/scripts
export AGENTS_PROJECT=/home/sayo/.openclaw/workspace/projects/Sakamichi
export MAI_PROJECT=/home/sayo/.openclaw/workspace/projects/Sakamichi

# 帮助
python3 mai.py --help

# 初始化项目
python3 mai.py project init Sakamichi

# 创建 Issue
python3 mai.py issue new architect-decisions "渲染管线技术方案评审"

# 查询
python3 mai.py issue list
python3 mai.py issue show REQ-001

# 认领（加锁）
python3 mai.py issue claim REQ-001
python3 mai.py lock check REQ-001   # 查看锁状态

# 完成（归档+解锁）
python3 mai.py issue complete REQ-001 "技术方案可行，同意实现"

# 每日汇总
python3 mai.py daily-summary trigger
python3 mai.py daily-summary write programmer "本日巡检 3 项，无超时"
python3 mai.py daily-summary write narrative "扫描 12 个文件，发现 1 处错误"

# JSON 输出
python3 mai.py issue list --format json
python3 mai.py queue check --format json

# 演练模式
python3 mai.py --dry-run issue new programmer-questions "dry-run test"
```

### 7.2 锁协议验证

```bash
# Terminal 1: 认领 Issue（会成功并持有锁）
python3 mai.py issue claim REQ-001

# Terminal 2: 同一 Terminal 1 持有锁期间再次认领
# 预期：exit 2，LOCK_HELD 错误
python3 mai.py issue claim REQ-001

# 等待锁超时后（25.5 min），再次认领
# 预期：exit 0（锁已自动释放或被 guardian 清理）
```

### 7.3 每日汇总顺序验证

```bash
# 触发汇总
python3 mai.py daily-summary trigger

# 按顺序写入（只有当前 Agent 能成功写）
python3 mai.py daily-summary write programmer "programmer 摘要"
python3 mai.py daily-summary write architect "architect 摘要"  # 会幂等跳过
# narrative 在 programmer 之后才轮到
```

---

## 八、部署

### 8.1 启动方式

**方式 1：直接调用（推荐）**
```bash
python3 ~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py <命令>
```

**方式 2：Shell 别名**
```bash
# 在 ~/.bashrc 或 ~/.zshrc 中添加
alias mai='python3 ~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py'
```

**方式 3：PATH 软链接**
```bash
ln -sf ~/.openclaw/workspace/agents/shared-workspace/scripts/mai.py /usr/local/bin/mai
chmod +x /usr/local/bin/mai
```

### 8.2 Cron 配置（推荐）

```crontab
# 每5分钟：守护进程，释放孤儿锁和超时事件
*/5 * * * * cd ~/.openclaw/workspace/agents/shared-workspace/scripts && python3 mai.py --project Sakamichi lock guardian

# 每日18:00：触发每日汇总事件
0 18 * * * cd ~/.openclaw/workspace/agents/shared-workspace/scripts && python3 mai.py --project Sakamichi daily-summary trigger
```

### 8.3 Agent Skill 配置

在每个 Agent 的 Skill 描述中加入以下环境变量设置（确保 agent 身份识别正确）：

```yaml
# 示例：programmer/SKILL.md
env:
  MAI_AGENT: programmer
  AGENTS_PROJECT: Sakamichi
  MAI_PROJECT: Sakamichi
```

---

*本文档与 `AGENTS_COLLAB_DESIGN_CMD.md` v3.0 同步维护。*
