---
name: workline-review
description: "审查 Workline 阶段产物并形成阶段门禁结论。Use when the user provides a Workline active directory, prd.md, tasks.csv, reviews folder, or review notes and wants to review PRD completeness, task split quality, blocking issues, stage readiness, or whether to proceed from grill to tasks or from tasks to run."
---

# Workline Review

## 目标

按用户主动要求审查 Workline 活动目录中的阶段产物，重点检查 `prd.md` 和 `tasks.csv` 是否足以进入下一阶段。

本 Skill 是可选阶段门禁：

- PRD 有问题时，回到 `$workline-grill` 修订。
- `tasks.csv` 有问题时，回到 `$workline-tasks` 修订。
- 审查通过后，才推荐进入下一阶段。

审查不产出独立报告文件。结论直接落到被审查对象里，避免出现改完就过期的第二份文档。

## 路径约定

`<CSV_SCRIPT>` 指 `workline-tasks` 或 `workline-run` skill 目录下的 `scripts/workline_csv.py`，两份实现等价，任选其一。运行环境未提供 skill 目录变量时，先定位实际路径再替换。所有命令都在项目根目录下执行。

## 入口检查

用户必须提供活动目录、`prd.md` 或 `tasks.csv` 路径。

定位活动目录后确认：

- `brief.md` 存在。
- `references/` 存在。
- 审查 PRD 时，`prd.md` 存在。
- 审查任务时，`prd.md` 和 `tasks.csv` 都存在。

外部 AI 或人工的审查意见文件按输入材料对待，放在 `references/` 下读取。

## 审查目标选择

根据用户意图选择一个目标：

| 目标 | 触发场景 |
| --- | --- |
| `prd` | `prd.md` 生成后、进入 `$workline-tasks` 前、或用户要求审查需求 |
| `tasks` | `tasks.csv` 生成后、进入 `/goal` 前、或用户要求审查任务拆分 |

## PRD 审查

读取 `brief.md`、`prd.md`、`references/` 一级目录和必要文件。

检查：

- 目标、非目标和范围边界是否明确。
- 术语、输入输出、用户流程是否足以指导实现。
- 功能要求是否可执行，是否存在隐含需求或冲突。
- 验收标准是否可验证，是否能映射到后续任务。
- 风险与待确认问题是否还有阻塞任务拆分的内容。
- 关键决策是否有来源，是否能追溯到 `brief.md`、`references/` 或澄清记录。
- 是否已完成 PRD 收敛：有没有残留的中途假设、已解决却仍挂着的待确认问题、重复陈述。

结论：

- `PASS`：可进入 `$workline-tasks`。
- `REVISE`：需要回到 `$workline-grill` 修订，但不需要重新初始化。
- `BLOCKED`：缺少关键材料或关键决策，任务拆分暂缓。

## Tasks 审查

读取 `prd.md`、`tasks.csv`、`references/` 一级目录和必要文件。

先运行 CSV 校验：

```bash
python <CSV_SCRIPT> validate .workline/active/<slug>/tasks.csv
```

检查：

- 校验是否通过，warnings 是否符合预期。
- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 `prd.md` 的功能要求或验收标准。
- 是否遗漏 PRD 中的功能要求、非功能要求、迁移要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode=AFK/HITL` 是否合理，人工输入、实机操作、账号权限是否被标为 HITL。
- `verification` 是否写清了验证手段**和**期望结果，是真实可执行命令或可判定的人工检查。
- `description` 是否写清了验证命令覆盖不到的完成标准。
- `REVIEW` 行是否最后一行且 `depends_on` 为空。
- 任务是否保持执行前初始状态；若已有非 `todo` 状态，需要确认用户是在审查历史任务表还是准备重新执行。

结论：

- `PASS`：可进入 `/goal 根据 $workline-run 规范 执行 ...`。
- `REVISE`：需要回到 `$workline-tasks` 修订 `tasks.csv`。
- `BLOCKED`：PRD 或任务定义存在阻塞问题，执行暂缓。

## 结论落地

- 审查 PRD：把需要修订的点写入 `prd.md` 的“风险与待确认问题”表，把已达成的判断写入“关键决策与澄清记录”表。
- 审查任务：把需要修订的点写入相应任务行的 `notes`，或直接修正任务定义。
- 阶段结论、阻塞问题数量和最关键的修订点在对话中给出。

## 硬约束

- 审查只形成阶段结论和修订建议，不实现任务。
- 不新增独立审查报告文件。
- 校验脚本不可用时停止并报告，禁止跳过校验直接下结论。

## 输出

完成时说明：

- 审查目标和阶段结论。
- 阻塞问题数量和最关键的修订点。
- 结论写到了哪些位置。
- 推荐下一步使用 `$workline-grill`、`$workline-tasks` 或 `$workline-run`。
