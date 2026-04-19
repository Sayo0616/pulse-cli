# Multi-Agent 协同工作设计方案

> 本文档定义 designer / architect / programmer / narrative / techartist 五个 Agent 的心跳任务、定时任务、Skill 配置及文件存储规范。
> 版本：v1.3（2026-04-19）｜基于 v1.2 + P2 阶段优化

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
- 所有 Agent 必须进行**工作记录**，写入 `projects/<项目名>/` 对应文件，作为团队透明度的唯一来源
- **exec 权限统一由用户管理**，审批被拒时通过飞书 channel 申请
- **安全命令免审批**（见 §四·P0-3 safe-exec-list.json）

---

## 二、工作区结构

### 目录分工

| 路径 | 用途 | 性质 |
|:---|:---|:---|
| `<workspace>/memory/` | Agent 记忆、长期知识、过往日志 | 个人/系统记忆，不可作为工作交付 |
| `~/.openclaw/workspace/agents/shared-workspace/` | 跨 Agent 共享的非特定项目文件 | 团队日常交流入口，不包含项目内容 |
| `~/.openclaw/workspace/projects/` | 跨 Agent 共享的工作文件、队列、日志 | 团队项目协作入口，source of truth |
| 真实项目地址（见 §八·P1-5 `project.config.json`） | 实际开发产物（代码、资源、配置） | 版本控制，本地存储 |

**严格约束：`memory/` 不得作为任何 Agent 的工作交付目录。**

### 团队文件柜（`~/.openclaw/workspace/agents/shared-workspace/`）

跨 Agent、非特定项目的共享文件：

```
~/.openclaw/workspace/agents/shared-workspace/
├── agents-group-protocol/          # 群聊协作规范
├── skills/                        # 跨 Agent 共享 Skill（除项目特定 Skill 外）
├── exec-auth-log.md               # exec 授权记录（各 Agent 申请授权的流水）
├── safe-exec-list.json            # 安全命令白名单（免审批）
└── agent-info/                    # 各 Agent 元信息（能力描述、联系方式）
```

### 项目工作区（`~/.openclaw/workspace/projects/<项目名>/`）

各项目独立的协作工作区：

```
~/.openclaw/workspace/projects/<项目名>/
├── async/                         # 异步队列（目录化，详见 §七·P0-1）
│   ├── programmer-questions/      # 单 Issue 一文件
│   │   └── REQ-<编号>.md
│   ├── architect-decisions/       # 同上
│   ├── techartist-reviews/       # 同上
│   ├── narrative-reports/         # 同上
│   ├── architect-reviews-designer/ # architect 事后否决通道（新增）
│   ├── designer-blockers/         # 同上
│   ├── quick-fix-requests/       # 客观错误快通道（新增）
│   ├── processing/               # 处理中的 Issue（原子锁机制）
│   └── history/
│       └── YYYY-MM-DD.log         # append-only 审计日志
├── decisions/                     # 终裁决策记录（终稿）
├── reports/                       # 各 Agent 产出的报告
│   └── daily-YYYY-MM-DD-summary.md
├── bitable-sync/                  # bitable API 同步状态（含容错，见 §十·P1-2）
│   └── sync-state.json
├── locks/                         # 锁文件（含超时，见 §七·P1-3）
│   └── .daily-lock                # 每日汇总顺序锁
└── templates/                     # 标准化模板
    └── escalation-template.md     # 冲突升级模板（见 §七·P2-1）
```

---

## 三、工作记录规范

每条工作记录必须包含以下字段，格式统一为 Markdown：

```markdown
## [YYYY-MM-DD HH:mm] <Agent> - <任务类型>

**摘要：** ...
**状态：** ✅ 完成 / ⚠️ 阻塞 / 🔄 进行中 / ⏱️ 超时
**关联方：** @architect / @designer（若涉及跨 Agent 依赖）
**下一步：** ...
**[REPORT_TO_USER]**（仅终裁决策结论携带此标记）
```

**记录写入规则：**
- Issue 单文件格式：见 §七·P0-1 队列生命周期协议
- exec 审批被拒 → **立即**通过飞书 channel 向用户申请，说明理由

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

**执行逻辑：**
1. Agent 发起的 exec 先匹配 `safe_commands` 正则
2. 命中且 `risk: "none"` → 直接放行，不弹审批
3. 未命中 → 进入标准审批流程
4. 白名单由用户（Sayo）手动维护，Agent 只读

### 审批被拒时的处理流程

当 Agent 因审批不通过而无法继续工作时：

```
1. 分析评估其他方式
2. 无法通过其他方式完成任务，或者不推荐通过其他方式实现时，主动暂停执行
3. 通过飞书 IM（私聊或群聊 channel）向用户发送权限申请
4. 申请内容必须包含：
   - 执行的具体命令或操作
   - 当前上下文和目的
   - 之前的重试次数（若有）
5. 等待用户授权，不得绕过
6. 用户授权后，Agent 将授权结论追加写入
   ~/.openclaw/workspace/agents/shared-workspace/exec-auth-log.md
```

**飞书申请消息模板：**

```
🤖 [Agent] exec 权限申请

操作：<具体命令>
目的：<要解决的问题>
上下文：<当前进度>
请回复 /approve <id> 或说明拒绝理由。
```

### 禁止行为

- ❌ 不得在审批被拒后切换命令写法重新尝试
- ❌ 不得将 exec 任务拆解为多个"看起来无害"的子命令绕过审批
- ❌ 不得在未经用户授权的情况下变更操作方向
- ❌ 不得修改 `safe-exec-list.json`（该文件由用户专属维护）

---

## 五、心跳任务设计

### P2-2 心跳间隔重新设计

各 Agent 心跳**错开时间**，避免同一时刻竞争共享文件。使用质数间隔，避免最小公倍数陷阱（20/30/45/60 的 LCM = 180 分钟会完全重合）：

| Agent | 心跳频率 | 核心巡逻内容 |
|:---|:---|:---|
| **programmer** | 每 17 分钟 | 检查 architect 批准方案；执行 diff 自审；检测逻辑漏洞 |
| **designer** | 每 29 分钟 | 处理 programmer 上报 Issue；检查 quick-fix 确认；检查 narrative 文本报告 |
| **architect** | 每 43 分钟 | 处理 designer 通过的新需求；处理 programmer 技术问题上报；处理 architect-reviews-designer 队列 |
| **techartist** | 每 47 分钟 | 检查渲染代码提交；运行性能基准；处理 quick-fix 反馈 |
| **narrative** | 每 61 分钟 | 扫描 strings.json 与剧本一致性；处理 quick-fix 反馈 |

**心跳写入目标：**
- 异步队列 → `~/.openclaw/workspace/projects/<项目名>/async/<queue>/`
- 审计历史 → `~/.openclaw/workspace/projects/<项目名>/async/history/YYYY-MM-DD.log`

---

## 六、定时任务（Cron）

| 调度频率 | 任务 | 执行者 | 输出路径 |
|:---|:---|:---|:---|
| 每 1 小时 | 体验抽查 | designer | `projects/<项目名>/reports/` |
| 每 2 小时 | 技术方案整理 | architect | `projects/<项目名>/decisions/` |
| 每 4 小时 | 代码逻辑巡检 | programmer | `projects/<项目名>/async/` |
| 每 6 小时 | strings.json 一致性扫描 | narrative | `projects/<项目名>/reports/` |
| 每日 14:00 | 性能报告 | techartist | `projects/<项目名>/reports/performance-YYYY-MM-DD.md` |
| 每日 18:00 | 协同状态汇总 | 全员顺序写入 | `projects/<项目名>/reports/daily-YYYY-MM-DD-summary.md` |

### 每日汇总顺序（原子锁整合）

通过 `locks/.daily-lock` 控制，按序写入。**与其他 Issue 锁文件遵循同一原子锁协议：**

```
programmer → narrative → techartist → architect → designer（最终摘要）
```

**流程：**
1. programmer 心跳时持有 `locks/.daily-lock`（超时阈值：17min × 1.5 = 25min）
2. 写入完成后删除锁
3. narrative 检测到锁不存在，开始自己的写入（同样持有锁 → 删除）
4. 以此类推
5. 若任一 Agent 持有锁超时，下一轮心跳强制释放

---

## 七、异步队列与并发控制（核心重构）

### P0-1 队列目录化 + 原子锁协议

#### 文件 → 目录升级

`async/` 下每个队列从单一 `.md` 文件改为独立目录，**每个 Issue 一文件**：

```
async/
├── programmer-questions/     # 原单一文件 → 目录
│   ├── REQ-001.md
│   ├── REQ-002.md
├── architect-decisions/
│   ├── REQ-010.md
├── quick-fix-requests/       # 客观错误快通道（新增）
│   └── FIX-001.md
└── ...
```

**Issue 文件格式（统一）：**

```markdown
# [REQ-001] <标题>

**发起方：** @programmer
**处理方：** @designer
**创建时间：** 2026-04-19T13:45:00+08:00
**状态：** 🔄 进行中 / ✅ 完成 / ⚠️ 阻塞 / ⏱️ 超时
**SLA 截止：** 2026-04-19T15:45:00+08:00（2h 后）

---

## 问题描述
...

## 关联上下文
...

## 处理记录
- [2026-04-19 13:45] @programmer: 创建
- [2026-04-19 13:50] @designer: 认领 → 移动至 processing/
```

#### 队列生命周期（4 步）

```
1. 创建：发起方 → 写入 async/<queue>/REQ-XXX.md，状态=🔄进行中
2. 认领：处理方读取后 → 创建 processing/REQ-XXX.md（原子锁），原文件删除或标记为已认领
3. 处理：处理方在 processing/ 目录下写入结论
4. 完成：结论归档至 decisions/ → processing/ 下的文件彻底删除
```

#### 原子锁协议

**所有对 async/ 下文件的写操作必须遵循以下锁协议：**

```
# Step 1: 检查是否存在同名锁文件
if exists locks/REQ-XXX.lock:
   放弃本次心跳操作（锁被占用）
else:
    # Step 2: 创建锁文件（包含时间戳）
    echo "<agent>|<timestamp>" > locks/REQ-XXX.lock
    # Step 3: 执行读写操作
    ...
    # Step 4: 操作完成后删除锁
    rm locks/REQ-XXX.lock
```

**P1-3 锁文件超时：** 锁文件 age 超过心跳间隔 × 1.5 倍 → 下一次心跳强制删除并重试。

---

### P0-2 architect 事后否决降级路径

designer 通过方案后，若 architect 事后发现技术不可行：

```
designer 通过 → architect 审查通过 → 实现中
                            ↓
              architect 发现技术问题（事后）
                            ↓
              写入 async/architect-reviews-designer/REQ-XXX.md
              状态=⚠️降级申请，标记"TECH_BLOCKER"
                            ↓
              designer 心跳检测到 → 重审体验决策
                            ↓
              若 designer 坚持 → [REPORT_TO_USER] 通知用户裁决
              若 designer 接受 → architect 撤销原批准，programmer 停实现
```

**设计原则：** architect 事后否决不直接覆盖已通过决策，而是通过降级队列触发 designer 重审，保留双向追溯能力。

**清理规则（CRITICAL-4 修复）：**
- designer 认领时：创建 `processing/REQ-XXX.md`（持锁），**同时由 architect 删除** `architect-reviews-designer/REQ-XXX.md`（或标记为已认领并由 architect 删除）
- 流程完成后：结论归档至 `decisions/REQ-XXX.md`，`processing/` 下的文件彻底删除
- 不得留下「已认领但未归档」的残留文件，否则 SLA 监控会重复触发

---

### P1-1 超时通知合并机制

超时后**不立即通知用户**，先汇聚到 `designer-blockers/`，由 designer 心跳**合并为一条飞书消息**后发送。

#### P1-1 队列 SLA 定义

| 队列 | 处理方 | SLA | 超时判定 |
|:---|:---|:---|:---|
| `async/programmer-questions/` | designer | 2h | 超过 SLA 截止时间即触发 |
| `async/architect-decisions/` | architect | 2h | 超过 SLA 截止时间即触发 |
| `async/techartist-reviews/` | designer | 4h | 超过 SLA 截止时间即触发 |
| `async/narrative-reports/` | designer | 4h | 超过 SLA 截止时间即触发 |
| `async/quick-fix-requests/` | programmer | 1h | 超过 SLA 截止时间即触发 |

#### P1-1 超时处理流程

**（CRITICAL-1 修复）超时检测方 = 超时写入方：**

```
# 每次心跳检测到超时（由该队列的处理方或其发起方检测）
→ 由检测方写入 async/designer-blockers/BLK-<编号>.md
   内容：超时的 Issue 链接 + 原始 SLA + 超时时长
→ 继续正常流程，不单独发飞书通知
```

**写入权限说明：**
- `architect-decisions/` 超时 → **architect** 写入 designer-blockers/
- `programmer-questions/` 超时 → **designer** 写入 designer-blockers/
- `quick-fix-requests/` 超时 → **designer** 写入 designer-blockers/
- `techartist-reviews/` / `narrative-reports/` 超时 → **designer** 写入 designer-blockers/

#### P1-1 designer 心跳汇总（合并发送）

```
designer 心跳 → 扫描 designer-blockers/
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

**去重规则：** 同一个 Issue 只在**首次超时**时报 BLK；持续超时期间不重复报告；Issue 处理完成后删除对应 BLK。

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

**快通道例外（不适用）：** 若客观错误由 designer 主动决策引起（如明确要求某特效无视性能），则视为 designer 已知的 trade-off，不触发快通道，记录至报告走标准链。

#### P1-4 快通道流程

```
narrative/techartist 发现问题
  → 判定：是否为例外（designer 已知 trade-off）？
      → 是：记录至报告，走标准链
      → 否：继续快通道

  → 写入 async/quick-fix-requests/FIX-XXX.md
  → 同时通知 programmer（执行修复）和 designer（知晓，不审批）
  → programmer 修复完成 → 写入结论至 FIX-XXX.md → 归档至 decisions/FIX-XXX.md
  → 删除 async/quick-fix-requests/FIX-XXX.md 和 processing/ 下的相关文件
  → 若 1 小时无响应 → 升级至 designer-blockers/
```

**结论归档（CRITICAL-2 修复）：** programmer 完成修复后，必须先将结论归档至 `decisions/FIX-XXX.md`，再删除 `quick-fix-requests/` 中的原文件。结论文件不得丢失，必须在 `decisions/` 中保留审计轨迹。

#### P1-4 禁止行为

- ❌ 快通道不得用于主观争议（体验/风格/氛围）
- ❌ narrative/techartist 不得以快通道为名绕过 designer 做体验决策
- ❌ programmer 不得以「快通道修复」为由自行变更实现方案

---

### P2-1 冲突升级标准化模板

讨论 3 轮无果后的上报格式，存入 `projects/<项目名>/templates/escalation-template.md`：

```markdown
## ⚠️ [冲突升级] <类型>

- **发起方：** @<Agent>
- **冲突对象：** @<Agent>
- **核心分歧：** <一句话描述>
- **立场 A：** <Agent A 的主张 + 依据>
- **立场 B：** <Agent B 的主张 + 依据>
- **客观数据（如有）：** <可量化的事实>
- **建议选项：**
  - [A] <选项描述>
  - [B] <选项描述>
- **请用户 (Sayo) 裁决：** [A] / [B]
```

**使用规则：** 冲突升级 Issue 必须使用此模板，Agent 不得自行发挥格式。

---

## 八、文件存储规范

### P1-5 真实项目地址配置化

在 `projects/<项目名>/` 下放置 `project.config.json`，消除跨 Agent 理解歧义：

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

**约束（所有 Agent 的 Skill 配置中必须写入）：**
> 除非 exec 权限经用户审批通过，否则不得向 `source_root` 写入任何文件。

### 存储分层

| 存储位置 | 内容 | 性质 |
|:---|:---|:---|
| **飞书云文档** | 周报、决策记录、知识库、架构文档、设计规范 | 团队知识沉淀，面向人类可读 |
| **`project.config.json` 定义的真实项目地址** | 源代码、游戏资源、strings.json、配置文件 | 实际开发材料，版本控制，本地存储 |
| **`projects/`** | 团队协作产生的所有工作文件（队列、报告、日志、锁） | 项目协作 source of truth |

### 强制约束

```
❌ 禁止将源代码、strings.json、游戏资源等开发产物上传到飞书
❌ 禁止将报告/文档等知识资料当作代码交付物使用
❌ 禁止将工作文件写入 memory/（memory 仅用于 Agent 记忆）
❌ 禁止将项目协作文件写入 agents/shared-workspace/（该目录不含项目内容）
```

---

## 九、Skill 配置矩阵

### 9.1 共享 Skill（所有 Agent 必须加载）

- `agents-group-protocol` — 群聊协作规范（位于 `~/.openclaw/workspace/agents/shared-workspace/agents-group-protocol/`）

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
    - architecture-designing # 技术方案否决权归 architect

# architect/SKILL.md
skills:
  deny:
    - user-document-writing  # 体验文档归 designer
    - software-dev-autopilot  # 实现推进归 programmer

# narrative/SKILL.md
skills:
  deny:
    - requirement-analysis   # 体验判断权归 designer

# techartist/SKILL.md
skills:
  deny:
    - architecture-designing # 技术方案归 architect
```

### 9.4 快通道触发条件（强制写入 Skill 说明）

以下条件必须写入对应 Agent 的 Skill 配置中，心跳检测到时**自动触发快通道**（§七·P1-4），不经 designer 审批直接通知 programmer：

| Agent | 快通道触发条件 | 阈值 |
|:---|:---|:---|
| **narrative** | strings.json 键值对不匹配 | 任意发现即触发 |
| | strings.json 缺失必含键 | 任意发现即触发 |
| | strings.json JSON 语法错误 | 任意发现即触发 |
| | 剧本关键场景文件缺失 | 任意发现即触发 |
| **techartist** | 帧率低于阈值 | < 30 FPS |
| | DrawCall 超标 | > 5000 |
| | 显存超预算 | 超出 10% 以上 |
| | 资产路径断裂 | 任意发现即触发 |

---

## 十、Bitable 待办管理

通过飞书多维表格组织维护所有 Agent 待处理项，**自动同步而非人工维护**：

```
Agent 心跳 → 写入 projects/<项目名>/async/<queue>/
         → 通过 feishu_bitable_app_table_record API 同步到 bitable
```

### P1-2 bitable 同步容错

在 `bitable-sync/` 下维护 `sync-state.json`：

```json
{
  "last_sync": "2026-04-19T13:45:00+08:00",
  "status": "ok",
  "failed_items": [],
  "retry_count": 0,
  "max_retries": 3
}
```

**容错逻辑：**
- API 调用失败 → `status: failed`，记录 `failed_items`，重试 +1
- 重试 3 次仍失败 → `status: stuck`，**停止重试**，在 `designer-blockers/` 写入告警 Issue，用户飞书通知
- `status: ok` 后清除 `failed_items` 和 `retry_count`

**数据一致性原则：** projects/ async/ 目录是 source of truth；bitable 是可视化层面副本；二者不一致时以 projects/ 为准。

---

## 十一、安全与审计

### 最小权限访问控制（目录化后）

| 目录 | 允许写入 | 允许读取 |
|:---|:---|:---|
| `async/programmer-questions/` | programmer | designer, architect |
| `async/architect-decisions/` | architect | programmer, designer |
| `async/architect-reviews-designer/` | architect, designer | designer |
| `async/designer-blockers/` | designer, architect, programmer | architect, user |
| `async/techartist-reviews/` | techartist | designer |
| `async/quick-fix-requests/` | narrative, techartist, programmer | programmer, designer |
| `async/processing/` | 处理方（持锁者） | 处理方 |
| `async/history/` | 无（append-only） | 所有人 |

### 锁文件访问

| 文件 | 允许操作 |
|:---|:---|
| `locks/*.lock` | 创建（持锁方）、删除（持锁方或超时强制） |
| 读锁文件判断锁状态 | 所有 Agent |

### 审计日志

每次写入 `async/` 时，追加到 `async/history/YYYY-MM-DD.log`（append-only，不可覆盖或修改）：

```
[2026-04-19 11:35] programmer@heartbeat → async/programmer-questions/REQ-001.md [创建]
[2026-04-19 11:36] designer@heartbeat → async/processing/REQ-001.md [持锁认领]
[2026-04-19 11:38] designer@heartbeat → async/architect-reviews-designer/REQ-002.md [降级申请]
```

### 决策回滚

designer 主动撤销否决 → 写入 `[REPORT_TO_USER]` 说明原因 → architect 确认技术可行性未变 → programmer 恢复实现。

architect 事后否决（降级路径）见 §七·P0-2。

---

## 十二、关键设计原则

1. **单向否决链** — designer ✗ → architect ✗ → programmer ✗（停止实现）
2. **双向否决降级** — architect 事后否决 → architect-reviews-designer 队列 → designer 重审，不直接覆盖
3. **工作记录替代直接汇报** — 所有 Agent 写工作记录，用户只接收终裁结论（`[REPORT_TO_USER]`）
4. **exec 权限归用户所有** — 审批被拒 → 飞书申请 → 用户授权 → 继续
5. **安全命令免审批** — `safe-exec-list.json` 白名单匹配通过则不弹审批
6. **四目录严格分工** — `memory/` 记忆、`agents/shared-workspace/` 非项目团队文件、`projects/` 项目协作文件、`project.config.json` 定义的真实项目地址
7. **队列目录化 + 原子锁** — async/ 从单文件改为 Issue-per-file + `locks/` 锁协议，解决并发覆盖和 Token 膨胀
8. **锁文件超时自动释放** — 锁 age 超心跳间隔×1.5 倍后自动强制解除，防止 orphan 锁死锁
9. **每日汇总原子锁整合** — `.daily-lock` 与 Issue 锁共用同一协议，防止多 Agent 并发写覆盖
10. **programmer 逻辑漏洞上报是唯一合法反向触发**
11. **narrative 和 techartist 是评审角色，非终裁** — 发现问题上报终裁，不得直接否决；**客观错误除外（快通道）**
12. **心跳质数间隔** — 避免 LCM 重合导致的并发锁竞争
13. **每日汇总由 designer 写入最终摘要** — designer 是体验最终负责人
14. **文件分层存储** — 飞书存报告/知识，真实项目地址存开发产物，`projects/` 是协作 source of truth
15. **bitable 自动同步 + 容错** — 机器驱动同步，失败重试 3 次后告警，以 projects/ 为 source of truth
16. **超时通知合并** — 超时先汇入 blocker 队列，由 designer 心跳合并发送，避免通知轰炸
17. **真实项目只读保护** — `project.config.json` 定义 `source_root`，exec 未审批时 Agent 不得向其写入
18. **快通道客观错误阈值强制写入 Skill** — §九·9.4 触发条件不可由 Agent 自行裁量
