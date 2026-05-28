---
name: workline-grill
description: "Workline 需求澄清与 PRD 生成。Use when the user provides a Workline active directory and wants grill-style one-question-at-a-time clarification, wants to turn brief.md and references into prd.md, or wants a concise PRD before task splitting. Do not use for tasks.csv generation or implementation."
---

# Workline Grill

## 目标

读取活动目录中的 `brief.md` 和 `references/`，通过逐问逐答澄清需求，生成简洁但可执行的 `prd.md`。

## 入口检查

要求用户明确提供活动目录路径，例如：

```text
.workline/active/2026-05-28-0915-example/
```

开始前确认：

- `brief.md` 存在。
- `references/` 存在。
- 用户已补充必要材料，或明确允许材料不足时开始澄清。

如果缺少活动目录路径，先要求用户提供路径；不要猜测当前 active 任务。

## 工作流

1. 读取 `brief.md`，保留其中原始需求；只追加补充整理，不覆盖原始需求。
2. 扫描 `references/` 的一级内容，优先自行查证能从仓库或参考资料判断的问题。
3. 使用 `templates/prd.md` 作为 `prd.md` 模板。
4. 每次只问一个关键问题。
5. 每个问题都给出推荐答案或推荐取舍，不只把问题抛回用户。
6. 将影响需求、边界、验收或取舍的结论写入 `prd.md` 的“关键决策与澄清记录”。
7. 将输入资料写入 `prd.md` 末尾“参考资料记录”，记录路径、类型、来源/创建方式、用途和是否归档。

## PRD 完成条件

进入 `$workline-tasks` 前，`prd.md` 必须满足：

- 目标明确。
- 非目标明确。
- 功能要求可执行。
- 验收标准可验证。
- 关键决策有来源。
- “风险与待确认问题”不存在阻塞任务拆分的未闭环问题。
- “参考资料记录”覆盖每个进入澄清和任务拆分阶段的输入资料。

## 硬约束

- 不生成 `tasks.csv`。
- 不执行代码。
- 不调用 OpenSpec、Trellis、Mission、`to-prd`、`to-issues` 或其它规划工作流。
- 不单独生成 `grill.md`。
- 不把完整聊天流水写入 PRD；只保留关键问答和决策。
- 不引入 `CONTEXT.md`、ADR 或其它外部文档体系。

## 输出

完成时说明：

- `prd.md` 路径。
- 已闭环的关键决策。
- 仍存在但不阻塞任务拆分的风险或待确认问题。
- 下一步使用 `$workline-tasks`。
