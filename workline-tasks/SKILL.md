---
name: workline-tasks
description: "根据 Workline PRD 生成或修订可执行 tasks.csv。Use when the user provides a Workline active directory or prd.md and wants to split confirmed requirements into small verifiable tasks, create tasks.csv with dependencies and REVIEW, revise tasks.csv after Workline review, or validate the generated CSV before /goal execution. Do not use for code implementation or PRD review."
---

# Workline Tasks

## 目标

只读取 `prd.md`，把已确认需求拆成可实现、可验证、可恢复执行的小任务，并生成 `tasks.csv`。

## 入口检查

开始前确认：

- `prd.md` 存在。
- 关键问题已确认。
- 非阻塞待确认问题已说明为什么不阻塞任务拆分。
- 如果 `reviews/prd-review-*.md` 存在且最新结论是 `REVISE` 或 `BLOCKED`，先要求回到 `$workline-grill` 修订 PRD。
- 如果用户要求按任务审查意见修订，读取相关 `reviews/tasks-review-*.md` 或外部审查文件。

如果 PRD 不满足以上条件，停止并指出缺口；不要把未确认问题伪装成任务。

## 任务拆分规则

- `prd.md` 是唯一需求源；审查报告只能作为质量反馈，不能引入 PRD 之外的新需求。
- 每条任务都应能单独实现、单独验证、单独记录状态。
- 默认状态为 `dev_state=todo`、`verify_state=pending`、`git_state=pending`。
- 最后一行必须是 `REVIEW`，并依赖所有非 `REVIEW` 任务。

字段含义：

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID，如 `T001`；末行固定为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个用空格分隔 |
| `mode` | `AFK` 可自动执行；`HITL` 需要人工、实机、账号或关键确认 |
| `title` | 简短任务标题 |
| `description` | 任务范围和实现说明 |
| `acceptance_criteria` | 完成条件 |
| `verification` | 验证命令或人工检查方式 |
| `dev_state` | 开发状态：`todo`、`doing`、`done`、`blocked`、`skipped` |
| `verify_state` | 验证状态：`pending`、`passed`、`failed`、`blocked`、`skipped` |
| `git_state` | 提交状态：`pending`、`done`、`blocked` |
| `refs` | PRD、`references/...` 或 `evidence/...` 等相关引用 |
| `notes` | 阻塞、跳过、验证摘要、提交哈希等备注 |

## CSV 生成

使用 `templates/tasks.csv` 的固定表头：

```csv
id,depends_on,mode,title,description,acceptance_criteria,verification,dev_state,verify_state,git_state,refs,notes
```

写 CSV 时使用标准 CSV 转义；字段里有逗号、换行或引号时必须正确引用。

生成后运行：

```bash
python workline-tasks/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

校验失败时修正 CSV，直到通过。

## REVIEW 行

`REVIEW` 行必须：

- 是最后一行。
- `depends_on` 包含所有非 `REVIEW` 任务 ID。
- 检查 PRD 覆盖、CSV 状态、验证记录、`run.md` 验证说明、失败/跳过解释和 `git_state` 结论。
- 不补做实现任务。

## 硬约束

- 不实现代码。
- 不降低 PRD 验收标准。
- 不把待确认问题拆成看似可执行的任务。
- 不把审查报告中的新增想法直接写入任务；需要先回到 PRD 澄清。

## 输出

完成时说明：

- `tasks.csv` 路径。
- 任务数量和 `REVIEW` 依赖范围。
- CSV 校验命令和结果。
- 下一步使用 `/goal 根据 $workline-run 规范 执行 <tasks.csv>`；如果用户希望先复核任务拆分，再主动调用 `$workline-review`。

