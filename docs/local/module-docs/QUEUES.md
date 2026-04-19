> 本文档归属：QUEUES.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §五+§六+§七

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
