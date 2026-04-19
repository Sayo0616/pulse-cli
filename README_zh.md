# Pulse CLI 脉

> 多 Agent 协作指令系统 — 标准化团队工作台

```
pulse — 协作元数据命令化 · flock 原子锁 · 事件驱动汇总 · JSON 配置外部化
```

---

## 一句话介绍

Pulse 是一个基于命令行的多 Agent 协作框架。通过标准化 CLI 将 Issue 队列、原子锁、审计日志、每日汇总全部封装为可验证、可脚本化的命令，让多个 Agent 在无需人工干预的情况下自主协作。

---

## 核心特性

- **🔒 flock 原子锁** — POSIX `fcntl.flock()` 实现，进程崩溃自动释放，无孤儿锁
- **📋 26 个标准化命令** — 覆盖 Issue 生命周期、队列扫描、锁管理、审计日志、每日汇总
- **📁 双层存储结构** — `.pulse/` 作为内部真实数据源，`async/` 作为人类可视化镜像
- **⚙️ JSON 配置外部化** — 队列 SLA、Agent 心跳频率、Issue ID 前缀全部在 `config.json`，改规则不碰代码
- **🔄 事件驱动每日汇总** — Cron 触发事件，各 Agent 在心跳中顺序写入，无需同步调度
- **✅ 幂等优先** — 所有写操作重复执行不破坏状态
- **📦 零外部依赖** — 仅 Python 3 标准库，部署简单

---

## 安装

```bash
pip install pulse-cli
```

或源码安装：

```bash
pip install .
```

安装后全局可用 `pulse` 命令。

---

## 快速开始

### 1. 初始化项目

```bash
pulse project init my-team
# ✅ Project 'my-team' initialized.
```

### 2. 创建 Issue

```bash
pulse issue new architect-decisions "渲染管线技术方案评审"
# ✅ Issue REQ-001 created in queue 'architect-decisions'
```

### 3. 认领 Issue（自动加锁）

```bash
pulse issue claim REQ-001
# 🔒 Issue REQ-001 claimed.
```

### 4. 完成 Issue（归档 + 解锁）

```bash
pulse issue complete REQ-001 "技术方案可行，同意实现"
# ✅ Issue REQ-001 completed.
```

### 5. 查看队列状态

```bash
pulse queue check
pulse queue check --overdue    # 只看超期的
pulse queue blockers           # 合并输出所有 blocker
```

---

## 架构亮点

### 为什么用 flock 而不是文件锁？

传统方案用"文件存在即锁定"，但进程崩溃时锁文件无法清理。`flock(LOCK_EX | LOCK_NB)` 由操作系统管理，进程退出时自动释放，双保险。

### 为什么用命令而不是直接文件读写？

Agent 直接读写队列文件容易出现竞态条件和状态不一致。命令系统将所有协作元数据封装为 API，输出确定性得到指数级提升。

### 为什么有 async/ 镜像层？

`.pulse/` 对 Agent 隐藏，`async/` 是给人类观察的可视化镜像。Agent 获取任何协作状态必须通过 `pulse` 命令，不得直接读写文件。

---

## 命令参考

### 全局选项

```
pulse [--project <项目名>] [--format json|text] [--dry-run] <子命令>
```

| 选项 | 说明 |
|:---|:---|
| `--project` | 指定项目 |
| `--format json` | JSON 结构化输出 |
| `--dry-run` | 只展示，不实际修改文件 |

### issue — Issue 生命周期

| 命令 | 说明 |
|:---|:---|
| `pulse issue new <queue> <标题>` | 创建 Issue，自动分配 ID |
| `pulse issue amend <issue-id> <备注>` | 追加修订记录 |
| `pulse issue claim <issue-id>` | 认领（获取锁） |
| `pulse issue complete <issue-id> <结论>` | 完成（归档 + 解锁） |
| `pulse issue list [queue]` | 列出 Issue |
| `pulse issue show <issue-id>` | 显示详情 |
| `pulse issue escalate <issue-id>` | 升级为冲突 |

### queue — 队列扫描

| 命令 | 说明 |
|:---|:---|
| `pulse queue check [--overdue]` | 扫描队列 |
| `pulse queue blockers` | 合并输出所有 blocker |

### lock — 锁管理

| 命令 | 说明 |
|:---|:---|
| `pulse lock check <issue-id>` | 检查锁状态 |
| `pulse lock force-release <issue-id>` | 强制释放过期锁 |
| `pulse lock guardian` | 全局锁守护 |

### log — 审计日志

| 命令 | 说明 |
|:---|:---|
| `pulse log write <agent> <type> <摘要>` | 写入工作记录 |
| `pulse log history [--date YYYY-MM-DD]` | 查询历史 |

### daily-summary — 每日汇总

| 命令 | 说明 |
|:---|:---|
| `pulse daily-summary trigger` | Cron 调用：触发每日汇总事件 |
| `pulse daily-summary write <agent> <内容>` | 各 Agent 顺序写入摘要 |
| `pulse daily-summary collect` | designer 生成最终报告 |

### 其他

| 命令 | 说明 |
|:---|:---|
| `pulse escalation gen <issue-id>` | 生成冲突升级模板 |
| `pulse bitable sync-status` | 查看 Bitable 同步状态 |
| `pulse exec safe-check <cmd>` | 检查命令是否危险 |
| `pulse project init <name>` | 初始化项目 |

---

## 配置文件示例

所有协作规则在 `.pulse/config.json` 中：

```json
{
  "name": "my-team",
  "queues": {
    "architect-decisions": {
      "handler": "architect",
      "sla_minutes": 120,
      "id_prefix": "REQ"
    },
    "quick-fix-requests": {
      "handler": "programmer",
      "sla_minutes": 60,
      "id_prefix": "FIX"
    }
  },
  "agents": {
    "programmer": { "heartbeat_minutes": 17 },
    "architect":  { "heartbeat_minutes": 43 }
  },
  "daily_summary_order": ["programmer", "narrative", "techartist", "architect", "designer"],
  "issue_status_emoji": {
    "open": "🔓",
    "claimed": "🔄",
    "complete": "✅"
  }
}
```

---

## 退出码

| 退出码 | 含义 |
|:---:|:---|
| 0 | 成功 |
| 1 | 一般错误（参数错误、Issue 未找到等） |
| 2 | 锁被占用（其他进程持有锁，未超时） |
| 3 | 权限不足 |
| 4 | 项目未初始化 |

---

## 支持环境

- Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12
- Linux / macOS / WSL（Windows Subsystem for Linux）
- 仅使用 Python 3 标准库，无外部依赖

---

## 目录结构

```
pulse-cli/
├── src/pulse/           # 源代码
│   ├── pulse.py         # 主入口 + dispatch
│   ├── config.py        # 配置加载
│   ├── issue.py         # Issue 命令
│   ├── queue.py         # 队列命令
│   ├── lock.py          # 锁命令
│   ├── log.py           # 日志命令
│   ├── daily_summary.py  # 每日汇总
│   └── ...
├── tests/              # 测试
├── docs/              # 文档
├── pyproject.toml     # 项目配置
└── README.md          # 英文版
```

---

## 相关文档

| 文档 | 说明 |
|:---|:---|
| [USER_GUIDE.md](./docs/USER_GUIDE.md) | 人类用户完整指南 |
| [DEVELOPMENT.md](./docs/DEVELOPMENT.md) | 开发文档（实现细节） |

---

## License

MIT License — 详见 [LICENSE](./LICENSE)

---

*Pulse CLI v1.1 — 配置外部化版本*
