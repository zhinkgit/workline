---
name: workline-run
description: "Workline 的 /goal 长任务执行规则包。Use when the user invokes /goal with a Workline active directory or tasks.csv, needs execution to follow tasks.csv state and dependencies, update task states with workline_csv.py, write run.md evidence, resume a long task, or execute the final REVIEW row. This skill is not a scheduler and does not replace /goal."
---

# Workline Run

## 定位

本 Skill 是 `/goal` 的执行规则包，不是独立执行器。它规定 `/goal` 在执行 Workline 任务时如何读取状态、选择下一任务、更新 `tasks.csv`、记录 `run.md`、处理失败和恢复。

用户主动调用时必须提供活动目录或 `tasks.csv` 路径；不要猜测当前 active 任务。

推荐调用：

```text
/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv
```

## 执行前检查

1. 定位活动目录、`prd.md`、`tasks.csv`、`references/`。
2. 运行：

```bash
python workline-run/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py next .workline/active/<slug>/tasks.csv
```

3. 如果 CSV 校验失败，先修复 CSV；不要开始执行任务。
4. 如果 `run.md` 不存在，创建它并记录本次执行入口、时间、PRD 路径和 CSV 路径。

## 任务执行循环

对 `next` 返回的任务按以下顺序处理：

1. 读取任务行的 `id`、`mode`、`title`、`description`、`acceptance_criteria`、`verification`、`refs` 和 `notes`。
2. 如果 `mode=HITL` 且需要人工输入、实机操作、账号权限或关键确认，先请求用户参与；不要伪装成自动完成。
3. 执行前将任务状态更新为 `doing`：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --dev_state doing --append-notes "started"
```

4. 按 PRD 和任务验收标准真实实现。
5. 运行任务要求的验证命令或人工检查，并记录真实输出摘要。
6. 将实现、验证结果、失败原因、阻塞项、运行产物路径追加到 `run.md`。
7. 验证通过后更新：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --dev_state done --review_state passed --git_state not_needed --append-notes "verified"
```

8. 如果任务产生 build log、截图、验证结果或其它产物，把文件放入 `references/` 或 `references/<task-id>-<name>/`，并通过 `--append-refs` 关联。

## 失败与阻塞

- 验证失败或初步检查失败时，不得把 `dev_state` 标为 `done`。
- 如果可以继续修复，保持或更新为 `doing`，并在 `run.md` 记录失败证据。
- 如果当前条件不足导致无法继续，更新为 `blocked`，同时把 `review_state` 更新为 `failed` 或 `blocked`，并写明原因。
- `skipped` 只能来自用户确认或 PRD 明确允许；必须在 `notes` 和 `run.md` 记录依据。
- 不吞错、不删除测试、不绕过校验、不降低验收标准。
- 发现任务定义有缺陷时，记录缺陷并请求确认；不要擅自扩大范围。

## REVIEW 行

`REVIEW` 行只在所有非 `REVIEW` 任务闭环或已确认跳过后执行。存在 `blocked` 任务时，不可执行 REVIEW。

REVIEW 需要检查：

- PRD 功能要求和验收标准是否都有任务覆盖。
- `tasks.csv` 状态是否一致。
- 每条任务是否有验证记录和 `run.md` 证据。
- 失败、阻塞、跳过是否有解释。
- `git_state` 是否已有归档前结论。

REVIEW 不能补做实现任务。发现缺口时只能记录问题、更新状态，并按需要请求用户确认。

## 恢复入口

恢复执行时先运行：

```bash
python workline-run/scripts/workline_csv.py validate <tasks.csv>
python workline-run/scripts/workline_csv.py next <tasks.csv>
```

继续处理返回的第一条 `todo` 或 `doing` 任务。`tasks.csv` 始终是计划和状态源，人类审阅也直接审阅 `tasks.csv`。

## 硬约束

- 不重新解释目标、功能要求或验收标准。
- 不把 `run.md` 或聊天记录当作任务状态源。
- 不手工编辑状态字段；状态变化必须通过 `workline_csv.py set`。
- 不用假数据、空跑、只读代码或“看起来可以”冒充通过。
