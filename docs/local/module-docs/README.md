# Multi-Agent 协同工作设计方案：文档导航

> 本目录为 `AGENTS_COLLAB_DESIGN_CMD.md` 的模块化拆分版本。
> 各文档可独立按需读取，减少单文件过载。

---

## 文档索引

| 文档 | 行数 | 内容概要 |
|:---|---:|:---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 38 | 协作架构总览：Agent 角色关系、三条红线、用户接触规则 |
| [CLI.md](./CLI.md) | 192 | 指令系统：`mai` 命令结构、签名、执行约定、设计原则 |
| [WORKSPACE.md](./WORKSPACE.md) | 79 | 工作区结构：目录分工、`.mai` 内部存储、文件存储分层 |
| [EXEC.md](./EXEC.md) | 51 | exec 权限管理：安全命令白名单、审批被拒处理、禁止行为 |
| [QUEUES.md](./QUEUES.md) | 378 | 任务与队列：心跳 SOP、定时任务、队列 SLA、并发控制、快通道 |
| [SKILLS.md](./SKILLS.md) | 197 | Skill 配置矩阵：共享 Skill、各 Agent 专属 Skill、禁止列表 |
| [APPENDIX.md](./APPENDIX.md) | 178 | 附录：Bitable 集成、安全审计、协作标准流程、文件清单 |

---

## 阅读指引

### Agent 视角

| Agent | 必读 | 选读 |
|:---|:---|:---|
| **programmer** | CLI, QUEUES | WORKSPACE, EXEC |
| **architect** | ARCHITECTURE, QUEUES, SKILLS | CLI, EXEC |
| **designer** | ARCHITECTURE, SKILLS, EXEC | QUEUES |
| **narrative** | ARCHITECTURE, QUEUES, SKILLS | CLI, EXEC |
| **techartist** | ARCHITECTURE, QUEUES, SKILLS | CLI, EXEC |
| **Sayo（用户）** | ARCHITECTURE | QUEUES, APPENDIX |

### 开发阶段顺序

1. **理解架构** → `ARCHITECTURE.md`（入口）
2. **掌握命令** → `CLI.md`（指令系统接口）
3. **配置环境** → `WORKSPACE.md`（目录结构）
4. **配置权限** → `EXEC.md`（exec 白名单）
5. **实现队列** → `QUEUES.md`（心跳 + 定时 + 并发）
6. **配置 Skill** → `SKILLS.md`（Skill 矩阵）
7. **查阅附录** → `APPENDIX.md`（协作流程 + 文件清单）

---

## 文档关系图

```
ARCHITECTURE.md          ← 入口文档，定义全局架构
    │
    ├── CLI.md          ← mai 命令系统（其他模块共同依赖）
    │
    ├── WORKSPACE.md     ← .mai/ 内部存储结构（被 QUEUES/SKILLS 引用）
    │
    ├── EXEC.md          ← exec 权限规则（独立模块）
    │
    ├── QUEUES.md        ← 心跳 SOP、定时任务、队列 SLA、并发控制
    │   └── 引用 CLI.md 的 mai 命令
    │   └── 引用 WORKSPACE.md 的 .mai/ 路径
    │
    ├── SKILLS.md        ← Skill 矩阵（包含文件存储规范）
    │   └── 引用 WORKSPACE.md 的目录结构
    │
    └── APPENDIX.md      ← 协作标准流程、文件清单（汇总参考）
```

---

## 重要约束（跨文档通用）

- `.mai/` 目录对 Agent **完全隐藏**，所有读写必须通过 `mai` 命令
- `async/` 为**人类可视化镜像**，Agent 不得直接读取
- `mai` 命令为唯一可信信息来源，禁止使用 `cat/read` 直读协作文件
- 心跳必须执行 5 步标准化流程（详见 `QUEUES.md §5`）
- exec 权限由用户统一管理，安全命令免审批（详见 `EXEC.md`）

---

## 源文档

- 原文：`../AGENTS_COLLAB_DESIGN_CMD.md`（v3.0 Mai）
- 审验报告：`../AnalysisReport.md`
