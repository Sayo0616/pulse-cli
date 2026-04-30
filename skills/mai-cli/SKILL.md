---
name: mai-cli
description: 多 Agent 协作工作流规范工具。当 Agent 需要按照标准流程创建（new）、认领（claim）、处理、转交（transfer）、审验（complete/reject）issue 时使用。触发短语：创建 issue、认领 issue、处理 issue、转交 issue、审验 issue、查看队列、处理队列。
---

# mai-cli — 多 Agent 协作工作流

通过统一的 issue 生命周期协调多 Agent 协作。所有操作需携带 `-o <name>` 标明操作者身份。

## 查找项目

通过指令 `project list --agent <name>` 查看 Agent 参与的项目列表，确认项目名称和路径。

### 注意事项

- 使用 `--agent <name>` 过滤只显示当前 Agent 参与的项目，禁止操作他人的项目。
- 不要自己创建mai项目，应该先查找已有的项目，除非用户确实需要一个新项目来管理issue。

## 工作流总览

```
提issue → 接issue → 转issue → 审验issue
  ↓         ↓         ↓           ↓
 创建     认领处理   交给下家    发起者确认
```

## 1. 提 Issue

**目的**：将任务投入到负责人（最终的审验人）队列，说明要解决的问题和预期结果。
**使用场景**：当你需要其他 Agent 协助完成某个任务时，创建一个 issue 描述问题、预期结果和审验标准。

```bash
mai issue new <queue> <title> -o <name> [--priority P0|P1|P2] [--ref <ref-id>]
```

**流程**：
1. 简要描述问题 + 预期结果（写入 title）
2. 用 `--priority` 指定优先级（默认 P2）
3. 如有参考资料或上下文，追加 `--ref` 关联

> 创建后，issue 状态为 **OPEN**，队列 Owner 负责后续分配或认领。

## 2. 接 Issue

**目的**：从自己的队列中筛选最紧急的 issue，认领后开始处理。
**使用场景**：当你准备处理某个 issue 时，先查看自己的队列，选择一个 issue 认领并开始处理。

```bash
# 筛选自己需要处理的 issue
mai queue check --handler <your-name>

# 认领最紧急的 issue
mai issue claim <issue-id> -o <your-name>

# 读取 issue 详情，开始处理
mai issue show <issue-id>

# 处理过程中追加进度/记录
mai issue amend <issue-id> <remark> -o <your-name>
```

**认领后**：状态变为 **IN_PROGRESS**，你成为当前 Handler。

> 处理完成后，**必须** 先追加完成信息，然后用 `issue transfer` 转给下一处理人或返回发起者审验。不得长时间持有锁。

## 3. 转 Issue

**目的**：自己的部分完成后，转交给下一处理人或返回给发起者审验。
**使用场景**：当你完成了自己负责的部分，需要交给下一位处理人继续处理，或者需要发起者审验时，使用转交命令。

```bash
# 转给下一位处理人（自动释放锁）
mai issue transfer <issue-id> <next-handler> -o <your-name>
```

**注意**：
- 仅变更处理人，队列不变
- 转交后 issue 状态保持 **OPEN**，由下一 Handler 认领
- 如果是最终交付，需转回 **发起者** 审验

## 4. 审验 Issue

**目的**：验证处理结果是否符合预期，只有发起者才能确认完成。
**使用场景**：当你是 issue 的发起者，收到处理结果后，需要确认是否符合预期，决定是否完成 issue。

```bash
# 审验通过，确认完成
mai issue complete <issue-id> <conclusion> -o <your-name>

# 或使用别名
mai issue confirm <issue-id> -o <your-name>
```

**审验未通过**：转回对应处理人重新处理

```bash
mai issue transfer <issue-id> <handler> -o <your-name>
```

> `complete` / `confirm` 会将状态置为 **COMPLETED**，自动释放锁。

## 常用命令速查

| 场景 | 命令 |
|------|------|
| 创建 issue | `mai issue new <queue> <title> -o <name>` |
| 查看我的队列 | `mai queue check --handler <name>` |
| 认领 issue | `mai issue claim <issue-id> -o <name>` |
| 查看详情 | `mai issue show <issue-id>` |
| 追加处理记录 | `mai issue amend <issue-id> <remark> -o <name>` |
| 转交处理人 | `mai issue transfer <issue-id> <next-handler> -o <name>` |
| 确认完成 | `mai issue complete <issue-id> <conclusion> -o <name>` |
| 拒绝（重新处理） | `mai issue reject <issue-id> <reason> -o <name>` |

## 角色权责

- **Owner**：工单负责人。负责 `create`、`complete`、`reject` 等管理操作。
- **Handler**：当前处理人。负责执行任务，执行完毕后需 `transfer` 给 Owner 验收。

## 注意事项

- **全局初始化**：首次使用必须运行 `mai setup` 初始化全局配置并设置 Root。
- 严格禁止使用他人的身份处理 issue，必须在 `-o` 参数中明确操作者身份。
- 需要到相应项目的路径下执行命令，或者使用 `--project <path>` 指定项目路径。
- **项目初始化**：`mai init` 强制要求 `-o <operator>` 且仅限 Root 执行。
- 注意留痕，需要同步的信息应该追加到 issue 中，避免私下沟通导致信息不透明。
- 定期检查自己的队列，避免 issue 长时间未处理或锁未释放。

## 参考文档

- [references/commands.md](references/commands.md) — 完整命令参考
- [references/queues.md](references/queues.md) — 队列配置与字段说明