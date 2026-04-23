# Changelog

## v1.8.0 (2026-04-24)
- **REQ: Issue 优先级支持 (P0/P1/P2)** — 为 Issue 引入了优先级字段。支持通过 `mai issue new --priority P0|P1|P2` 指定紧急程度（默认为 P2）。
- **REQ: 优先级排序逻辑** — `issue list` 和 `queue check` 现在全局按优先级升序（P0→P1→P2）排序，同优先级内按创建时间升序。
- **REQ: 冲突升级优先级归一化** — `issue escalate` 生成的冲突升级 Issue 现在默认设置为 P0 最高优先级。
- **Fix: `queue check --handler` 格式修正** — 指定处理人过滤时，输出格式优化为更紧凑的单行模式，并自动隐藏冗余的队列头。
- **Fix: 处理人匹配鲁棒性** — 修复了 `--handler` 匹配时对 `@` 前缀处理不一致的问题。现在无论输入参数还是 Issue 文件中的 `owner` 字段是否包含 `@`，均能正确实现不区分大小写的匹配。

## v1.7.2 (2026-04-23)
- **Fix: Reject Handler Reversion** — 修复了 `issue reject` 时处理人没有正确回退的问题。现在会根据 Timeline 记录自动将 Issue 归还给上一个处理人。
- **Fix: Multi-line Timeline Parsing** — 修复了 `issue show` 无法显示处理记录中换行内容的问题，现在能正确解析并保留多行备注。
- **Fix: Handler Substring Matching** — 将 `--handler` 过滤逻辑优化为不区分大小写的子串匹配，解决部分 Agent 因名称大小写或部分前缀不匹配而搜不到 Issue 的问题。
- **Fix: Creator Fallback Strategy** — 增强了 `submit-to-creator` 的健壮性，当 `creator` 字段意外丢失时，可自动从历史记录中追溯初始发起人。

## v1.7.1 (2026-04-23)
- **ID: 全局唯一哈希 ID** — 重构 Issue ID 生成逻辑，从递增序列升级为 `[Prefix]-[6位随机哈希]`（如 `REQ-94064B`）。新增全局冲突检测，遍历所有队列目录确保 ID 绝对唯一。
- **UX: Handler 参数归一化** — 官方推荐使用不带 `@` 前缀的 Agent 名称作为 `--handler` 参数。同步更新了 README、DEPLOYMENT 和 SKILL 文档示例，并移除了文档中关于“自动剥离 @”的过时描述（代码仍保持兼容）。
- **DOC: 心跳流程标准化** — 重写了 `DEPLOYMENT.md` 中的 `HEARTBEAT.md` 配置示例，将其拆分为“处理人流程 (Handler Flow)”和“发起人验收 (Creator Flow)”，降低 Agent 学习成本。

## v1.7.0 (2026-04-23)
- **REQ: 多步协作流转 (Multistage Flow)** — 新增 `issue transfer`, `issue submit-to-creator`, `issue confirm`, `issue reject` 四大命令，支持从“创建人 → 处理人 A → 处理人 B → 创建人确认”的完整闭环流程。
- **SEC: 锁所有权校验** — 在执行转交、提交、完成、确认等敏感操作前，强制校验当前 Agent 是否持有该 Issue 的 flock 锁，防止越权操作，并保障状态流转的一致性。
- **UI: 智能队列检索** — `queue check` 默认隐藏已完成任务；新增 `--all` 展示全部，`--handler @agent` 过滤特定处理人任务。
- **UI: 超期项筛选** — 为 `queue check` 新增 `--overdue` 命令行标志，支持快速定位 SLA 超时的 Issue。
- **UX: 前缀自动归一化** — `issue list` 和 `queue check` 的 `--handler` 参数现在支持自动剥离 `@` 前缀（如输入 `@alice` 自动转为 `alice`）。
- **AUDIT: 审计记录修正** — 修正了 Issue 初始创建时的 Timeline 记录，确保其归属于 `creator` 而非默认处理人。
- **稳定性: 状态机加固** — 为所有 `issue` 操作增加了状态预检查，禁止在 `COMPLETED` 状态下执行无效的状态流转操作，并实现了操作的幂等性提示。

## v1.6.4 (2026-04-23)
- **REQ: 指定发起方** — `issue new` 新增 `--creator` 参数，允许显式指定 Issue 发起者身份（默认回退至当前 Agent 环境变量）。
- **UI: 状态展示优化** — 移除 `mai status` 和 `mai daily-summary status` 中过时的 "Next up" 逻辑，适配并发独立写入模型。
- **稳定性** — 为 `issue new` 覆盖逻辑新增单元测试。

## v1.6.3 (2026-04-23)
- **Bug 修复** — 修复了 `mai.py` 中 `cmd_status` 命令因缺少 `get_status_emoji` 导入而导致的运行时 `NameError`。
- **稳定性增强** — 为 `cmd_status` 添加了冒烟测试，确保全局状态视图的长期稳定性。

## v1.6.2 (2026-04-23)
- **Bug 修复** — 修复了 `issue.py` 中 `make_issue_content` 在未提供 `project_root` 时无法正确获取默认图标的问题。
- **测试增强** — 修复了测试套件中的 `GLOBAL.dry_run` 状态泄漏问题，并新增了图标与摘要写入的专项验证。
- **图标展示增强** — `mai status` 移除硬编码图标，完全由配置驱动；`issue list` 优化了图标 Fallback 逻辑（使用 ❓）。

## v1.6.1 (2026-04-23)
- **Bug 修复** — 修复了 `daily-summary write` 在接收命令行多个单词作为内容时，误将其写为 Python 列表字符串表示的问题。
- **状态解析优化** — 修复了 `issue.py` 在解析不带图标的状态字段时的正则 Bug，增强了手动编辑后的兼容性。

## v1.6.0 (2026-04-23)
- **REQ-001: 发起方与处理方分离** — Issue 结构新增 `creator` 字段，支持跨 Agent 协作追踪。
- **REQ-003: 简化队列命名** — `mai agent add` 创建的默认队列名不再包含 `-tasks` 后缀，直接与 Agent 名一致。
- **REQ-004: 并发每日摘要** — 废除摘要写入的强制顺序，改为基于状态表的独立写入模式，大幅提升协作灵活性。
- **REQ-002: 可视化监控增强** — `mai issue list` 新增状态图标、实时锁持有者显示；支持 SLA 超时 (⏱️) 动态叠加提示。
- **自定义配置** — `config.json` 新增 `issue_status_emoji` 字段，支持自定义所有状态展示图标。

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
