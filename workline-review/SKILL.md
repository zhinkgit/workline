---
name: workline-review
description: "审查 Workline 阶段产物并写入 run.md 阶段门禁。Use when a Workline PRD or tasks.csv needs the mandatory stage review after grill or after task splitting, or when the user wants an additional independent review by another agent or model."
disable-model-invocation: true
---

# Workline Review

审查活动目录中的阶段产物，把 `PASS` / `REVISE` / `BLOCKED` 写入 `run.md` 的「阶段门禁」表。只由用户显式调用。

**开始前先读 `<SKILL_DIR>/REFERENCE.md`**：脚本拒绝时说不出来的那几条（`mode` 判定权、`verification` 可判定性、`refs` 的两条语义、`skipped` 的调度影响）在那里。结构、状态迁移、门禁顺序、`refs` 合法形式、阻断项这些，直接按脚本的错误消息改，消息里带着完整的正确答案。本会话已经读过就不必重复读。

两种用法，不要混成一种：

1. **阶段必审**（默认）。`$workline-grill` 写出 `prd.md` 之后、`$workline-tasks` 写出 `tasks.csv` 之后，当前会话必须先跑一遍。没有对应门禁的 `PASS`，下一阶段脚本会拒绝。
2. **额外他审**（可选）。用户可以再换一个 agent 或模型，单独安装、单独调用。后写覆盖先写。

本 Skill 不需要加载 `$workline-grill` 或 `$workline-tasks` 的上下文，自带校验脚本。审查不产出独立报告文件：修订点直接落到被审查对象里，阶段结论只写「阶段门禁」。

## 入口检查

用户必须提供活动目录、`prd.md` 或 `tasks.csv` 路径。定位活动目录后确认 `brief.md`、`references/`、`run.md` 存在且 `run.md` 含 `## 阶段门禁`；审查 PRD 需要 `prd.md`，审查任务需要 `prd.md` 和 `tasks.csv`。

`run.md` 或门禁表缺失时停止并回到 `$workline-init`，不要另建一份门禁文件继续。外部 AI 或人工的审查意见文件按输入材料对待，放在 `references/` 下读取。

先读门禁再选目标：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates .workline/active/<slug>
```

| 目标 | 触发场景 | 写入的门 |
| --- | --- | --- |
| `prd` | `prd.md` 刚生成、`$workline-tasks` 尚未开始，或用户要求再审需求 | `prd-review` |
| `tasks` | `tasks.csv` 刚生成、执行尚未开始，或用户要求再审任务拆分 | `tasks-review` |

## PRD 审查

读取 `brief.md`、`prd.md`、`references/` 一级目录和必要文件；材料清单里登记的仓库内相对路径或外部绝对路径按需读取；`.workline/notes/index.md` 存在时一并读取。

- 目标、非目标和范围边界是否明确。
- 术语、输入输出、用户流程是否足以指导实现。
- 功能要求是否可执行，是否全部使用 `### FR-<序号>` 编号，编号是否连续无重复、无空占位、无前导零。需要单独拆任务的非功能要求是否用 `### NFR-<序号>`。
- 验收标准是否可验证，是否能映射到后续任务。
- 「风险与待确认问题」是否还有阻塞任务拆分的内容。
- 关键决策是否有来源，能否追溯到材料或澄清记录。外部绝对路径的材料不进 `refs`，其结论必须已固化进 `prd.md`。
- `brief.md` 材料表里由 grill 追加的候选行是否已被用户确认；仍标 `agent 建议` 而 `materials` 已 `CONFIRMED`，说明确认流程被跳过。
- 是否已完成 PRD 收敛：有没有残留的中途假设、已解决却仍挂着的待确认问题、重复陈述。
- 是否与 `.workline/notes/` 已有的项目约定冲突且未说明理由。
- `materials` 是否为 `CONFIRMED` 或 `WAIVED`；仍是 `未确认` 则结论不得为 `PASS`。

结论：`PASS` 可进入 `$workline-tasks`；`REVISE` 回到 `$workline-grill` 修订，不重新初始化；`BLOCKED` 缺关键材料或关键决策，任务拆分暂缓。

## Tasks 审查

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates .workline/active/<slug> --require prd-review=PASS
python <SKILL_DIR>/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

- 每条 warning 是否已处理或有合理解释。`[阻断]` 的不必你把关：没清掉时 `gates-set tasks-review=PASS` 会直接拒绝并列出来；你要判断的是 `[提示]` 那几条的结论是否成立。
- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 PRD 的功能要求、非功能要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode` 是否按判定权标对，而不是按工具形态。
- `verification` 是否写清手段和期望结果；AFK 的判定必须在无人值守下可完成，写「验证一下」则 `REVISE`。
- `refs` 是否合法；涉及的领域有 `.workline/notes/` 主题文件时是否引用了它。
- 依赖关系是否反映真实实现顺序，`REVIEW` 是否最后一行且 `depends_on` 为空。
- 任务是否保持执行前初始状态；已有非 `todo` 状态时确认用户是在审查历史任务表还是准备重新执行。

结论：`PASS` 可请求执行确认；`REVISE` 回到 `$workline-tasks`；`BLOCKED` 执行暂缓。

## 结论落地

修订点写回被审查对象：审 PRD 时写入「风险与待确认问题」和「关键决策与澄清记录」两张表；审任务时写入相应任务行的 `notes`，或直接修正任务定义。

阶段结论必须用脚本写入，禁止只在对话里说 `PASS`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate prd-review --status PASS --actor same-session --notes "关键缺口已闭环"
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate tasks-review --status PASS --actor same-session
```

`--actor` 区分审查方：`same-session` 是当前会话的必审，换模型或换 agent 再审用 `external-agent` 或具体模型名。

`prd-review` 写成 `PASS` / `REVISE` / `BLOCKED` 都会把 `tasks-review` 和 `execute` 重置为未完成。这是故意的：PRD 有实质修订后再通过，旧任务表不能继续当作已审。只有在**任务表已审之后的 PRD 加审、且本次没改 PRD 正文**时才加 `--keep-downstream`；脚本会核对摘要，PRD 已改时该开关也会失败。第一次 PRD 必审不要加。

任务审查 `PASS` 后先请求执行确认，用户明确同意再写：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set .workline/active/<slug> --gate execute --status CONFIRMED --actor user
```

用户未确认时不要写 `CONFIRMED`，也不要启动 `$workline-run`。

## 硬约束

- 只形成阶段结论和修订建议，不实现任务，不新增独立审查报告文件。
- 不得因为「任务表已经生成」就默认放行；`PASS` 必须逐条核对后给出。
- 不得把对话里的「看起来可以」当成门禁；下一阶段只认「阶段门禁」表。

## 输出

- 审查目标、这是必审还是额外他审、阶段结论。
- 阻塞问题数量和最关键的修订点。
- 校验命令输出，包括每条 warning 的判断。
- `gates-set` 写入了哪一扇门。
- 推荐下一步：`$workline-grill`、`$workline-tasks`、请求执行确认，或 `$workline-run`。
- 若用户还想换一个 agent 再审一遍，告诉他再次调用本 Skill 即可，后写覆盖先写。
