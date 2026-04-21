# mai-cli 命令参考

所有命令前缀：`mai --project <共享工作区路径>`（项目已初始化时可省略）

## issue 子命令

| 命令 | 说明 |
|------|------|
| `issue new <queue> <title> [--ref <ref-id>]` | 新建 issue 到指定队列 |
| `issue claim <issue-id>` | 认领 issue（加 flock 锁），状态 → IN_PROGRESS |
| `issue block <issue-id> <reason>` | 标记 issue 为 BLOCKED（记录原因） |
| `issue unblock <issue-id>` | 解除 BLOCKED，恢复为 IN_PROGRESS |
| `issue complete <issue-id> <conclusion>` | 完成 issue（释放锁，记录结论） |
| `issue reopen <issue-id> <reason>` | 重新打开已完成的 issue（记录原因） |
| `issue status <issue-id>` | 查看 issue 状态历史时间线 |
| `issue amend <issue-id> <remark>` | 补充说明或备注 |
| `issue list [queue]` | 列出队列中的所有 issue |
| `issue show <issue-id>` | 查看 issue 详情 |
| `issue escalate <issue-id>` | 将 issue 升级到上级处理 |

## queue 子命令

| 命令 | 说明 |
|------|------|
| `queue check [queue] [--overdue]` | 检查队列状态，可选只显示 SLA 超时项 |
| `queue blockers` | 显示当前阻塞队列的 issue |
| `queue create <queue> --owner <agent> [--sla <hours>]` | 创建新队列 |

## lock 子命令

| 命令 | 说明 |
|------|------|
| `lock check <issue-id>` | 查看 issue 的锁状态 |
| `lock release <issue-id>` | 正常释放锁（仅持有者可操作） |
| `lock release <issue-id> --force` | 强制释放锁（需确认，非 TTY 环境用 --yes） |
| `lock release <issue-id> --yes` | 静默强制释放锁（跳过确认） |
| `lock guardian` | 启动锁监护进程（后台运行，自动释放 stale 锁） |

## log 子命令

| 命令 | 说明 |
|------|------|
| `log history [--date YYYY-MM-DD] [--agent NAME]` | 查看历史日志 |
| `log undo` | 撤销最后一次日志写入（基于 .log.bak 快照） |
| `log write <agent> <type> <summary> [status]` | 写入日志条目 |

## daily-summary 子命令

| 命令 | 说明 |
|------|------|
| `daily-summary trigger` | 触发今日摘要轮转 |
| `daily-summary status` | 查看当前轮次进度 |
| `daily-summary reset` | 重置今日轮次（删除 status.json） |
| `daily-summary write <agent> <content...>` | 写入指定 Agent 的摘要内容（按顺序） |
| `daily-summary read [<agent>|.|--all]` | 读取摘要，`.` 表示当前 Agent，`--all` 读取全部 |

## escalation 子命令

| 命令 | 说明 |
|------|------|
| `escalation gen <issue-id>` | 生成 issue 的 escalation 文档（issue 详情 + 历史记录） |
| `issue escalate <issue-id>` | 将 issue 标记为已升级，触发上级处理流程 |

**注意**：`escalation gen` 生成文档（供人工或外部审查），`issue escalate` 执行升级操作（改变 issue 状态）。两者配合使用，先 gen 再 escalate。

## exec 子命令

| 命令 | 说明 |
|------|------|
| `exec safe-check <command>` | 在沙盒环境中安全执行命令（预览模式） |

## project / agent 子命令

| 命令 | 说明 |
|------|------|
| `init` | 在当前目录初始化 mai-cli 项目（不接受参数） |
| `project init [project-name]` | 在指定路径初始化项目，name 可选 |
| `agent list` | 列出所有已注册的 Agent |
| `agent add <name> [--heartbeat-minutes 30]` | 注册新 Agent 并创建默认任务队列 |

## status 命令

| 命令 | 说明 |
|------|------|
| `status [--verbose]` | 全局项目视图：队列摘要、锁状态、日报进度。`verbose` 输出各队列详细 issue 列表 |
