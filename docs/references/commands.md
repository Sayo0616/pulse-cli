# mai-cli 命令参考

## 全局选项

| 选项 | 说明 |
|------|------|
| `-v, --version` | 显示程序版本号并退出 |
| `--project <path>` | 指定项目根目录（默认从环境变量推断） |
| `--format <json\|text>` | 指定输出格式（默认 text） |
| `--dry-run` | 模拟执行模式，不产生实际修改 |

## init 子命令 (快捷方式)

| 命令 | 说明 |
|------|------|
| `init [project-name]` | 在当前目录（.）或默认项目路径初始化项目 |

## issue 子命令

| 命令 | 说明 |
|------|------|
| `issue new <queue> <title> [--ref REQ-XXX]` | 新建 issue 到指定队列 |
| `issue claim <issue-id>` | 认领 issue（加锁） |
| `issue complete <issue-id> <conclusion>` | 完成 issue（释放锁） |
| `issue amend <issue-id> <remark>` | 补充说明 |
| `issue list [queue]` | 列出队列中的 issue |
| `issue show <issue-id>` | 查看 issue 详情 |
| `issue escalate <issue-id>` | 升级 issue 到上级处理 |

## queue 子命令

| 命令 | 说明 |
|------|------|
| `queue check [queue] [--overdue]` | 检查队列状态，可选只显示超时项 |
| `queue blockers` | 显示当前阻塞队列的 issue |

## lock 子命令

| 命令 | 说明 |
|------|------|
| `lock check <issue-id>` | 查看 issue 的锁状态 |
| `lock force-release <issue-id>` | 强制释放锁 |
| `lock guardian` | 扫描并释放超时锁（建议 cron 触发） |

## daily-summary 子命令

| 命令 | 说明 |
|------|------|
| `daily-summary trigger` | 触发今日摘要轮转 |
| `daily-summary write <agent> <content...>` | 写入某 Agent 的摘要（由 flock 保护） |
| `daily-summary read [<agent>\|.\|--all]` | 读取摘要（.=当前 agent，--all=生成汇总报告） |

## log 子命令

| 命令 | 说明 |
|------|------|
| `log history [--date YYYY-MM-DD] [--agent NAME]` | 查询审计历史 |
| `log write <agent> <type> <summary> [status]` | 写入标准化工作记录 |

## escalation 子命令

| 命令 | 说明 |
|------|------|
| `escalation gen <issue-id>` | 生成 escalation 文档模板 |

## exec 子命令

| 命令 | 说明 |
|------|------|
| `exec safe-check <cmd>` | 检查命令是否包含危险操作模式 |

## project 子命令

| 命令 | 说明 |
|------|------|
| `project init <project-name>` | 在默认项目路径初始化新项目 |
