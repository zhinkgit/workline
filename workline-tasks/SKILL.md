---
name: workline-tasks
description: "根据 Workline PRD 生成或修订可执行 tasks.csv。Use when the user provides a Workline active directory or prd.md and wants to split confirmed requirements into small verifiable tasks, create tasks.csv with dependencies and REVIEW, revise tasks.csv after Workline review, or validate the generated CSV before /goal execution."
---

# Workline Tasks

## 目标

读取 `prd.md`，把已确认需求拆成可实现、可验证、可恢复执行的小任务，并生成 `tasks.csv`。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

## 入口检查

开始前确认：

- `prd.md` 存在。
- 关键问题已确认。
- 非阻塞待确认问题已说明为什么不阻塞任务拆分。
- 如果 `prd.md` 的“风险与待确认问题”表中还有标记为阻塞任务拆分的问题，先要求回到 `$workline-grill` 修订 PRD。

如果 PRD 不满足以上条件，停止并指出缺口。

## 任务拆分规则

- `prd.md` 是需求源；审查意见作为质量反馈。
- 每条任务都应能单独实现、单独验证、单独记录状态。
- 默认状态为 `state=todo`，`commit` 留空。
- 最后一行必须是 `REVIEW`，且它的 `depends_on` 必须留空。

字段含义：

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID，如 `T001`；末行固定为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个用空格分隔；普通任务不得依赖 `REVIEW`，`REVIEW` 行留空 |
| `mode` | `AFK` 可自动执行；`HITL` 需要人工、实机、账号或关键确认 |
| `title` | 简短任务标题 |
| `description` | 任务范围和实现说明；验证命令覆盖不到的完成标准也写这里 |
| `verification` | 验证手段 + 期望结果，优先真实可执行命令；无法自动验证时写人工检查方式和判定标准 |
| `state` | `todo`、`doing`、`done`、`failed`、`blocked`、`skipped` |
| `commit` | 7–64 位十六进制提交哈希 / `no-change` / 留空 |
| `refs` | PRD 章节、`references/...` 或 `evidence/...` 等相关引用 |
| `notes` | 阻塞、跳过等短备注 |

`state` 语义：

| 值 | 含义 | 满足后继依赖 |
| --- | --- | --- |
| `todo` | 未开始 | 否 |
| `doing` | 进行中，含验证失败后正在修 | 否 |
| `done` | 实现完成**且**验证通过，唯一成功终态 | 是 |
| `failed` | 验证已执行且未通过，当前暂停 | 否 |
| `blocked` | 条件不足无法继续 | 否 |
| `skipped` | 经用户确认或 PRD 允许跳过 | 是 |

## CSV 生成

使用 `templates/tasks.csv` 的固定表头：

```csv
id,depends_on,mode,title,description,verification,state,commit,refs,notes
```

写 CSV 时使用标准 CSV 转义；字段里有逗号、换行或引号时必须正确引用。

生成后运行：

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

校验失败时修正 CSV，直到通过。校验器检查 `commit` 格式和依赖关系等结构约束；`state=done` 缺 `commit` 之类的问题以 warning 形式输出，不影响退出码。

## REVIEW 行

`REVIEW` 行必须：

- 是最后一行。
- `depends_on` 留空；它隐式依赖全部任务，中途新增任务不需要回来修改这一行。
- 由执行阶段负责最终审计，不承担实现工作。

## 硬约束

- PRD 验收标准保持原样。
- 待确认问题先回到 PRD 澄清。
- 审查意见中的新增想法先进入 PRD。
- 校验脚本不可用时停止并报告，禁止跳过校验直接交付 CSV。

## 输出

完成时说明：

- `tasks.csv` 路径。
- 任务数量。
- CSV 校验命令和结果，包括 warning。
- 下一步使用 `/goal 根据 $workline-run 规范 执行 <tasks.csv>`；如果用户希望先复核任务拆分，再主动调用 `$workline-review`。
