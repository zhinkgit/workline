---
name: workline-review
description: "审查 Workline 阶段产物并形成阶段门禁结论。Use when the user provides a Workline active directory, prd.md, tasks.csv, reviews folder, or review notes and wants to review PRD completeness, task split quality, blocking issues, stage readiness, or whether to proceed from grill to tasks or from tasks to run."
---

# Workline Review

## 目标

按用户主动要求审查 Workline 活动目录中的阶段产物，重点检查 `prd.md` 和 `tasks.csv` 是否足以进入下一阶段，并把结论沉淀到按需创建的 `reviews/`。

本 Skill 是可选阶段门禁：

- PRD 有问题时，回到 `$workline-grill` 修订。
- `tasks.csv` 有问题时，回到 `$workline-tasks` 修订。
- 审查通过后，才推荐进入下一阶段。

## 入口检查

用户必须提供活动目录、`prd.md` 或 `tasks.csv` 路径。

定位活动目录后确认：

- `brief.md` 存在。
- `references/` 存在。
- 审查 PRD 时，`prd.md` 存在。
- 审查任务时，`prd.md` 和 `tasks.csv` 都存在。
- `reviews/` 不存在时创建；已有审查记录保留。

## 审查目标选择

根据用户意图选择一个目标：

| 目标 | 触发场景 | 输出文件 |
| --- | --- | --- |
| `prd` | `prd.md` 生成后、进入 `$workline-tasks` 前、或用户要求审查需求 | `reviews/prd-review-YYYY-MM-DD-HHMM.md` |
| `tasks` | `tasks.csv` 生成后、进入 `/goal` 前、或用户要求审查任务拆分 | `reviews/tasks-review-YYYY-MM-DD-HHMM.md` |

## PRD 审查

读取：

- `brief.md`
- `prd.md`
- `references/` 一级目录和必要文件
- 已有 `reviews/prd-review-*.md` 或用户指定的审查意见

检查：

- 目标、非目标和范围边界是否明确。
- 术语、输入输出、用户流程是否足以指导实现。
- 功能要求是否可执行，是否存在隐含需求或冲突。
- 验收标准是否可验证，是否能映射到后续任务。
- 风险与待确认问题是否还有阻塞任务拆分的内容。
- 关键决策是否有来源，是否能追溯到 `brief.md`、`references/` 或澄清记录。

结论：

- `PASS`：可进入 `$workline-tasks`。
- `REVISE`：需要回到 `$workline-grill` 修订，但不需要重新初始化。
- `BLOCKED`：缺少关键材料或关键决策，任务拆分暂缓。

## Tasks 审查

读取：

- `prd.md`
- `tasks.csv`
- `references/` 一级目录和必要文件
- 已有 `reviews/tasks-review-*.md` 或用户指定的审查意见

先运行 CSV 校验；优先使用当前仓库中的脚本：

```bash
python workline-tasks/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

如果需要快速查看 `tasks.csv` 中是否已有非初始状态，可以额外运行：

```bash
python workline-tasks/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
```

`summary` 只是可选状态快照，不自动决定阶段结论。Tasks 审查主要结合 PRD 和 `tasks.csv` 判断是否存在阻塞问题、需要修订的问题或可选建议。

检查：

- CSV 表头、转义、依赖关系和状态枚举是否有效。
- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 `prd.md` 的功能要求或验收标准。
- 是否遗漏 PRD 中的功能要求、非功能要求、迁移要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode=AFK/HITL` 是否合理，人工输入、实机操作、账号权限是否被标为 HITL。
- `REVIEW` 行是否最后一行，并依赖所有非 `REVIEW` 任务。
- `verification` 是否是真实可执行的验证命令或人工检查。
- `notes` 是否只记录任务定义阶段需要说明的短备注，不预填执行结论。
- 任务是否保持执行前初始状态；若已有非初始状态，需要确认用户是在审查历史任务表还是准备重新执行。

结论：

- `PASS`：可进入 `/goal 根据 $workline-run 规范 执行 ...`。
- `REVISE`：需要回到 `$workline-tasks` 修订 `tasks.csv`。
- `BLOCKED`：PRD 或任务定义存在阻塞问题，执行暂缓。

## 报告生成

使用 `templates/review.md` 生成审查报告，写入 `reviews/`：

- PRD 审查：`reviews/prd-review-YYYY-MM-DD-HHMM.md`
- Tasks 审查：`reviews/tasks-review-YYYY-MM-DD-HHMM.md`

## 硬约束

- 审查只形成阶段结论和修订建议。
- 审查报告只保留关键问题、判断和建议。

## 输出

完成时说明：

- 审查报告路径。
- 阶段结论。
- 阻塞问题数量和最关键的修订点。
- 推荐下一步使用 `$workline-grill`、`$workline-tasks` 或 `$workline-run`。

