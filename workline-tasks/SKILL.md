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
- 功能要求已使用 `### FR-<序号>` 编号。
- 非阻塞待确认问题已说明为什么不阻塞任务拆分。
- 如果 `prd.md` 的“风险与待确认问题”表中还有标记为阻塞任务拆分的问题，先要求回到 `$workline-grill` 修订 PRD。

如果 PRD 不满足以上条件，停止并指出缺口。

## 任务拆分规则

- `prd.md` 是需求源；审查意见作为质量反馈。
- 每条任务都应能单独实现、单独验证、单独记录状态。
- 每条 PRD 功能要求至少被一条任务的 `refs` 引用。
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

## refs 是加载清单，不是备注

`refs` 决定执行该任务时要加载哪些材料。它不是自由文本备注，执行阶段会按它取材料。

格式：空格分隔的引用项，三类：

| 形式 | 含义 |
| --- | --- |
| `FR-2` | `prd.md` 中对应功能要求小节 |
| `references/proto-v2.md` | `references/` 下的输入材料 |
| `evidence/T001-smoke/` | 执行阶段产生的产物目录，由 `--append-refs` 追加 |

示例：

```text
FR-2 FR-3 references/import-format.md
```

**不要写源码路径。** 执行阶段的 agent 有搜索和读文件能力，源码它自己会找；`refs` 要给的是它不知道去哪找的东西——需求出处、协议文档、外部资料、历史决策。把源码塞进 `refs` 只会挤占上下文。

`refs` 为空会产生 `refs-missing` warning。确实不需要任何材料的任务（例如纯配置项调整），用 `--allow-empty-refs` 豁免校验。

## verification 的强度

`mode=AFK` 意味着无人值守，它的验证必须机器可判定。校验器会检查 `verification` 里有没有可执行命令的痕迹，没有就输出 `verification-weak` warning。

看到这个 warning 时二选一，不要放着不管：

- 补上真实可执行命令，命令用反引号包裹。
- 承认这条任务需要人判断，改为 `mode=HITL`，并写清人工检查方式和判定标准。

`AFK` + “检查代码是否正确”这类写法会让整个无人值守执行变成自我确认，必须避免。

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

校验失败时修正 CSV，直到通过。结构错误退出码为 1；`refs-missing`、`verification-weak`、`fr-uncovered`、`commit-missing`、`run-log-missing`、`exception-state` 以 warning 形式输出，不影响退出码。

生成阶段必须逐条处理这三类 warning：

| 代码 | 处理 |
| --- | --- |
| `fr-uncovered` | 该 FR 漏拆，补任务或说明为什么不需要任务 |
| `refs-missing` | 补加载清单，或确认无需材料后用 `--allow-empty-refs` |
| `verification-weak` | 补可执行命令，或改为 `mode=HITL` |

## REVIEW 行

`REVIEW` 行必须：

- 是最后一行。
- `depends_on` 留空；它隐式依赖全部任务，中途新增任务不需要回来修改这一行。
- 由执行阶段负责最终审计，不承担实现工作。

## 交付前自检

交付 `tasks.csv` 前逐条核对，把结论写进输出：

- 每条非 `REVIEW` 任务是否足够小、可单独实现、可单独验证。
- 每条任务是否能追溯到 `prd.md` 的功能要求或验收标准。
- 是否遗漏 PRD 中的功能要求、非功能要求、迁移要求或验收标准。
- 是否把 PRD 中未闭环的待确认问题伪装成可执行任务。
- `mode=AFK/HITL` 是否合理，人工输入、实机操作、账号权限是否被标为 `HITL`。
- `verification` 是否写清了验证手段**和**期望结果。
- `description` 是否写清了验证命令覆盖不到的完成标准。
- `refs` 是否只含 FR 编号和材料路径，没有混入源码路径。
- 依赖关系是否反映真实的实现顺序，而不是凭空串行。

需要独立复核或换一个模型审查时，调用 `$workline-review`。

## 执行确认门

`tasks.csv` 校验通过不等于可以开始执行。

用户最初说“帮我实现 X”是需求描述，不是执行许可。进入 `/goal` 前必须让用户在**看过任务表之后**再确认一次：

1. 输出任务清单摘要：任务数、`HITL` 任务有哪些、关键依赖链、预计需要用户参与的节点。
2. 明确请求用户确认可以开始执行。
3. 用户确认前不得启动 `/goal`，不得开始实现任何一条任务。

## 硬约束

- PRD 验收标准保持原样。
- 待确认问题先回到 PRD 澄清。
- 审查意见中的新增想法先进入 PRD。
- 校验脚本不可用时停止并报告，禁止跳过校验直接交付 CSV。
- 未获得执行确认前不进入 `/goal`。

## 输出

完成时说明：

- `tasks.csv` 路径。
- 任务数量、`HITL` 任务清单、关键依赖链。
- CSV 校验命令和结果，包括每条 warning 的处理结论。
- 交付前自检结论。
- 请求用户确认可以开始执行；确认后再使用 `/goal 根据 $workline-run 规范 执行 <tasks.csv>`。
