# Multi-Agent 协同工作设计方案：审验评估报告 (v2.6 指令系统版)

**评估时间：** 2026-04-19 **评估对象：** Multi-Agent 协同工作设计方案 v2.6（指令系统版） **评估结论：****架构迎来了质变。引入 `agents-cmd` 抽象层将系统的工程可靠性提升到了准生产级别（Production-Ready）。系统巧妙地利用 CLI 屏蔽了 LLM 的操作不确定性，但在“Cron 调度与 Agent 交互边界”和“镜像存储一致性”上仍有微调空间。全量采纳，并建议打上微调补丁后进入封测。**

## 一、 核心架构升级亮点 (Architectural Triumphs)

### 1\. 完美的控制反转 (Inversion of Control via CLI)

原方案中，系统依赖 Agent 去“自觉”遵守移动文件、加锁、追加文本等繁琐规则，这极易因 LLM 幻觉导致状态机崩溃。v2.6 引入 `agents-cmd`，将所有协作元数据封装在 `.cmd/` 目录中对 Agent 隐藏，实现了绝佳的封装。Agent 从\*\*“文件系统操作员”**变成了**“API 调用者”\*\*，输出的确定性得到了指数级提升。

### 2\. POSIX `flock` + 守护进程 (Bulletproof Concurrency)

废弃了脆弱的“文件存在即锁定”机制，改用系统底层的 `flock(LOCK_EX | LOCK_NB)`。

* **防止死锁：**`flock` 在进程崩溃/退出时由操作系统级自动释放。
* **Guardian 守护进程：** 独立于 Agent 心跳，每 5 分钟由系统 Cron 触发的 `lock guardian` 扫尾清理，构成了严密的双保险，彻底杜绝了 Orphan Lock（孤儿锁）瘫痪队列的风险。

### 3\. 标准化心跳 SOP (Standardized Operating Procedure)

在 §9.4 中硬编码了每个 Agent 心跳必须执行的 5 步命令。这为 Prompt Engineering 提供了极其坚实的骨架，避免了 Agent 在空闲心跳时“无所事事”或“自行加戏”。

### 4\. 幂等性与 JSON 结构化输出

命令的 `[--format json]` 选项和严格的退出码（0/1/2/3/4）设计，对 LLM 的工具调用（Tool Calling / Function Calling）极度友好。LLM 可以精准捕获 `LOCK_HELD` 等错误并进行分支决策。

## 二、 潜在风险与逻辑盲点 (Identified Risks & Blind Spots)

尽管系统十分健壮，但在“指令系统层”与“Agent 行为层”的交界处，仍存在几个需要澄清的边缘场景：

### 1\. `async/` 镜像层的“脑裂”风险 (Split-Brain Risk)

**描述：** 设计中提到 `.cmd/` 是内部存储，而 `async/` 是暴露给 Agent 读取的镜像层。 **风险：** 既然 Agent 可以使用 `agents-cmd issue list/show` 来获取 Issue 状态和详情，为何还需要允许 Agent 直接去读取 `async/` 目录？如果指令系统的同步脚本发生微小延迟或失败，Agent 直接读取 `async/REQ-003.md` 会得到脏读（Dirty Read），导致决策基于过时状态。 **定性：** 架构冗余导致的潜在数据不一致。

### 2\. `daily-summary` 的调度倒置 (Scheduling Inversion)

**描述：** 规定中写道 `0 18 * * * agents-cmd daily-summary`，由 Cron 触发。 **风险：** Cron 触发的是一个 Python 脚本。但 Daily Summary 需要 5 个 Agent 依据当天的日志**生成总结文本**。 如果 Cron 只是运行 `agents-cmd` 脚本，这个脚本是如何“唤醒” LLM 去执行思考和生成的？

* **情况 A：**`agents-cmd daily-summary` 内部包含了调用 5 个 LLM API 的逻辑。（此时它是一个编排脚本，脱离了“命令系统”的定义）。
* **情况 B：**`agents-cmd daily-summary` 只是创建一个锁或发布一个事件，但 Cron 并没有能力唤醒休眠中的 Agent。Agent 必须等自己的下一个心跳才能发现这个事件。 **定性：** 调度机制语义模糊，可能导致 18:00 的汇总任务在实现时卡壳。

### 3\. `designer-blockers` 的重复轰炸风暴

**描述：** 心跳步骤中：`queue check --overdue` 发现超时 -> 立即 `issue new designer-blockers ... --ref <id>`。 **风险：** 虽然方案提到“去重规则”，但如果去重逻辑仅仅是“检查 designer-blockers 队列里有没有”，那么当 Designer 完成了某个 Blocker（并将其归档）后，如果原 Issue 仍然处于超时且未解决状态，下一次 Programmer/Architect 的心跳又会重新触发超时上报，导致已经看过的 Blocker 死灰复燃。 **定性：** 状态机闭环漏洞。

## 三、 封测前微调建议 (Refinement Patches)

建议在进入开发阶段前，对方案进行以下 3 点微调补丁（无需大改，只需在代码实现时明确）：

### 补丁 1：废除 Agent 对 `async/` 目录的直读权限

修改 §3.3 设计：彻底斩断 Agent 直接读取 `projects/<项目名>/async/` 文件的权限。

* **新规则：**`async/` 目录仅作为**人类（Sayo）观察系统运行状态的可视化镜像**。Agent 的 Skill 限制中增加一条：`获取 Issue 详情必须使用 agents-cmd issue show <id>，禁止使用 cat / read 读取 async 目录`。

### 补丁 2：明确 `daily-summary` 的触发模型

如果保留 Cron，建议采用 **Event-Driven (事件驱动)** 模型，而不是让 Cron 直接执行汇总：

* Cron 在 18:00 执行：`agents-cmd daily-summary trigger`（仅在 `.cmd/locks/` 中创建一个特殊的全局 `.daily-summary-event` 标志）。
* 各 Agent 的心跳逻辑（§9.4）中加入第 6 步：检查是否存在 `.daily-summary-event`，若存在且轮到自己，则执行 `agents-cmd daily-summary write "我的总结..."`。
* 这样完美契合了当前的“心跳驱动 Agent”底层逻辑。

### 补丁 3：在原始 Issue 级实现超时标记 (Blocker State in Parent)

为彻底解决超时重复上报风暴：

* 修改 `agents-cmd queue check --overdue` 的内部逻辑：当它发现 `REQ-003` 超时并自动创建 `BLK-001` 后，必须在 `.cmd/queues/.../REQ-003.json` 的元数据中打上一个标签 `"escalated_blocker_id": "BLK-001"`。
* 下次 `queue check` 时，发现该 Issue 已经有此标签，则直接静默，不再重复生成 Blocker，直到该 Issue 的状态发生实质性转变。

## 四、 最终结论

这套以 CLI 为核心协调器的设计，不仅解决了 Token 爆炸和文件系统竞态问题，其强制的规范化接口也使得系统未来的监控、前端面板搭建（甚至直连 Bitable API）变得极其简单。**这标志着该系统从“实验性 Agent 玩具”正式毕业，成为了“生产力工具”。**