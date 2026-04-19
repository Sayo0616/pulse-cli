> 本文档归属：WORKSPACE.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §三

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
