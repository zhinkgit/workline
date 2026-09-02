---
name: workline-run
description: "Workline 的 /goal 长任务执行规则包。Use when the user invokes /goal with a Workline active directory or tasks.csv, needs execution to follow tasks.csv state and dependencies, update task states with workline_csv.py, write run.md verification notes, resume a long task, or execute the final REVIEW row."
---

# Workline Run

## 目标

本 Skill 规定 `/goal` 如何执行一份 Workline `tasks.csv`：读取下一任务、更新状态、记录执行日志，并处理最终 REVIEW。

四个文件角色要分清：

| 文件或目录 | 作用 |
| --- | --- |
| `tasks.csv` | 唯一任务状态源；任务选择、恢复和 REVIEW 都以它为准 |
| `prd.md` | 需求和验收来源 |
| `run.md` | 人类复盘日志；记录过程、命令、输出摘要和限制 |
| `evidence/` | 可选产物目录；只在有日志、截图、包、快照等独立产物时创建 |

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

用户主动调用时必须提供活动目录或 `tasks.csv` 路径。

推荐调用：

```text
/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv
```

## 输入定位

如果用户给的是活动目录：

1. 使用 `<active-dir>/tasks.csv` 作为任务表。
2. 使用 `<active-dir>/prd.md` 作为需求来源。
3. 使用 `<active-dir>/run.md` 作为执行日志。
4. 只在需要查引用材料时读取 `<active-dir>/references/`。

如果用户直接给的是 `tasks.csv`：

1. 使用该 CSV 的父目录作为活动目录。
2. 在父目录下寻找 `prd.md`、`run.md`、`references/`。
3. 如果缺少 `prd.md` 或 `tasks.csv`，先停止并说明缺失项。

## 启动或恢复

每次开始或恢复执行都先运行：

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
```

处理规则：

1. `validate` 失败时，不开始实现任务；先修复明显的 CSV 格式问题，无法确定时请求用户确认。
2. 脚本调不到时停止并报告，禁止跳过校验继续执行。
3. `next` 返回的任务对象就是本轮执行对象；它的 `on_complete` 字段列出本任务的收尾动作，必须真实执行，不得只在回复里声称已执行。
4. `next` 和 `validate` 输出的 `warnings` 是系统侧回查结果，必须先处理再继续：
   - `commit-missing`：已闭环任务的提交收口没做完。
   - `run-log-missing`：已闭环任务在 `run.md` 里没有对应小节，说明日志漏写。
   - `exception-state`：存在 `failed` / `blocked` / `skipped` 任务。
5. `next` 返回 `{"next": null}` 时按 `reason` 处理：`all-closed` 表示全部闭环；`needs-attention` 表示有失败、阻塞或依赖未满足的任务，按 `detail` 逐项说明并请求用户决策。
6. 如果 `run.md` 不存在，创建它，并记录本次入口时间、PRD 路径和 CSV 路径。

## 读取任务

对 `next` 返回的任务，先读取这些字段：

| 字段 | 执行时怎么用 |
| --- | --- |
| `id` | 状态更新、日志标题、提交信息和产物目录命名 |
| `mode` | 判断是否需要 HITL、人工确认或实机参与 |
| `title` / `description` | 明确本任务要做什么，以及验证命令覆盖不到的完成标准 |
| `verification` | 决定要跑什么验证或做什么人工检查，以及什么输出算通过 |
| `refs` / `notes` | 查引用、了解已有阻塞原因 |
| `on_complete` | 本任务的收尾动作清单 |

如果任务 `id=REVIEW`，跳到“REVIEW 行”。其它任务按“普通任务执行”处理。

## 普通任务执行

### 标记开始

执行前把任务状态更新为 `doing`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state doing
```

### 处理 HITL

如果 `mode=HITL`，并且任务需要人工输入、账号权限、实机操作、现场确认或高风险选择，先请求用户参与。

人工确认、实机操作和外部 ACK 只记录已经真实发生的结果。

### 实现

按 `prd.md`、任务描述和 `verification` 做最小必要实现。

执行中遵守三点：

1. 不扩大任务范围。
2. 验收要求保持不变。
3. 发现任务定义和 PRD 冲突时，停止并请求确认。

### 验证

实现后按任务的 `verification` 字段验证。

验证记录必须包含：

1. 执行过的命令或人工检查动作。
2. 真实输出摘要或检查结论。
3. 失败原因、阻塞项或未覆盖范围。
4. 必要时说明未覆盖真实设备、真实服务或真实 ACK。

### 写入 run.md

`run.md` 只写人类需要复盘的信息，保持简短。小节标题必须是 `## <任务 ID> <title>`，脚本靠这个标题回查日志是否真的写了：

```md
## T001 <title>

- 实现：<改了什么>
- 验证：<命令或人工检查>
- 输出：<真实输出摘要>
- 限制：<未覆盖项；没有则写“无”>
```

状态仍以 `tasks.csv` 为准。

### 处理 evidence 产物

只有任务自然产生 build log、截图、验证结果、配置快照、部署包等可复查产物时，才创建 `evidence/<任务 ID>-<短名>/` 目录，内部结构自便。创建后通过 `--append-refs` 关联路径：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --append-refs "evidence/T001-smoke/"
```

没有独立产物时省略 evidence 目录。

## 提交收口

任务验证通过后，自动尝试提交本任务的业务改动。

执行顺序：

1. 运行 `git status --short`，把脏文件分成两类：本次会话中你自己改的业务文件，以及你没有碰过的文件。后者不得静默纳入提交。
2. 提交范围限于当前任务相关的业务代码、测试、文档或配置文件。
3. 使用显式路径暂存文件。
4. 没有业务改动需要提交时，`commit` 写 `no-change`。
5. 成功提交后，`commit` 写 7–64 位十六进制提交哈希。
6. 当前环境无法安全提交时（改动归属不清、提交失败、当前目录不是 Git 仓库），`commit` 留空，在 `notes` 和 `run.md` 写明原因，然后继续执行后续任务。

任务级提交信息推荐包含任务 ID：

```text
workline: T003 完成批量导入校验
```

### 标记完成

验证通过且提交收口处理完后，一次性写入终态：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234
```

## 失败与阻塞

失败时先保护状态真实性：

1. 验证失败或初步检查失败时，不得把 `state` 标为 `done`。
2. 如果可以继续修复，保持 `doing`，并在 `run.md` 记录失败输出或检查结论。
3. 如果验证已执行且未通过、本轮不再继续，更新为 `failed` 并写明原因。
4. 如果当前条件不足导致无法继续，更新为 `blocked` 并写明原因。
5. 提交失败不改变验证结论，只让 `commit` 留空并记录原因。
6. `skipped` 只能来自用户确认或 PRD 明确允许；必须在 `notes` 和 `run.md` 记录依据。

验证结论必须来自真实命令、人工检查或外部确认。

## REVIEW 行

`REVIEW` 行只在所有非 `REVIEW` 任务闭环或已确认跳过后执行，由 `next` 自动判定。

REVIEW 只做检查和结论，不实现任务。

覆盖检查：

1. PRD 功能要求和验收标准是否都有任务覆盖。
2. 每条完成任务是否有真实验证记录和 `run.md` 小节。
3. 有独立产物的任务是否有 `evidence/` 路径。
4. HITL、真实链路未覆盖、失败、阻塞、跳过是否都有解释。
5. `commit` 为空的任务是否已记录为归档前待处理问题。

范围纪律检查，针对 AI 编码的典型偏差：

1. 是否做了任务没要求的顺手整理或重构。
2. 是否为当前不存在的场景加了抽象层、配置项或扩展点。
3. 是否为不可能发生的状态加了投机性兜底分支。
4. 是否改了 PRD 和任务描述都没提到的文件。
5. 是否在调用方打了补丁，而不是去行为真正所在的位置修。

发现缺口时，只记录问题、更新状态，并按需要请求用户确认。结论写入 `run.md` 的 `## REVIEW` 小节。

## 硬约束

- `tasks.csv` 始终是计划和状态源。
- 状态字段通过 `workline_csv.py set` 更新。
- 目标、功能要求和验收标准来自 `prd.md`。
- 通过结论必须有真实验证依据。
- `commit` 为空不阻止后续任务和 REVIEW，但会阻止 `$workline-archive` 归档。

## 输出

完成或暂停时说明：

- 当前任务 ID 和状态更新结果。
- `run.md` 记录位置，以及 evidence 产物路径（如有）。
- 验证命令或人工检查结论。
- `commit` 结论；如果为空，说明原因。
- 脚本输出的 warnings 及处理情况。
- 如果执行的是 REVIEW，说明最终检查结论和归档前待处理问题。
