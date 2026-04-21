# Changelog

## v1.5.0 (2026-04-21)
- **REQ-009: 自动项目探测** — 移除 `--project` 强制要求，默认从当前目录向上递归搜索 `.mai/config.json`；支持 `MAI_PROJECT` 环境变量优先级最高。
- **REQ-013: Dry-run 漏洞修复** — `acquire_lock` 和 `release_lock` 在 `--dry-run` 模式下完全不产生任何文件。
- **REQ-011: 日报状态机透明化** — 引入持久化 `status.json` 取代临时 event file；新增 `mai daily-summary status` 和 `mai daily-summary reset` 命令。
- **REQ-012: 全局状态视图** — 新增 `mai status [--verbose]` 命令，聚合展示队列计数、锁持有情况及日报进度。
- **REQ-008: Issue 过程追踪** — 引入 `IN_PROGRESS` 和 `BLOCKED` 状态；新增 `mai issue block/unblock/status` 命令；`claim` 时状态从 OPEN → IN_PROGRESS。
- **REQ-017: 撤销与重开标准化** — `mai issue reopen` 带原因记录；`mai log undo` 基于 `.log.bak` 快照恢复；Lock Release 三档语义（normal / `--force` / `--yes`）。
- **REQ-014: 模糊匹配与引导报错** — 集成 `difflib`，队列/Agent 名拼错时给出 `Did you mean...?` 建议；所有报错统一增加 `HINT: Run 'mai ...'` 指引。
- **mai init 简化** — `mai init` 不接受任何参数，始终初始化当前目录。
- **新增 `mai agent list`** — 列出所有已注册 Agent。

## v1.4.0 (2026-04-20)
- **通用默认值 (REQ-003)**：将默认 Agent 设为 `default`，取消硬编码具体项目角色，提高 CLI 通用性。支持旧版配置中的 legacy 队列回退，保障老项目无缝兼容。
- **Agent 管理 (REQ-004)**：新增 `mai agent add` 命令，支持动态注册 Agent 并自动创建 `<agent>-tasks` 任务队列。
- **约束加强**：`mai daily-summary read` 在未指定 `--all` 时必须明确指定目标 Agent。

## v1.3.0 (2026-04-20)
- **版本管理统一**：移除源码中的硬编码版本号，统一使用 `importlib.metadata`。
- **并发安全性**：在 `daily_summary_write` 中引入 `flock` 锁保护，确保多 Agent 并发写入日报时的原子性。
- **命令行优化**：
  - 添加 `-v/--version` 旗舰支持。
  - 新增 `mai init [name]` 快捷命令，支持在当前目录初始化。
  - 增强子命令 `dispatch` 的返回值透传，支持编程式调用。
- **流程行为变更**：每日汇报事件文件现在会在 `order` 中的最后一个 Agent 写入完成后立即删除。这 enforces 了严格的轮转周期，但在最后一个 Agent 完成后将无法再进行追加或重试，请确保流程完整。

## v1.1.0 (2026-04-19)
- 配置外部化：所有协作规则移至 config.json
- 深度合并 fallback：支持老配置平滑迁移
- 兼容旧格式（owner→handler，sla_hours→sla_minutes）

## v1.0.0 (2026-04-19)
- 初始版本：26 个命令，flock 原子锁，事件驱动每日汇总
