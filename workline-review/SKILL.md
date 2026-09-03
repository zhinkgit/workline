---
name: workline-review
description: "审查 Workline 阶段产物并写入 run.md 阶段门禁。Use when a Workline PRD or tasks.csv needs the mandatory stage review after grill or after task splitting, or when the user wants an additional independent review by another agent or model."
---

# Workline Review

## 目标

审查活动目录中的阶段产物，把 `PASS` / `REVISE` / `BLOCKED` 写入 `run.md` 的「阶段门禁」表。

本 Skill 有两种用法，不要混成一种：

1. **阶段必审**（默认）。`$workline-grill` 写出 `prd.md` 之后、`$workline-tasks` 写出 `tasks.csv` 之后，当前会话必须先跑一遍本 Skill。没有对应门禁的 `PASS`，下一阶段脚本会拒绝。
2. **额外他审**（可选）。用户可以再换一个 agent 或模型，单独安装、单独调用本 Skill。后写覆盖先写。

它不需要加载 `$workline-grill` 或 `$workline-tasks` 的上下文，自带校验脚本。

- PRD 结论为 `REVISE` / `BLOCKED`：回到 `$workline-grill`。
- 任务结论为 `REVISE` / `BLOCKED`：回到 `$workline-tasks`。
- 结论为 `PASS`：才推荐进入下一阶段。

审查不产出独立报告文件。修订点直接落到被审查对象里；阶段结论只写 `run.md` 的「阶段门禁」。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

校验与门禁脚本是 `<SKILL_DIR>/scripts/workline_csv.py`。

## 入口检查

用户必须提供活动目录、`prd.md` 或 `tasks.csv` 路径。

定位活动目录后确认：

- `brief.md`、`references/`、`run.md` 存在，且 `run.md` 含 `## 阶段门禁`。
- 审查 PRD 时，`prd.md` 存在。
- 审查任务时，`prd.md` 和 `tasks.csv` 都存在。

外部 AI 或人工的审查意见文件按输入材料对待，放在 `references/` 下读取。

若 `run.md` 不存在或没有「阶段门禁」表，先停止并回到 `$workline-init`；不要另建一份门禁文件继续。

## 审查目标选择

根据用户意图和当前门禁选择一个目标：

| 目标 | 触发场景 | 写入的门 |
| --- | --- | --- |
| `prd` | `prd.md` 刚生成、`$workline-tasks` 尚未开始，或用户要求再审需求 | `prd-review` |
| `tasks` | `tasks.csv` 刚生成、执行尚未开始，或用户要求再审任务拆分 | `tasks-review` |

开始前先读门禁：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates .workline/active/<slug>
```

## PRD 审查

读取 `brief.md`、`prd.md`、`references/` 一级目录和必要文件；`.workline/notes/index.md` 存在时一并读取，核对 PRD 是否与已沉淀的项目约定冲突。

检查：

- 目标、非目标和范围边界是否明确。
- 术语、输入输出、用户流程是否足以指导实现。
- 功能要求是否可执行，是否全部使用 `### FR-<序号>` 编号，编号是否连续无重复、无空占位、无前导零。
- 需要单独拆任务的非功能要求是否使用 `### NFR-<序号>`。
- 验收标准是否可验证，是否能映射到后续任务。
- 风险与待确认问题是否还有阻塞任务拆分的内容。
- 关键决策是否有来源，是否能追溯到 `brief.md`、`references/` 或澄清记录。
- 是否已完成 PRD 收敛：有没有残留的中途假设、已解决却仍挂着的待确认问题、重复陈述。
- 是否与 `.workline/notes/` 中已有的项目约定冲突且未说明理由。
- `run.md` 的 `materials` 是否为 `CONFIRMED` 或 `WAIVED`；仍是 `未确认` 则结论不得为 `PASS`。

结论：

- `PASS`：可进入 `$workline-tasks`。
- `REVISE`：回到 `$workline-grill` 修订，不重新初始化。
- `BLOCKED`：缺少关键材料或关键决策，任务拆分暂缓。

## Tasks 审查

读取 `prd.md`、`tasks.csv`、`references/` 一级目录和必要文件。

先确认 PRD 门禁已过，再校验 CSV：

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates .workline/active/<slug> --require prd-review=PASS
python <SKILL_DIR>/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

检查：

- 校验是否通过；`fr-headings-missing`、`fr-uncovered`、`nfr-uncovered`、`refs-invalid`、`refs-not-found`、`req-id-padded`、`verification-weak`、`refs-missing` 是否都已处理或有合理解释。
- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 `prd.md` 的功能要求、非功能要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode=AFK/HITL` 是否合理；`next` 会优先调度独立 AFK，HITL 仍须标对。
- `verification` 是否写清验证手段和期望结果；AFK 任务的命令必须用反引号包裹。
- `refs` 是否只含 `FR-` / `NFR-` 编号、`references/` 或 `evidence/` 路径。
- 依赖关系是否反映真实实现顺序。
- `REVIEW` 行是否最后一行且 `depends_on` 为空。
- 任务是否保持执行前初始状态；若已有非 `todo` 状态，确认用户是在审查历史任务表还是准备重新执行。

结论：

- `PASS`：可请求执行确认，通过后进入 `$workline-run`。
- `REVISE`：回到 `$workline-tasks` 修订 `tasks.csv`。
- `BLOCKED`：PRD 或任务定义存在阻塞问题，执行暂缓。

## 结论落地

修订点仍写回被审查对象：

- 审查 PRD：把需要修订的点写入 `prd.md` 的“风险与待确认问题”表，把已达成的判断写入“关键决策与澄清记录”表。
- 审查任务：把需要修订的点写入相应任务行的 `notes`，或直接修正任务定义。

阶段结论必须用脚本写入，禁止只在对话里说 `PASS`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate prd-review --status PASS --actor same-session --notes "关键缺口已闭环"
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate tasks-review --status PASS --actor same-session
```

脚本会强制门禁顺序：`prd-review=PASS` 前必须已确认或豁免材料，`tasks-review=PASS` 前必须有当前有效的 PRD PASS。非初始状态必须填 `--actor`。

PRD PASS 会保存 `prd.md` 的 SHA-256，任务 PASS 会保存规范化任务计划摘要。后续文件发生实质变化时，`require-gates` 会拒绝旧结论。需求未覆盖、非法/缺失 refs 和前导零编号会直接阻止任务 PASS。

`--actor` 区分审查方：`same-session` 表示当前会话的必审；换模型或换 agent 再审时用 `external-agent` 或具体模型名。

`prd-review` 写成 `PASS` 时，脚本默认会把 `tasks-review` 和 `execute` 重置为未完成。这是故意的：PRD 有实质修订后再通过，旧任务表不能继续当作已审。PRD 被写成 `REVISE` / `BLOCKED` 也会重置下游。

若这是任务表已经审查过之后的 **PRD 加审**，且本次没有改 PRD 正文，才加 `--keep-downstream`，避免无意义地作废任务审查。脚本会核对已有摘要，PRD 已改时该开关也会失败。第一次 PRD 必审不要加这个开关。

任务审查为 `PASS` 后，先请求执行确认，用户明确同意后再写：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate execute --status CONFIRMED --actor user
```

用户未确认时不要写 `CONFIRMED`，也不要启动 `$workline-run`。

## 硬约束

- 审查只形成阶段结论和修订建议，不实现任务。
- 不新增独立审查报告文件。
- 校验或门禁脚本不可用时停止并报告，禁止跳过校验直接下结论。
- 不得因为“任务表已经生成”就默认放行；`PASS` 必须逐条核对后给出。
- 不得把对话里的“看起来可以”当成门禁；下一阶段只认 `run.md` 的「阶段门禁」。

## 输出

完成时说明：

- 审查目标、这是必审还是额外他审、阶段结论。
- 阻塞问题数量和最关键的修订点。
- 校验命令输出，包括每条 warning 的判断。
- `gates-set` 写入了哪一扇门。
- 推荐下一步：`$workline-grill`、`$workline-tasks`、请求执行确认，或 `$workline-run`。
- 若用户还想换一个 agent 再审一遍，告诉他再次调用本 Skill 即可，后写覆盖先写。
