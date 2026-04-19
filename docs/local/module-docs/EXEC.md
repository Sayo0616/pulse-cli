> 本文档归属：EXEC.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §四

## 四、exec 权限管理

### P0-3 安全命令白名单

**所有 exec 权限归用户（Sayo）所有，但无害命令免审批。**

在 `~/.openclaw/workspace/agents/shared-workspace/safe-exec-list.json` 维护白名单：

```json
{
  "safe_commands": [
    { "cmd": "npm run test",          "agent": "programmer", "risk": "none" },
    { "cmd": "pytest",                "agent": "programmer", "risk": "none" },
    { "cmd": "git status",            "agent": "*",          "risk": "none" },
    { "cmd": "git diff",              "agent": "*",          "risk": "none" },
    { "cmd": "tsc --noEmit",          "agent": "programmer", "risk": "none" },
    { "cmd": "eslint",                "agent": "programmer", "risk": "none" },
    { "cmd": "python3 -m py_compile", "agent": "programmer", "risk": "none" },
    { "cmd": "ls",                    "agent": "*",          "risk": "none" },
    { "cmd": "cat",                   "agent": "*",          "risk": "none" }
  ],
  "high_risk_patterns": [
    "rm -rf", "chmod 777", "curl.*|bash.*pipe",
    "systemctl", "mkfs", "dd if="
  ]
}
```

### P0-3 审批被拒时的处理流程

```
1. 分析评估其他方式
2. 无法通过其他方式完成任务，主动暂停执行
3. 通过飞书 IM（私聊或群聊 channel）向用户发送权限申请
4. 申请内容必须包含：
   - 执行的具体命令或操作
   - 当前上下文和目的
   - 之前的重试次数（若有）
5. 等待用户授权，不得绕过
6. 用户授权后，Agent 将授权结论追加写入
   ~/.openclaw/workspace/agents/shared-workspace/exec-auth-log.md
```

### P0-3 禁止行为

- ❌ 不得在审批被拒后切换命令写法重新尝试
- ❌ 不得将 exec 任务拆解为多个"看起来无害"的子命令绕过审批
- ❌ 不得在未经用户授权的情况下变更操作方向
- ❌ 不得修改 `safe-exec-list.json`（该文件由用户专属维护）
