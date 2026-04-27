---
name: mai-cli
description: 多 Agent 协作命令行工具。当 Agent 需要创建（new）issue、认领（claim）issue、完成（complete）issue、补充说明（amend）、查看队列状态（queue check）、触发每日摘要（daily-summary trigger/write/read）、强制释放锁（lock release --force）、或升级 issue（issue escalate）时使用。触发短语：创建 issue、认领 issue、完成 issue、查看队列、触发摘要、强制释放锁、escalate。
---

# mai-cli — 多 Agent 协作命令行工具

mai-cli 通过 flock 原子锁和队列路由协调多 Agent 工作流。

## 通用命令格式

所有命令可附加 `--project <共享工作区路径>`，项目已初始化时 mai 会自动向上查找，实际使用时可省略。

## Issue 生命周期

所有写操作均需携带 `-o` / `--operator <name>` 参数（REQ-A）。

```
# 1. 新建 issue（指定队列，优先级默认 P2）
mai --project <path> issue new <queue> <title> -o <name> [--ref <ref-id>] [--priority P0|P1|P2]

# 2. 认领 issue（加 flock 锁，状态 → IN_PROGRESS，自动成为当前 Handler）
mai --project <path> issue claim <issue-id> -o <name>

# 3. 如遇阻塞，标记 blocked
mai --project <path> issue block <issue-id> <原因> -o <name>

# 4. 解除阻塞
mai --project <path> issue unblock <issue-id> -o <name>

# 5. 修订/补充备注
mai --project <path> issue amend <issue-id> <remark> -o <name>

# 6. 转交任务（自动释放锁，状态保持为 OPEN；注意：仅变更处理人，队列不变）
# 转交后，任务通常由下一位处理人认领，或交还给 Owner 结项
mai --project <path> issue transfer <issue-id> <next-handler> -o <name>

# 7. Owner/Root 验收与反馈
# 确认完成（状态 → COMPLETED，只能由队列负责人或管理员执行）
mai --project <path> issue complete <issue-id> <conclusion> -o <name>
# 或使用 alias:
mai --project <path> issue confirm <issue-id> -o <name>

# 拒绝结论（恢复为 OPEN 并退回给前任负责人，只能由负责人或管理员执行）
mai --project <path> issue reject <issue-id> <原因> -o <name>

# 8. 如需重开（只能由负责人或管理员执行）
mai --project <path> issue reopen <issue-id> <原因> -o <name>
```

## 队列与检索

```
# 查看队列状态（默认隐藏 COMPLETED）
# --all 显示全部，--overdue 只看超时，--handler 过滤处理人
# queue 可以指定具体队列，也可省略查看所有队列
mai --project <path> queue check [queue] [--all] [--overdue] [--handler <agent>]

# 列表展示 Issue（支持过滤）
mai --project <path> issue list [queue] [--handler <agent>]

# 查看 issue 详情
mai --project <path> issue show <issue-id>
```

## 锁控制

```
# 检查锁状态
mai --project <path> lock check <issue-id>

# 正常释放锁（仅持有者或 stale 锁可操作）
mai --project <path> lock release <issue-id>

# 强制释放锁（需交互确认）
mai --project <path> lock release <issue-id> --force

# 静默强制释放（非 TTY/CI 环境）
mai --project <path> lock release <issue-id> --yes

# 启动锁监护进程（后台运行，自动释放 stale 锁）
mai --project <path> lock guardian
```

## 每日摘要

```
# 触发今日摘要轮转
mai --project <path> daily-summary trigger

# 查看当前轮次进度
mai --project <path> daily-summary status

# 重置今日轮次（如需重新来过）
mai --project <path> daily-summary reset

# 4. 写入当前 Agent 的摘要内容（不限顺序，需先 trigger）
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

## 全局状态

```
# 查看全局项目状态
mai --project <path> status

# 查看详细 issue 列表
mai --project <path> status --verbose
```

## Agent 与日志

```
# 在当前目录初始化项目
mai --project <path> init

# 在指定路径初始化项目
mai --project <path> project init [project-name]

# 列出所有已注册 Agent
mai --project <path> agent list

# 撤销最近一次日志写入
mai --project <path> log undo
```

## 注意事项

- **操作署名制**：v1.9.0 后，所有对 Issue 状态或元数据的修改都必须附带 `-o` / `--operator <name>`，否则命令将失败。
- **角色权责分明**：
    - **Root**：全权限管理员。
    - **Owner**：队列负责人。负责 `create`, `complete`, `transfer`, `reject`, `reopen`, `escalate` 等管理 操作。
    - **Handler**：当前处理人。负责执行任务，可进行 `claim`, `amend`, `block`, `unblock`, `transfer` 等操 作。执行完毕后需 `transfer` 给 Owner 验收。

- claim 后必须 transfer 或 block，长期持有锁会阻塞队列。
- `lock release --force` 在 CI/脚本环境使用 `--yes` 跳过交互确认。
- escalation gen 生成文档，issue escalate 执行升级，两者配合使用。
- 详细命令参数和队列配置见下方参考文件。

## 参考文件

- [references/commands.md](references/commands.md) — 完整命令速查
- [references/queues.md](references/queues.md) — 队列配置结构与字段说明
