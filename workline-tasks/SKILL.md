---
name: workline-tasks
description: "根据 Workline PRD 生成或修订可执行 tasks.csv。Use when the user provides a Workline active directory or prd.md and wants to split a reviewed PRD into small verifiable tasks, create tasks.csv with dependencies and REVIEW, revise tasks.csv after Workline review, or validate the generated CSV before execution."
disable-model-invocation: true
---

# Workline Tasks

## 目标

读取已通过审查的 `prd.md`，把需求拆成可实现、可验证、可恢复执行的小任务，并生成 `tasks.csv`。

本 Skill 只由用户显式调用（`/workline-tasks` 或 `$workline-tasks`）。

**开始前先读 `<SKILL_DIR>/REFERENCE.md`**：脚本拒绝时说不出来的那几条（`mode` 判定权、`verification` 可判定性、`refs` 的两条语义、`skipped` 的调度影响）在那里。结构、状态迁移、门禁顺序、`refs` 合法形式、阻断项这些，直接按脚本的错误消息改，消息里带着完整的正确答案。本会话已经读过就不必重复读。

## 入口检查

开始前先跑门禁，失败即停止，回到 `$workline-grill` 或 `$workline-review`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates .workline/active/<slug> --require materials=CONFIRMED,WAIVED --require prd-review=PASS
```

然后确认：

- `prd.md` 存在。
- 功能要求已使用 `### FR-<序号>` 编号，没有 `fr-headings-missing`。
- 非阻塞待确认问题已说明为什么不阻塞任务拆分。
- 如果 `prd.md` 的「风险与待确认问题」表中还有标记为阻塞任务拆分的问题，先要求回到 `$workline-grill` 修订 PRD。

如果 PRD 不满足以上条件，停止并指出缺口。

## tasks.csv 十列

`id`（`T` 加至少三位数字，末行固定 `REVIEW`）、`depends_on`（空格分隔的任务 ID，普通任务不得依赖 `REVIEW`，`REVIEW` 行留空）、`mode`、`title`、`description`（范围和实现说明，验证覆盖不到的完成标准也写这里）、`verification`、`state`、`commit`（7–64 位十六进制哈希 / `no-change` / 留空）、`refs`、`notes`。

前 6 列是计划，审查通过后不要改；后 4 列是执行状态。中途加任务用脚本的 `add`，不要手改表头。

## 任务拆分规则

- `prd.md` 是需求源；审查意见作为质量反馈。
- 每条任务都应能单独实现、单独验证、单独记录状态。
- 每条 PRD 功能要求至少被一条任务的 `refs` 引用；有 `### NFR-<序号>` 的非功能要求同样必须被引用。
- 任务涉及的领域在 `.workline/notes/` 有对应主题文件时，把该文件路径写进 `refs`——执行阶段不会自己去翻 notes。
- 默认状态为 `state=todo`，`commit` 留空。
- 最后一行必须是 `REVIEW`，且它的 `depends_on` 必须留空。

## CSV 生成

使用 `templates/tasks.csv` 的固定表头。写 CSV 时使用标准 CSV 转义。执行中途新增任务不要手改 CSV，用：

```bash
python <SKILL_DIR>/scripts/workline_csv.py add .workline/active/<slug>/tasks.csv T012 --mode AFK --title "补校验" --description "..." --verification "pytest tests/test_import.py 退出码 0" --refs "FR-2"
```

生成后运行：

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
```

结构错误、`done` 任务收口不完整会以退出码 1 失败。生成阶段应没有 `done` 任务。

输出的每条 warning 都要处理后再交付。`[阻断]` 的必须真正改掉，否则 `$workline-review` 放行时脚本会拒绝；`[提示]` 的要给出判断结论。`fr-headings-missing` 是 PRD 编号缺失，回到 `$workline-grill`。

## REVIEW 行

`REVIEW` 行必须是最后一行，`depends_on` 留空；它隐式依赖全部任务。由执行阶段负责最终审计，不承担实现工作。

`REVIEW` 行的 refs 不计入 FR/NFR 覆盖，防止用最终审计行代替真正的实现任务。

## 交付前自检

交付 `tasks.csv` 前逐条核对，把结论写进输出。核对范围与 `$workline-review` 的任务审查清单相同：任务是否足够小、能否追溯到 PRD、AFK/HITL 是否按判定权标对、验证是否写清手段和期望结果、refs 是否合法、依赖是否真实。不要因为没有反引号就把 AFK 改成 HITL。

本 Skill 做完自检仍不能进入执行。下一步是必审。

## 审查门

`tasks.csv` 校验通过不等于可以开始执行。

用户最初说「帮我实现 X」是需求描述，不是执行许可。本 Skill 交付后必须进入 `$workline-review` 审查任务表；执行确认由审查 `PASS` 之后再请求，不在这里提前放行。

1. 输出任务清单摘要：任务数、`HITL` 任务有哪些、关键依赖链、预计需要用户参与的节点。
2. 明确下一步是 `$workline-review`（任务目标）。同一会话跑即可。
3. 用户确认前不得启动 `$workline-run`，不得开始实现任何一条任务。
4. 若用户还想换一个 agent 再审一遍，告诉他那是可选的第二次 `$workline-review`。

## 硬约束

- PRD 验收标准保持原样。
- 待确认问题先回到 PRD 澄清。
- 审查意见中的新增想法先进入 PRD。
- 校验或门禁脚本不可用时停止并报告，禁止跳过校验直接交付 CSV。
- 没有 `prd-review=PASS` 不得拆任务。
- 交付后不得进入 `$workline-run`。

## 输出

完成时说明：

- `tasks.csv` 路径。
- 任务数量、`HITL` 任务清单、关键依赖链。
- CSV 校验命令和结果，包括每条 warning 的处理结论。
- 交付前自检结论。
- 下一步必须使用 `$workline-review` 审查 `tasks.csv`。
