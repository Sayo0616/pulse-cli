> 本文档归属：SKILLS.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §八+§九

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
