# 队列配置参考

## 配置文件

配置文件位置：`.mai/config.json`（相对于共享工作区根目录）。

## 完整配置结构

```json
{
  "queues": {
    "<queue-name>": {
      "handler": "<agent-name>",
      "sla_minutes": <number>,
      "id_prefix": "<prefix>"
    }
  },
  "agents": {
    "<agent-name>": {
      "heartbeat_minutes": <number>
    }
  },
  "daily_summary_order": ["<agent>", ...]
}
```

## queues 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `handler` | string | 负责处理该队列的 Agent 名称 |
| `sla_minutes` | int | SLA 超时时间（分钟），超时后 issue 标记为 overdue |
| `id_prefix` | string | issue ID 前缀，例如 `"ARC"` 生成 `ARC-001` |

## agents 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `heartbeat_minutes` | int | Agent 心跳间隔（分钟），锁在 `heartbeat × 1.5` 分钟后自动释放 |

## daily_summary_order

数组，定义每日摘要的轮转顺序。每个 Agent 按顺序在各自的窗口内调用 `daily-summary write` 写入摘要。

## 兼容性别名字段

| 旧字段 | 新字段 | 说明 |
|------|------|------|
| `owner` | `handler` | 同义，兼容旧配置 |
| `sla_hours` | `sla_minutes` | 同义，按分钟计算 |

## 标准五队列配置

```json
{
  "queues": {
    "architect-questions":  { "handler": "architect",  "sla_minutes": 120, "id_prefix": "ARC" },
    "programmer-questions": { "handler": "programmer", "sla_minutes": 120, "id_prefix": "PRG" },
    "designer-questions":   { "handler": "designer",   "sla_minutes": 120, "id_prefix": "DSN" },
    "narrative-questions":  { "handler": "narrative",  "sla_minutes": 120, "id_prefix": "NAR" },
    "techartist-questions": { "handler": "techartist", "sla_minutes": 120, "id_prefix": "TAT" }
  },
  "agents": {
    "architect":  { "heartbeat_minutes": 17 },
    "programmer": { "heartbeat_minutes": 17 },
    "designer":   { "heartbeat_minutes": 29 },
    "narrative":  { "heartbeat_minutes": 29 },
    "techartist": { "heartbeat_minutes": 29 }
  },
  "daily_summary_order": ["architect", "programmer", "designer", "narrative", "techartist"]
}
```
