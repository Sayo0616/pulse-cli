# Changelog

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
