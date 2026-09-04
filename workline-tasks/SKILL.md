---
name: workline-tasks
description: "根据 Workline PRD 生成或修订可执行 tasks.csv。Use when the user provides a Workline active directory or prd.md and wants to split a reviewed PRD into small verifiable tasks, create tasks.csv with dependencies and REVIEW, revise tasks.csv after Workline review, or validate the generated CSV before execution."
---

# Workline Tasks

## 目标

读取已通过审查的 `prd.md`，把需求拆成可实现、可验证、可恢复执行的小任务，并生成 `tasks.csv`。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

## 入口检查

开始前先跑门禁，失败即停止，回到 `$workline-grill` 或 `$workline-review`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates .workline/active/<slug> --require materials=CONFIRMED,WAIVED --require prd-review=PASS
```

然后确认：

- `prd.md` 存在。
- 功能要求已使用 `### FR-<序号>` 编号，没有 `fr-headings-missing`。
- 非阻塞待确认问题已说明为什么不阻塞任务拆分。
- 如果 `prd.md` 的“风险与待确认问题”表中还有标记为阻塞任务拆分的问题，先要求回到 `$workline-grill` 修订 PRD。

如果 PRD 不满足以上条件，停止并指出缺口。

## 任务拆分规则

- `prd.md` 是需求源；审查意见作为质量反馈。
- 每条任务都应能单独实现、单独验证、单独记录状态。
- 每条 PRD 功能要求至少被一条任务的 `refs` 引用；有 `### NFR-<序号>` 的非功能要求同样必须被引用。
- 默认状态为 `state=todo`，`commit` 留空。
- 最后一行必须是 `REVIEW`，且它的 `depends_on` 必须留空。

字段含义：

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID，必须是 `T` 加至少三位数字，如 `T001`；末行固定为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个用空格分隔；普通任务不得依赖 `REVIEW`，`REVIEW` 行留空 |
| `mode` | `AFK` 可无人值守；`HITL` 需要人判断、人手操作或账号确认。编译器、探针、串口等若能自行给出通过/失败，仍标 AFK |
| `title` | 简短任务标题，必填 |
| `description` | 任务范围和实现说明；验证手段覆盖不到的完成标准也写这里 |
| `verification` | 验证手段 + 期望结果。手段可以是命令行、Skill 或其他工具，见下节 |
| `state` | `todo`、`doing`、`done`、`blocked`、`skipped` |
| `commit` | 7–64 位十六进制提交哈希 / `no-change` / 留空 |
| `refs` | 本任务的材料加载清单，见下节 |
| `notes` | 阻塞、跳过等短备注 |

`state` 语义：

| 值 | 含义 | 满足后继依赖 |
| --- | --- | --- |
| `todo` | 未开始 | 否 |
| `doing` | 进行中，含验证失败后正在修 | 否 |
| `done` | 实现完成**且**验证通过，唯一成功终态 | 是 |
| `blocked` | 验证未通过或条件不足，当前暂停；原因写 `notes` | 否 |
| `skipped` | 经用户确认或 PRD 允许跳过 | 是 |

`skipped` 会满足后继依赖。校验器会对“依赖被跳过的任务”输出 `skipped-unblocks`。看到时必须确认这不是空地基施工，否则不要把后继标成可执行 AFK。

## refs 是加载清单，不是备注

`refs` 决定执行该任务时要加载哪些材料。只允许四类，空格分隔：

| 形式 | 含义 | 解析基准 |
| --- | --- | --- |
| `FR-2` / `NFR-1` | `prd.md` 中对应要求小节 | — |
| `references/proto-v2.md` | `references/` 下的输入材料 | 活动目录 |
| `evidence/T001-smoke/` | 执行阶段产生的产物目录，由 `--append-refs` 追加 | 活动目录 |
| `src/driver/uart.c` | `brief.md` 登记的仓库内材料 | 项目根（含 `.workline/` 的目录） |

示例：

```text
FR-2 NFR-1 references/import-format.md src/driver/uart.c
```

仓库内路径只写「执行时要读的既有材料」，不写本任务要修改的目标文件——改哪些源码由执行者自己定位。

不要写外部绝对路径（`D:/...`、`/opt/...`），也不要写成 `FR-01`。路径中禁止 `.` / `..` 跳转和反斜杠。校验器会对非法项输出 `refs-invalid`，对指向不存在位置的路径输出 `refs-not-found`。`brief.md` 里登记的外部绝对路径材料不能进 `refs`，需要它的结论应已在 PRD 中固化。

`refs` 为空会产生 `refs-missing` warning。确实不需要任何材料的任务，用 `--allow-empty-refs` 豁免校验。

## verification 写什么

`verification` 描述「用什么手段、怎样算过」。不要另加工具列。手段可以是命令行、已安装的 Agent Skill，或其他能给出通过/失败的工具。反引号只是可选排版，校验器不要求。

| `mode` | 何时使用 | `verification` 怎么写 |
| --- | --- | --- |
| `AFK` | 执行时不等人，判定能由命令、Skill 或其他工具自己给出 | 写清调用什么、期望什么。例如：`pytest tests/test_import.py` 退出码 0；keil build 成功且 errors=0；jlink flash 成功，且 jlink rtt 在 3s 内出现 boot ok |
| `HITL` | 判定权在人，或必须人选 / 人手操作 | 写清人看什么、怎样算过。例如：打开导入页上传 samples/bad.csv，人确认错误报告可读 |

拆表时按判定权选模式，不要因为「不是 shell 命令」或「会碰到板子」就改成 HITL：

- 工具能自行判定 → `AFK`。点名 Skill 时写 skill 名和期望结果，执行阶段会去加载该 Skill。
- 必须人看、人选、人确认 → `HITL`。例如界面是否可读、多工程时 Skill 规定不得自动猜测。
- 工具或环境不具备（没装 Skill、没探针、编译器不在）→ 执行时标 `blocked`，不是改成 HITL 等人来补环境。

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

生成阶段必须逐条处理这些 warning：

| 代码 | 处理 |
| --- | --- |
| `fr-headings-missing` | PRD 功能要求没有 `### FR-N`，回到 `$workline-grill` |
| `fr-uncovered` / `nfr-uncovered` | 漏拆，补任务或说明为什么不需要 |
| `refs-missing` | 补加载清单，或确认无需材料后用 `--allow-empty-refs` |
| `refs-invalid` / `refs-not-found` / `req-id-padded` | 改正 refs |
| `skipped-unblocks` | 确认后继仍可执行 |

## REVIEW 行

`REVIEW` 行必须是最后一行，`depends_on` 留空；它隐式依赖全部任务。由执行阶段负责最终审计，不承担实现工作。

`REVIEW` 行的 refs 不计入 FR/NFR 覆盖，防止用最终审计行代替真正的实现任务。

## 交付前自检

交付 `tasks.csv` 前逐条核对，把结论写进输出。核对范围与 `$workline-review` 的任务审查清单相同：任务是否足够小、能否追溯到 PRD、AFK/HITL 是否按判定权标对、验证是否写清手段和期望结果、refs 是否合法、依赖是否真实。不要因为没有反引号就把 AFK 改成 HITL。

本 Skill 做完自检仍不能进入执行。下一步是必审。

## 审查门

`tasks.csv` 校验通过不等于可以开始执行。

用户最初说“帮我实现 X”是需求描述，不是执行许可。本 Skill 交付后必须进入 `$workline-review` 审查任务表；执行确认由审查 `PASS` 之后再请求，不在这里提前放行。

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
