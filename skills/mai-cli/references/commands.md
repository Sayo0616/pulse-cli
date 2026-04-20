# mai-cli 命令参考

所有命令前缀：`mai --project <共享工作区路径>`

## issue 子命令

| 命令 | 说明 |
|------|------|
| `issue new <queue> <title> [--ref <ref-id>]` | 新建 issue 到指定队列 |
| `issue claim <issue-id>` | 认领 issue（加 flock 锁） |
| `issue complete <issue-id> <conclusion>` | 完成 issue（释放锁，记录结论） |
| `issue amend <issue-id> <remark>` | 补充说明或备注 |
| `issue list [queue]` | 列出队列中的所有 issue |
| `issue show <issue-id>` | 查看 issue 详情 |
| `issue escalate <issue-id>` | 将 issue 升级到上级处理 |

## queue 子命令

| 命令 | 说明 |
|------|------|
| `queue check [queue] [--overdue]` | 检查队列状态，可选只显示 SLA 超时项 |
| `queue blockers` | 显示当前阻塞队列的 issue |

## lock 子命令

| 命令 | 说明 |
|------|------|
| `lock check <issue-id>` | 查看 issue 的锁状态 |
| `lock force-release <issue-id>` | 强制释放锁（仅在持有者失控时使用） |
| `lock guardian` | 启动锁监护进程（后台运行，自动释放 stale 锁） |

## daily-summary 子命令

| 命令 | 说明 |
|------|------|
| `daily-summary trigger` | 触发今日摘要轮转 |
| `daily-summary write <agent> <content...>` | 写入指定 Agent 的摘要内容 |
| `daily-summary read [<agent>\|.\|--all]` | 读取摘要，`.` 表示当前 Agent，`--all` 读取全部 |

## escalation 子命令

| 命令 | 说明 |
|------|------|
| `escalation gen <issue-id>` | 生成 issue 的 escalation 文档（issue 详情 + 历史记录） |
| `issue escalate <issue-id>` | 将 issue 标记为已升级，触发上级处理流程 |

**注意**：`escalation gen` 生成文档（供人工或外部审查），`issue escalate` 执行升级操作（改变 issue 状态）。两者配合使用，先 gen 再 escalate。

## project 子命令

| 命令 | 说明 |
|------|------|
| `project init <project-name>` | 在当前目录初始化新的 mai-cli 项目，生成 `.mai/` 目录和 `config.json` |
