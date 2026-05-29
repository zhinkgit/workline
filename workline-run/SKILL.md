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

1. 定位活动目录、`prd.md`、`tasks.csv` 和 `references/`。不要预创建 `evidence/`；只有任务产生需要保留的过程物时才创建。
2. 运行：

```bash
python workline-run/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py next .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
```

3. 如果 CSV 校验失败，先修复 CSV；不要开始执行任务。
4. `summary` 的 warnings 只作为复盘提醒，不阻断执行；执行前应阅读 warnings，尤其是历史任务的 `blocked/skipped/failed`、`git_state=pending` 和证据标签缺失。
5. 如果 `run.md` 不存在，创建它并记录本次执行入口、时间、PRD 路径和 CSV 路径。

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
6. 将实现、验证命令、真实输出摘要、失败原因、阻塞项、运行产物路径和证据等级追加到 `run.md`。
7. 验证通过后更新 `dev_state` 和 `verify_state`；`git_state` 必须按真实提交需求选择，不默认写成无需提交：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --dev_state done --verify_state passed --git_state pending --append-notes "verified"
```

   如果任务确实无需提交，才把 `git_state` 更新为 `not_needed`；如果已经提交，更新为 `committed`。
8. 如果任务产生 build log、截图、验证结果、配置快照、部署包或其它执行产物，把文件放入 `evidence/<task-id>-<name>/`，并通过 `--append-refs` 关联。`references/` 只放 PRD / grill 输入材料，不放执行证据。
9. 追加证据引用时，必须同时把轻量证据标签写入 `refs` 或 `notes`，例如 `[evidence:local]`、`[evidence:sim]`、`[evidence:target]`、`[evidence:real]`、`[evidence:manual]`；不要新增 CSV 字段。`run.md` 可以重复说明证据等级，但不能作为 `summary` 的机读输入。

多轮实机验证或多次尝试时，在同一个任务证据目录下按尝试分组，例如：

```text
evidence/T012-board-check/
├── attempt-01-timeout/
├── attempt-02-new-ip/
└── smoke/
```

证据等级含义：

| 标签 | 含义 |
| --- | --- |
| `[evidence:local]` | 本地测试、构建、静态检查或 dry-run |
| `[evidence:sim]` | mock、仿真、模拟协议或模拟外部依赖 |
| `[evidence:target]` | 已在目标环境或板端烟测，但未覆盖真实外设、真实服务或真实 ACK |
| `[evidence:real]` | 真实设备、真实服务、真实 ACK 或现场链路验证 |
| `[evidence:manual]` | 人工检查、截图复核、HITL 操作确认 |

如果只有 `[evidence:target]` 而没有 `[evidence:real]`，`notes`、`run.md` 和最终 REVIEW 必须明确说明“未覆盖真实设备/真实 ACK”，避免把目标环境烟测扩大表述为真实联调完成。

## 失败与阻塞

- 验证失败或初步检查失败时，不得把 `dev_state` 标为 `done`。
- 如果可以继续修复，保持或更新为 `doing`，并在 `run.md` 记录失败证据。
- 如果当前条件不足导致无法继续，更新为 `blocked`，同时把 `verify_state` 更新为 `failed` 或 `blocked`，并写明原因。
- `skipped` 只能来自用户确认或 PRD 明确允许；必须在 `notes` 和 `run.md` 记录依据。
- 不吞错、不删除测试、不绕过校验、不降低验收标准。
- 发现任务定义有缺陷时，记录缺陷并请求确认；不要擅自扩大范围。

## REVIEW 行

`REVIEW` 行只在所有非 `REVIEW` 任务闭环或已确认跳过后执行。存在 `blocked` 任务时，不可执行 REVIEW。

REVIEW 需要检查：

- PRD 功能要求和验收标准是否都有任务覆盖。
- `tasks.csv` 状态是否一致。
- 每条任务是否有验证记录、`run.md` 证据说明，以及 `refs` 或 `notes` 中的机读证据路径和标签。
- `summary` warnings 是否已解释，尤其是证据标签缺失、HITL 证据不足和 `target` 未覆盖真实链路。
- 失败、阻塞、跳过是否有解释。
- `git_state` 是否已有归档前结论。

REVIEW 不能补做实现任务。发现缺口时只能记录问题、更新状态，并按需要请求用户确认。

## 恢复入口

恢复执行时先运行：

```bash
python workline-run/scripts/workline_csv.py validate <tasks.csv>
python workline-run/scripts/workline_csv.py next <tasks.csv>
python workline-run/scripts/workline_csv.py summary <tasks.csv>
```

继续处理返回的第一条 `todo` 或 `doing` 任务。`tasks.csv` 始终是计划和状态源，人类审阅也直接审阅 `tasks.csv`。

## 硬约束

- 不重新解释目标、功能要求或验收标准。
- 不把 `run.md` 或聊天记录当作任务状态源。
- 不把仅写在 `run.md` 的证据标签当作已通过 `summary` 检查。
- 不手工编辑状态字段；状态变化必须通过 `workline_csv.py set`。
- 不用假数据、空跑、只读代码或“看起来可以”冒充通过。

