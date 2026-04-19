> 本文档归属：ARCHITECTURE.md｜原文：AGENTS_COLLAB_DESIGN_CMD.md §一
# Multi-Agent 协同工作设计方案（Mai 指令系统版）

> 本文档定义 designer / architect / programmer / narrative / techartist 五个 Agent 的心跳任务、定时任务、Skill 配置及文件存储规范。
> **指令系统版**：所有协作元数据（队列/锁/审计）通过 `mai` 命令管理，`.mai` 目录对 Agent 隐藏，Agent 不可直接读写协作文件，只调用命令。
> 版本：v3.0（命名：Mai）（2026-04-19）｜终审修复：daily-summary命令补全+心跳第6步

---

## 一、协作架构总览

```
designer（体验终裁）
    ↑ 体验验收 / 否决
architect（技术终裁）
    ↑ 技术方案审批 / 否决
    ↑ 事后否决降级 → architect-reviews-designer 队列（见 §七·P0-2）
programmer（实现）
    ↑ 发现逻辑漏洞 → @designer 重评
    ↑ 技术风险 → @architect 确认
narrative（文本一致性）
    → strings.json / 剧本 / UI 文本审查
    → 客观错误 → 快通道直接通知 programmer（见 §七·P1-4）
techartist（美术 + 性能）
    → 渲染代码审查 / 性能基准测试
    → 客观错误 → 快通道直接通知 programmer（见 §七·P1-4）
```

**三条红线：**
1. **designer 否决 = 停工** — 体验不通过，architect 不能批准技术方案
2. **architect 否决 = 停实现** — 技术不可行，programmer 不得绕过
3. **architect 事后否决（designer 通过后）** → 触发 architect-reviews-designer 队列，由 designer 重审，不直接覆盖已通过决策

**用户接触规则：**
- 用户（Sayo）不介入日常决策，只接收**终裁结论性汇报**（带 `[REPORT_TO_USER]` 标记）
- 所有 Agent 必须进行**工作记录**，通过 `mai log write` 写入，作为团队透明度的唯一来源
- **exec 权限统一由用户管理**，审批被拒时通过飞书 channel 申请
- **安全命令免审批**（见 §四·P0-3 `safe-exec-list.json`）
