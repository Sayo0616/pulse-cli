> 本文档归属：APPENDIX.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §十+§十一+附录

## 十、Bitable 待办管理

通过飞书多维表格组织维护所有 Agent 待处理项，**自动同步而非人工维护**：

```
Agent 心跳 → mai issue new/list/complete 等命令
          → 指令系统写入 .mai
          → 自动同步到 bitable（通过 feishu_bitable_app_table_record API）
```

### P1-2 bitable 同步容错

在 `bitable-sync/` 下维护 `sync-state.json`（由 `mai` 命令自动更新）：

```json
{
  "last_sync": "2026-04-19T13:45:00+08:00",
  "status": "ok",
  "failed_items": [],
  "retry_count": 0,
  "max_retries": 3
}
```

**`failed_items` 格式定义：**
```json
[
  {
    "issue_id": "REQ-003",
    "operation": "create|update|delete",
    "error": "rate_limit_exceeded|network_error|permission_denied",
    "attempted_at": "2026-04-19T13:44:00+08:00"
  }
]
```

**查询命令：**
```
mai bitable sync-status
```

**容错逻辑：**
- API 调用失败 → `status: failed`，记录 `failed_items`，重试 +1
- 重试 3 次仍失败 → `status: stuck`，**停止重试**，在 `designer-blockers/` 写入告警 Issue，同时**通知相关 Agent**：
  - 若对应的 Issue 在 `quick-fix-requests/` → 同时通知 programmer（已修复但同步失败）
  - 其他队列 → 只通知 designer（由 designer 决定处理方式）
- `status: ok` 后清除 `failed_items` 和 `retry_count`

**数据一致性原则：** `.mai` 是 Source of Truth；bitable 是可视化层面副本；二者不一致时以 `.mai` 为准。

---

## 十一、安全与审计

### 11.1 最小权限访问控制（通过命令保证）

| 目录 | 允许写入 | 允许读取 | 通过命令 |
|:---|:---|:---|:---|
| `.mai/queues/<queue>/` | 指令系统内部 | 指令系统内部 | `mai issue new` |
| `async/<queue>/` | **Agent 不可直接写入** | 仅 Sayo 可读（可视化镜像） | 通过命令同步（Agent 使用 `issue show/list` 获取信息） |
| `.mai/processing/` | 指令系统内部 | 指令系统内部 | `mai issue claim` |
| `.mai/locks/` | 指令系统内部 | 所有 Agent（通过 `mai lock check`） | `mai lock *` |
| `.mai/decisions/` | 指令系统内部 | 所有 Agent（只读） | `mai issue complete` |
| `async/history/` | 无（append-only） | 所有人 | `mai log write` |

### 11.2 锁文件访问

| 文件 | 允许操作 |
|:---|:---|
| `.mai/locks/*.lock` | 创建/删除由 `mai` 命令处理（持锁方或超时强制） |
| 查询锁状态 | `mai lock check <issue-id>`（所有 Agent） |

### 11.3 审计日志

每次通过命令操作协作数据时，自动追加到 `.mai/history/YYYY-MM-DD.log`（append-only）：

```
[2026-04-19 11:35] programmer@heartbeat → architect-decisions/REQ-001.md [创建]
[2026-04-19 11:52] architect@heartbeat → architect-decisions/REQ-001.md [认领]
[2026-04-19 12:10] architect@heartbeat → architect-decisions/REQ-001.md [完成]
```

**Agent 可通过以下命令查看审计历史：**
```
mai log history [--date YYYY-MM-DD] [--agent <agent>]
```

---

## 附录 A：Agent 协作标准流程（命令版）

### A.1 典型 programmer 工作流

```
1. 心跳启动
   $ mai queue check architect-decisions --overdue
   $ mai log write programmer heartbeat "正常" "进行中"

2. 发现逻辑漏洞
   $ mai issue new programmer-questions "AI 路径在边缘情况出错"
   # 或走快通道（如果可量化）
   $ mai issue new quick-fix-requests "strings.json 拼写错误：bananer → banana"

3. 收到快通道修复请求
   $ mai issue list quick-fix-requests
   $ mai issue claim FIX-001
   # 执行修复
   $ mai issue complete FIX-001 "已修复拼写错误"
```

### A.2 典型 architect 工作流

```
1. 心跳启动
   $ mai queue check architect-decisions
   $ mai log write architect heartbeat "正常" "进行中"

2. 处理技术方案审批
   $ mai queue check architect-decisions
   $ mai issue claim REQ-003
   # 审查方案
   $ mai issue complete REQ-003 "技术方案可行，同意实现"

3. 事后发现技术问题
   $ mai issue new architect-reviews-designer "渲染管线事后否决：DX12 支持问题"
```

### A.3 典型 designer 工作流

```
1. 心跳启动
   $ mai queue blockers  # 合并检查 blocker
   $ mai log write designer heartbeat "正常" "进行中"

2. 处理 programmer 上报问题
   $ mai queue check programmer-questions
   $ mai issue list programmer-questions
   # 认领并处理
   $ mai issue claim REQ-005
   $ mai issue complete REQ-005 "体验标准通过，同意实现"

3. 处理超时积压
   $ mai queue blockers
   # 若有积压 → 生成合并报告 → 飞书通知用户
```

### A.4 每日定时任务（cron）

```
# 每5分钟：守护进程，释放过期的 .daily-lock
*/5 * * * * mai lock guardian

# 每日18:00：触发每日汇总事件
0 18 * * * mai daily-summary trigger
```

**Agent 心跳汇总处理（第 6 步）：**
- 各 Agent 心跳第 6 步执行 `mai daily-summary write <agent> "<当日摘要>"`
- 命令内部自动检查 `.daily-summary-event` 是否存在、是否轮到本 Agent；若不符合条件则幂等跳过
- designer 在最后执行 `mai daily-summary collect` 生成最终汇总

> 注：体验抽查（每1小时）由 designer 心跳轮次处理，无需独立 cron。

---

## 附录 B：指令系统文件清单

| 文件 | 位置 | 说明 |
|:---|:---|:---|
| `mai.py` | `~/.openclaw/workspace/agents/shared-workspace/scripts/` | 主入口脚本 |
| `mai SKILL.md` | `~/.openclaw/workspace/agents/shared-workspace/scripts/` | Skill 配置 |
| `queues.yaml` → 取消 | `.mai/config.json` 内嵌 | 队列配置移入项目内部配置 |
| `safe-exec-list.json` | `~/.openclaw/workspace/agents/shared-workspace/` | exec 白名单（用户维护） |
| `exec-auth-log.md` | `~/.openclaw/workspace/agents/shared-workspace/` | exec 授权记录 |
| `project.config.json` | `projects/<项目名>/` | 对外项目配置 |
| `.mai/config.json` | `projects/<项目名>/.mai/` | 内部协作配置（SLA、心跳间隔） |
