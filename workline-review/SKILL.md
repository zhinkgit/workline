---
name: workline-review
description: "审查 Workline 阶段产物并形成阶段门禁结论。Use when the user provides a Workline active directory, prd.md, tasks.csv, reviews folder, or review notes and wants to review PRD completeness, task split quality, blocking issues, stage readiness, or whether to proceed from grill to tasks or from tasks to run. Do not implement code or silently rewrite requirements."
---

# Workline Review

## 目标

审查 Workline 活动目录中的阶段产物，重点检查 `prd.md` 和 `tasks.csv` 是否足以进入下一阶段，并把结论沉淀到 `reviews/`。

本 Skill 是阶段门禁，不替代 `$workline-grill`、`$workline-tasks` 或 `$workline-run`：

- PRD 有问题时，回到 `$workline-grill` 修订。
- `tasks.csv` 有问题时，回到 `$workline-tasks` 修订。
- 审查通过后，才推荐进入下一阶段。

## 入口检查

用户必须提供活动目录、`prd.md` 或 `tasks.csv` 路径；不要猜测当前 active 任务。

定位活动目录后确认：

- `brief.md` 存在。
- `references/` 存在。
- `evidence/` 不要求预先存在；执行阶段已有证据时再检查。
- 审查 PRD 时，`prd.md` 存在。
- 审查任务时，`prd.md` 和 `tasks.csv` 都存在。
- `reviews/` 不存在时创建；不要覆盖已有审查记录。

## 审查目标选择

根据用户意图选择一个目标：

| 目标 | 触发场景 | 输出文件 |
| --- | --- | --- |
| `prd` | `prd.md` 生成后、进入 `$workline-tasks` 前、或用户要求审查需求 | `reviews/prd-review-YYYY-MM-DD-HHMM.md` |
| `tasks` | `tasks.csv` 生成后、进入 `/goal` 前、或用户要求审查任务拆分 | `reviews/tasks-review-YYYY-MM-DD-HHMM.md` |

如果用户没有明确目标：

- 只有 `prd.md` 没有 `tasks.csv` 时，审查 `prd`。
- 已有 `tasks.csv` 时，审查 `tasks`。
- 用户粘贴或引用审查意见时，按被审查对象归入 `prd` 或 `tasks`；无法判断时先要求用户说明。

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
- `BLOCKED`：缺少关键材料或关键决策，不能继续拆任务。

## Tasks 审查

读取：

- `prd.md`
- `tasks.csv`
- `references/` 一级目录和必要输入材料
- 已存在的 `evidence/` 任务证据目录
- 已有 `reviews/tasks-review-*.md` 或用户指定的审查意见

先运行 CSV 校验；优先使用当前仓库中的脚本：

```bash
python workline-tasks/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-tasks/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
```

`summary` warnings 是提醒型复盘结果，不自动决定阶段结论。审查者需要结合 PRD、`run.md`、`evidence/` 和上下文判断这些 warning 是阻塞问题、需要修订的问题、可选建议，还是已有合理解释。

检查：

- CSV 表头、转义、依赖关系和状态枚举是否有效。
- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 `prd.md` 的功能要求或验收标准。
- 是否遗漏 PRD 中的功能要求、非功能要求、迁移要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode=AFK/HITL` 是否合理，人工输入、实机操作、账号权限是否被标为 HITL。
- `REVIEW` 行是否最后一行，并依赖所有非 `REVIEW` 任务。
- `verification` 是否是真实可执行的验证命令或人工检查，不是空泛描述。
- 已执行任务的验证产物是否优先落在 `evidence/<task-id>-<name>/`，而不是混入 `references/`。
- 已执行任务是否在 `refs`、`notes` 或 `run.md` 中标明证据等级，例如 `[evidence:local-test]`、`[evidence:mock-mqtt]`、`[evidence:board-smoke]`、`[evidence:real-device]`、`[evidence:manual-review]`。
- `mode=HITL` 的任务是否具备人工、板端或真实设备证据；只有 `[evidence:board-smoke]` 时，是否明确说明未覆盖真实设备或真实 ACK。
- `summary` 输出的 `git-pending`、`skipped-or-blocked`、缺证据路径、缺证据等级等 warnings 是否已有解释或需要修订。

结论：

- `PASS`：可进入 `/goal 根据 $workline-run 规范 执行 ...`。
- `REVISE`：需要回到 `$workline-tasks` 修订 `tasks.csv`。
- `BLOCKED`：PRD 或任务定义存在阻塞问题，不能执行。

## 已有审查意见处理

当用户提供其它 AI 或人工审查意见时：

1. 读取被审查对象和审查意见。
2. 将意见分成：
   - 阻塞问题
   - 应修订问题
   - 可选建议
   - 误报或不采纳意见
3. 对每条意见给出处理建议和依据。
4. 不直接修改 `prd.md` 或 `tasks.csv`，除非用户明确要求本次同时修订。
5. 需要修订时，明确交给 `$workline-grill` 或 `$workline-tasks`。

## 审查报告格式

审查报告写入 `reviews/`，使用以下结构：

```markdown
# Workline Review

## 基本信息

- 审查目标：
- 审查时间：
- 活动目录：
- 输入文件：
- 阶段结论：PASS / REVISE / BLOCKED

## 阻塞问题

## 需要修订的问题

## 可选建议

## 覆盖检查

## Summary Warnings

- 命令：
- warning 数量：
- 采纳为阻塞：
- 采纳为需修订：
- 采纳为可选建议：
- 已解释或不采纳：

## 建议下一步
```

## 硬约束

- 不实现代码。
- 不把审查报告当作新的需求源；`prd.md` 仍是任务拆分的需求源。
- 不降低 `prd.md` 的验收标准。
- 不把缺少证据的判断写成已确认事实。
- 不覆盖已有 review 文件；同一分钟重名时追加短后缀。
- 不把完整聊天流水写入审查报告，只保留关键问题、判断和建议。

## 输出

完成时说明：

- 审查报告路径。
- 阶段结论。
- 阻塞问题数量和最关键的修订点。
- 推荐下一步使用 `$workline-grill`、`$workline-tasks` 或 `$workline-run`。
