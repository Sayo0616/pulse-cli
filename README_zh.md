# Mai CLI —— 脉

[English](./README.md) | **简体中文**

> 多 Agent 协作指令系统 — 标准化团队工作台

```
mai — 协作元数据命令化 · flock 原子锁 · 并发安全写入 · JSON 配置外部化
```

---

## 一句话介绍

脉 是一个基于命令行的多 Agent 协作框架。通过标准化 CLI 将 Issue 队列、原子锁、审计日志、每日汇总全部封装为可验证、可脚本化的命令，让多个 Agent 在无需人工干预的情况下自主协作。

---

## 核心特性

- **🔒 flock 原子锁** — POSIX `fcntl.flock()` 实现，并发写入安全，进程崩溃自动释放
- **📋 标准化命令** — 覆盖 Issue 生命周期、队列扫描、锁管理、审计日志、每日汇总
- **📁 双层存储结构** — `.mai/` 作为内部真实数据源，`async/` 作为人类可视化镜像
- **⚙️ JSON 配置外部化** — 队列 SLA、Agent 心跳频率、Issue ID 前缀全部在 `config.json`
- **🔄 并发安全每日汇总** — 引入 `fcntl` 保护，支持多 Agent 同时写入日报，自动闭环周期
- **✅ 幂等优先** — 所有写操作重复执行不破坏状态
- **📦 零外部依赖** — 仅 Python 3 标准库，部署简单

---

## 安装

```bash
pip install mai-cli
```

或源码安装：

```bash
pip install -e .
```

安装后全局可用 `mai` 命令。

---

## 快速开始

### 1. 初始化项目

```bash
mai init my-team
# ✅ Project 'my-team' initialized.
```

### 2. 创建 Issue

```bash
mai issue new architect-decisions "渲染管线技术方案评审"
# ✅ Issue REQ-001 created in queue 'architect-decisions'
```

### 3. 认领 Issue（自动加锁）

```bash
mai issue claim REQ-001
# 🔒 Issue REQ-001 claimed.
```

### 4. 完成 Issue（归档 + 解锁）

```bash
mai issue complete REQ-001 "技术方案可行，同意实现"
# ✅ Issue REQ-001 completed.
```

### 5. 查看队列状态

```bash
mai queue check
mai queue check --overdue    # 只看超期的
mai queue blockers           # 合并输出所有 blocker
```

---

## 架构亮点

### 为什么用 flock 而不是文件锁？

传统方案用"文件存在即锁定"，但进程崩溃时锁文件无法清理。`flock(LOCK_EX | LOCK_NB)` 由操作系统管理，进程退出时自动释放，双保险。

### 为什么用命令而不是直接文件读写？

Agent 直接读写队列文件容易出现竞态条件和状态不一致。命令系统将所有协作元数据封装为 API，输出确定性得到指数级提升。

### 为什么有 async/ 镜像层？

`.mai/` 对 Agent 隐藏，`async/` 是给人类观察的可视化镜像。Agent 获取任何协作状态必须通过 `mai` 命令，不得直接读写文件。

---

## 命令参考

### 全局选项

```
mai [-v|--version] [--project <项目名>] [--format json|text] [--dry-run] <子命令>
```

| 选项 | 说明 |
|:---|:---|
| `-v, --version` | 显示程序版本号 |
| `--project` | 指定项目根目录（默认当前目录或环境变量） |
| `--format json` | JSON 结构化输出 |
| `--dry-run` | 只展示，不实际执行修改 |

### issue — Issue 生命周期

| 命令 | 说明 |
|:---|:---|
| `mai issue new <queue> <标题>` | 创建 Issue，自动分配 ID |
| `mai issue amend <issue-id> <备注>` | 追加修订记录 |
| `mai issue claim <issue-id>` | 认领（获取锁） |
| `mai issue complete <issue-id> <结论>` | 完成（归档 + 解锁） |
| `mai issue list [queue]` | 列出 Issue |
| `mai issue show <issue-id>` | 显示详情 |
| `mai issue escalate <issue-id>` | 升级为冲突 |

### queue — 队列扫描

| 命令 | 说明 |
|:---|:---|
| `mai queue check [--overdue]` | 扫描队列 |
| `mai queue blockers` | 合并输出所有 blocker |

### lock — 锁管理

| 命令 | 说明 |
|:---|:---|
| `mai lock check <issue-id>` | 检查锁状态 |
| `mai lock force-release <issue-id>` | 强制释放过期锁 |
| `mai lock guardian` | 全局锁守护 |

### log — 审计日志

| 命令 | 说明 |
|:---|:---|
| `mai log write <agent> <type> <摘要>` | 写入工作记录 |
| `mai log history [--date YYYY-MM-DD]` | 查询历史 |

### daily-summary — 每日汇总

| 命令 | 说明 |
|:---|:---|
| `mai daily-summary trigger` | 触发每日汇报事件 |
| `mai daily-summary write <agent> <内容>` | 写入日报（并发锁保护，最后一个 Agent 提交后自动结束） |
| `mai daily-summary read [<agent>|.|--all]` | 读取日报、查看进度或生成汇总报告 |

### 其他

| 命令 | 说明 |
|:---|:---|
| `mai escalation gen <issue-id>` | 生成冲突升级模板 |
| `mai exec safe-check <cmd>` | 检查命令是否危险 |
| `mai init [name]` | 初始化项目（默认当前目录） |
| `mai project init <name>` | 在默认路径初始化项目 |


---

## 配置文件示例

所有协作规则在 `.mai/config.json` 中：

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
mai-cli/
├── src/mai/           # 源代码
│   ├── mai.py         # 主入口 + dispatch
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

*Mai CLI v1.3 — 并发安全与体验优化版*
