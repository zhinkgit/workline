---
name: workline-grill
description: "Workline 需求澄清与 PRD 生成。Use when the user provides a Workline active directory, answers an in-progress Workline Grill clarification question, wants grill-style one-question-at-a-time clarification, wants to turn brief.md and references into prd.md, or wants to revise prd.md after Workline review before task splitting."
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

如果缺少活动目录路径，先要求用户提供路径。

## 证据规则

能靠查证解决的，一律不要问用户。

- 仓库、`brief.md`、`references/` 能回答的事实问题，自己查证后直接写进 `prd.md`，并在“关键决策与澄清记录”的“来源”列写清依据。
- 只问仓库永远回答不了的：产品意图、范围边界、优先级、风险容忍度、期望的验收行为、以及查证后仍然含混的判断。
- 仓库里已存在某种做法，只是**候选方案和推荐依据，不等于决策**。不得用“现有代码就是这么写的”替代用户确认，尤其在涉及接口、数据格式、删除行为和兼容性时。

## 工作流

1. 读取 `brief.md`，不修改 `brief.md`；读取 `references/` 的内容。
2. 如果用户要求按审查意见修订 PRD，读取 `prd.md` 中“关键决策与澄清记录”“风险与待确认问题”两张表里已登记的审查结论，以及 `references/` 中的外部审查意见文件。
3. 先按证据规则自行查证，再把需要用户确认的判断拿出来问。
4. 使用 `templates/prd.md` 在活动目录下创建或更新草稿态 `prd.md`；将模板中的 `{{title}}` 替换为活动目录名；第一版 `prd.md` 只是工作底稿，不代表澄清完成。
5. 在内部形成待澄清问题队列，像 `grill-me` 一样沿决策树逐个分支推进：每次只问一个关键问题，等待用户回答后继续下一个问题。
6. 问题编号为“问题 1 / 问题 2 / ...”；每个问题按选择题的方式给出多个选项（可多选），每个选项给出简短解释，并且给出推荐选项。并说明“你回答后我继续追问下一个边界点”。
7. 每次收到回答后，先更新 `prd.md` 的相关章节和“关键决策与澄清记录”，再继续提出下一个尚未闭环的问题。
8. 持续推进问题队列，直到满足“PRD 完成条件”。
9. 收尾前执行一次 PRD 收敛。

## 用户选择工具

- 当运行环境提供 `AskUserQuestion`、`request_user_input` 或同类选择式提问工具时，积极优先调用，用于所有需要用户确认、选择、定边界或补充判断的关键问题。

## PRD 收敛

边问边写的 `prd.md` 会变成流水账，混着已被推翻的假设和已解决的疑问，下一个会话读到会被误导。宣布澄清完成前，把 `prd.md` 整体重写一遍，要求无损：

- 把重复陈述合并到唯一的权威位置。
- 把已解决的待确认问题从“风险与待确认问题”表中删除，结论并入相应章节。
- 删除中途假设、临时理解和已被推翻的方案，保留它们在“关键决策与澄清记录”中的结论行。
- 保留每一条决策、约束、功能要求和验收标准，以及它们的来源引用。
- 无明确用户流程的任务（重构、配置、工具链改造）可删除“典型流程”整节。

## PRD 完成条件

进入 `$workline-tasks` 前，`prd.md` 必须满足：

- 目标明确。
- 非目标明确。
- 功能要求可执行。
- 验收标准可验证。
- 关键决策有来源。
- “风险与待确认问题”不存在阻塞任务拆分的未闭环问题。
- 已完成一次 PRD 收敛。

## 硬约束

- PRD 只保留关键问答和决策。

## 输出

完成时说明：

- `prd.md` 路径。
- 已闭环的关键决策。
- 仍存在但不阻塞任务拆分的风险或待确认问题。
- 下一步使用 `$workline-tasks` 拆分任务；如果用户希望先复核 PRD，再主动调用 `$workline-review`。
