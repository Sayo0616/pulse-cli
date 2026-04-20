---
name: mai-cli
description: 多 Agent 协作命令行工具。当 Agent 需要创建（new）issue、认领（claim）issue、完成（complete）issue、补充说明（amend）、查看队列状态（queue check）、触发每日摘要（daily-summary trigger/write/read）、强制释放锁（lock force-release）、或升级 issue（issue escalate）时使用。触发短语：创建 issue、认领 issue、完成 issue、查看队列、触发摘要、强制释放锁、escalate。
---

# mai-cli — 多 Agent 协作命令行工具

mai-cli 通过 flock 原子锁和队列路由协调多 Agent 工作流。

## 通用命令格式

所有命令需附加 `--project <共享工作区路径>`。

## Issue 生命周期

```
# 1. 新建 issue（指定队列）
mai --project <path> issue new <queue> <title> [--ref <ref-id>]

# 2. 认领 issue（加 flock 锁）
mai --project <path> issue claim <issue-id>

# 3. 完成 issue（释放锁 + 记录结论）
mai --project <path> issue complete <issue-id> <conclusion>

# 4. 补充说明
mai --project <path> issue amend <issue-id> <remark>
```

## 队列与阻塞

```
# 查看队列状态（含 SLA 超时）
mai --project <path> queue check [queue] [--overdue]

# 查看当前阻塞队列的 issue
mai --project <path> queue blockers

# 列出队列中所有 issue
mai --project <path> issue list [queue]

# 查看 issue 详情
mai --project <path> issue show <issue-id>
```

## 锁控制

```
# 检查锁状态
mai --project <path> lock check <issue-id>

# 强制释放锁（仅在锁持有者失控时使用）
mai --project <path> lock force-release <issue-id>

# 启动锁监护进程（后台运行，自动释放 stale 锁）
mai --project <path> lock guardian
```

## 每日摘要

```
# 触发今日摘要轮转
mai --project <path> daily-summary trigger

# 写入当前 Agent 的摘要内容
mai --project <path> daily-summary write <agent> <content...>

# 读取摘要（<agent> / . 当前agent / --all 全部）
mai --project <path> daily-summary read [<agent>|.|--all]
```

## Issue 升级

```
# 将 issue 升级到上级处理（人工或更高层 Agent）
mai --project <path> issue escalate <issue-id>

# 生成 escalation 文档（issue 详情 + 处理记录）
mai --project <path> escalation gen <issue-id>
```

## 注意事项

- claim 后必须 complete，长期持有锁会阻塞队列
- force-release 仅在持有者失控（断连/超时）时使用
- escalation gen 生成文档，issue escalate 执行升级，两者配合使用
- 详细命令参数和队列配置见下方参考文件

## 参考文件

- [references/commands.md](references/commands.md) — 完整命令速查
- [references/queues.md](references/queues.md) — 队列配置结构与字段说明
