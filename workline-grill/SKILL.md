---
name: workline-grill
description: "Workline 需求澄清与 PRD 生成。Use when the user provides a Workline active directory, answers an in-progress Workline Grill clarification question, wants grill-style one-question-at-a-time clarification, wants to turn brief.md and references into prd.md, or wants a concise PRD before task splitting. Do not use for tasks.csv generation or implementation."
---

# Workline Grill

## 目标

对 Workline 活动目录做 `grill-me` 式需求澄清：读取 `brief.md` 和 `references/`，持续一问一答压实边界，并把关键结论沉淀到活动目录下的 `prd.md`。

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

1. 只读取 `brief.md`，不修改 `brief.md`；扫描 `references/` 的一级内容。
2. 优先自行查证能从仓库、`brief.md` 或 `references/` 判断的问题，再把需要用户确认的判断拿出来问。
3. 使用 `templates/prd.md` 在活动目录下创建或更新草稿态 `prd.md`；第一版 `prd.md` 只是工作底稿，不代表澄清完成。
4. 在内部形成待澄清问题队列，至少覆盖：目标和非目标、范围边界、术语定义、输入输出、用户流程、验收标准、风险与依赖。
5. 像 `grill-me` 一样沿决策树逐个分支推进：每次只问一个关键问题，等待用户回答后继续下一个问题。
6. 每个问题都给出推荐答案或推荐取舍；问题编号为“问题 1 / 问题 2 / ...”，并说明“你回答后我继续追问下一个边界点”。
7. 每次收到回答后，先更新 `prd.md` 的相关章节和“关键决策与澄清记录”，再继续提出下一个尚未闭环的问题。
8. 不要轻易判断“只剩一个问题”“唯一问题”“当前只有一个阻塞问题”；只有满足“PRD 完成条件”后才能最终收尾。

## 用户选择工具

- 当运行环境提供 `AskUserQuestion`、`request_user_input` 或同类选择式提问工具时，积极优先调用，用于所有需要用户确认、选择、定边界或补充判断的关键问题。

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
- 不把完整聊天流水写入 PRD；只保留关键问答和决策。

## 输出

完成时说明：

- `prd.md` 路径。
- 已闭环的关键决策。
- 仍存在但不阻塞任务拆分的风险或待确认问题。
- 下一步使用 `$workline-tasks`。
