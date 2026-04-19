要让这五个 Agent 真正做到\*\*“完美配合、长时间自主推进中大型项目”**，单纯依靠现在的状态机是不够的。随着项目的推进，系统必然会遇到**上下文爆炸**和**逻辑死锁\*\*的问题。

我认为系统还需要在以下四个维度进行升级（建议作为 v3.0 的规划）：

### 1\. 任务依赖拓扑（DAG）：从“扁平队列”到“阻塞图”

* **当前痛点：** 现有的 `issue` 系统是扁平的。如果 Programmer 要实现一个功能，需要 Architect 先定好网络协议，同时需要 TechArtist 提供一个着色器。目前没有一种原生的方式来表达这种“多重依赖”。
* **升级方案：** 在 `agents-cmd issue new` 命令中加入 `--depends-on <issue-id>` 参数。

* 当一个 Issue 有未完成的前置依赖时，它在队列中处于 `Blocked` 状态，对处理方隐藏或标灰。
* 当前置 Issue 被 `complete` 时，后置 Issue 自动解锁变为 `Ready`。这能让 Agent 的工作流像流水线一样精准，避免 Programmer 提前动工导致返工。

### 2\. 长上下文坍缩与 RAG（记忆检索）：解决 Token 爆炸

* **当前痛点：**`.cmd/decisions/` 目录会随着项目推进无限增长。如果 Agent 每次心跳都把所有历史决策塞进 Prompt，不但 Token 费用高昂，还会导致模型注意力分散（Lost in the middle）。
* **升级方案：** 引入一个只读的“知识库（Knowledge Base）”机制。

* 禁止 Agent 随意读取全量历史，改为在 `agents-cmd` 中增加 `search` 和 `summarize` 命令。
* 例如：`agents-cmd memory search "关于多光源渲染的往期决策"`。系统底层通过向量检索（RAG）或定期对旧 Decision 进行 LLM 总结坍缩，来保证 Agent 永远有清晰且不超载的上下文。

### 3\. 死循环熔断器（Loop Breaker）：防 Token 消耗黑洞

* **当前痛点：** 目前的 SLA 都是基于**时间**的（如 2 小时超时）。如果 Programmer 写了一段代码，运行测试报错，再修，再报错……在短短 20 分钟内心跳了 10 次，尝试了 10 次都失败，这虽然没触发时间超时，但构成了严重的“行为死循环”。
* **升级方案：** 在 `agents-cmd` 内部增加**迭代计数器（Iteration Tracker）**。

* 对于同一个 Issue，如果某个 Agent 进行相似的“重试”动作（或者两个 Agent 之间比如 Programmer 和 TechArtist 快速互相驳回）超过 N 次（例如 5 次）。
* 系统立即强制中断当前操作，自动生成一个高级别的冲突/求助报告，并休眠相关 Agent，等待人类（Sayo）介入。

### 4\. 基于 Git 的物理工作区快照（Workspace Snapshotting）

* **当前痛点：** 尽管有 `safe-exec-list.json` 限制，但 Programmer 依然在直接修改真实项目的代码。如果 Designer 最终“一票否决”了某个体验，Programmer 需要自己写代码把改动撤销回去——这对于 LLM 来说极其困难且极易出错。
* **升级方案：** 将 `agents-cmd issue claim` 和 `issue complete` 与 Git 深度绑定。

* 当 Programmer 认领一个大 Issue 时，`agents-cmd` 自动为其检出一个新分支或执行 `git stash/commit`。
* 如果该特性最终被否决或撤销，系统能提供一个 `agents-cmd project rollback <issue-id>` 的命令，一键将物理文件恢复到修改前的干净状态，卸下 Agent 自己去“修 Bug 式撤销”的负担。

总而言之，目前的 v2 解决了\*\*“一群 Agent 如何不打架地沟通”**，而下一步的升级需要解决**“这群 Agent 如何处理长线记忆和死循环”\*\*。加入依赖图、记忆坍缩和物理回滚后，这个系统就能真正实现长周期无人值守运转了。