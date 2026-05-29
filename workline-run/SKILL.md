---
name: workline-run
description: "Workline 的 /goal 长任务执行规则包。Use when the user invokes /goal with a Workline active directory or tasks.csv, needs execution to follow tasks.csv state and dependencies, update task states with workline_csv.py, write run.md verification notes, resume a long task, or execute the final REVIEW row. This skill is not a scheduler and does not replace /goal."
---

# Workline Run

## 0. 定位

本 Skill 只规定 `/goal` 如何执行一份 Workline `tasks.csv`。它不是调度器，不重新拆任务，不重写 PRD，也不凭聊天记录判断任务状态。

四个文件角色要分清：

| 文件或目录 | 作用 |
| --- | --- |
| `tasks.csv` | 唯一任务状态源；任务选择、恢复和 REVIEW 都以它为准 |
| `prd.md` | 需求和验收来源；执行时只读取，不擅自改目标 |
| `run.md` | 人类复盘日志；记录过程、命令、输出摘要和限制 |
| `evidence/` | 可选产物目录；只在有日志、截图、包、快照等独立产物时创建 |

用户主动调用时必须提供活动目录或 `tasks.csv` 路径；不要猜测当前 active 任务。

推荐调用：

```text
/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv
```

## 1. 输入定位

如果用户给的是活动目录：

1. 使用 `<active-dir>/tasks.csv` 作为任务表。
2. 使用 `<active-dir>/prd.md` 作为需求来源。
3. 使用 `<active-dir>/run.md` 作为执行日志。
4. 只在需要查引用材料时读取 `<active-dir>/references/`。

如果用户直接给的是 `tasks.csv`：

1. 使用该 CSV 的父目录作为活动目录。
2. 在父目录下寻找 `prd.md`、`run.md`、`references/`。
3. 如果缺少 `prd.md` 或 `tasks.csv`，先停止并说明缺失项。

## 2. 启动或恢复

每次开始或恢复执行都先运行：

```bash
python workline-run/scripts/workline_csv.py validate <tasks.csv>
python workline-run/scripts/workline_csv.py next <tasks.csv>
```

如果需要快速了解整体状态，可以额外运行：

```bash
python workline-run/scripts/workline_csv.py summary <tasks.csv>
```

处理规则：

1. `validate` 失败时，不开始实现任务；先修复明显的 CSV 格式问题，无法确定时请求用户确认。
2. `next` 返回的第一条 `todo` 或 `doing` 任务就是本轮执行对象。
3. `summary` 只作为状态快照，不是门禁；不要把它当成验证质量判断。
4. 如果 `run.md` 不存在，创建它，并记录本次入口时间、PRD 路径和 CSV 路径。

## 3. 读取任务

对 `next` 返回的任务，先读取这些字段：

| 字段 | 执行时怎么用 |
| --- | --- |
| `id` | 状态更新、日志标题、提交信息和产物目录命名 |
| `mode` | 判断是否需要 HITL、人工确认或实机参与 |
| `title` / `description` | 明确本任务要做什么 |
| `acceptance_criteria` | 判断任务是否完成 |
| `verification` | 决定要跑什么验证或做什么人工检查 |
| `refs` / `notes` | 查引用、记录验证摘要、阻塞原因和简短限制 |

如果任务 `id=REVIEW`，跳到“7. REVIEW 行”。其它任务按“4. 普通任务执行”处理。

## 4. 普通任务执行

### 4.1 标记开始

执行前把任务状态更新为 `doing`：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --dev_state doing --append-notes "started"
```

### 4.2 处理 HITL

如果 `mode=HITL`，并且任务需要人工输入、账号权限、实机操作、现场确认或高风险选择，先请求用户参与。

不要把未发生的人工确认、实机操作或外部 ACK 写成已完成。

### 4.3 实现

按 `prd.md`、任务描述和验收标准做最小必要实现。

执行中遵守三点：

1. 不扩大任务范围。
2. 不降低验收标准。
3. 发现任务定义和 PRD 冲突时，停止并请求确认。

### 4.4 验证

实现后按任务的 `verification` 字段验证。

验证记录必须包含：

1. 执行过的命令或人工检查动作。
2. 真实输出摘要或检查结论。
3. 失败原因、阻塞项或未覆盖范围。
4. 必要时说明未覆盖真实设备、真实服务或真实 ACK。

### 4.5 写入 run.md

`run.md` 只写人类需要复盘的信息，保持简短：

```md
## T001 <title>

- 实现：<改了什么>
- 验证：<命令或人工检查>
- 输出：<真实输出摘要>
- 产物：<如有 evidence 路径则写路径；没有则写“无”>
- 限制：<未覆盖项；没有则写“无”>
```

`run.md` 不是机读状态源。状态仍以 `tasks.csv` 为准。

### 4.6 处理 evidence 产物

只有任务自然产生 build log、截图、验证结果、配置快照、部署包等可复查产物时，才创建 evidence 目录：

```text
evidence/T012-board-check/
├── attempt-01-timeout/
├── attempt-02-new-ip/
└── smoke/
```

创建后通过 `--append-refs` 关联路径。没有独立产物时，不要为了流程创建空 evidence 目录。

### 4.7 标记验证通过

验证通过后，把 `dev_state` 和 `verify_state` 更新完成，同时把 `git_state` 置为 `pending`，表示提交收口还没完成。

示例：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --dev_state done --verify_state passed --git_state pending --append-notes "verified"
```

如果有独立 evidence 产物，追加引用：

```bash
python workline-run/scripts/workline_csv.py set <tasks.csv> T001 --append-refs "evidence/T001-smoke/"
```

## 5. 提交收口

任务验证通过后，自动尝试提交本任务的业务改动。

执行顺序：

1. 运行 `git status --short`，识别当前任务相关改动。
2. 不提交 `.workline/active/...`、`.workline/archive/...`、`references/`、`evidence/` 或其它 Workline 过程文件。
3. 不使用 `git add .`。
4. 只暂存能确认属于当前任务的业务代码、测试、文档或配置文件。
5. 如果没有业务改动需要提交，将 `git_state` 更新为 `done`，并在 `notes` 或 `run.md` 说明 `no business changes`。
6. 如果业务改动归属清晰，暂存相关文件并执行一次任务级提交，然后将 `git_state` 更新为 `done`，并记录提交哈希。
7. 如果当前不是 Git 仓库、提交失败、混有不相关改动或改动归属不清，将 `git_state` 更新为 `blocked`，在 `notes` 和 `run.md` 写明原因，然后继续执行后续任务。

任务级提交信息推荐包含任务 ID：

```text
workline: T003 完成批量导入校验
```

## 6. 失败与阻塞

失败时先保护状态真实性：

1. 验证失败或初步检查失败时，不得把 `dev_state` 标为 `done`。
2. 如果可以继续修复，保持或更新为 `doing`，并在 `run.md` 记录失败输出或检查结论。
3. 如果当前条件不足导致无法继续，更新为 `blocked`，同时把 `verify_state` 更新为 `failed` 或 `blocked`，并写明原因。
4. 自动提交失败不改变 `dev_state=done` 和 `verify_state=passed` 的验证结论，只把 `git_state` 更新为 `blocked`。
5. `skipped` 只能来自用户确认或 PRD 明确允许；必须在 `notes` 和 `run.md` 记录依据。

禁止为了推进流程而吞错、删除测试、绕过校验、使用假数据、空跑或把“看起来可以”写成通过。

## 7. REVIEW 行

`REVIEW` 行只在所有非 `REVIEW` 任务闭环或已确认跳过后执行。

进入条件：

1. 不存在 `todo` 或 `doing` 的普通任务。
2. 不存在未解释的 `failed` 或 `blocked` 任务。
3. 不存在未解释的 `failed`、`blocked`、`skipped` 或 `git_state=pending/blocked`。

REVIEW 只做检查和结论，不补做实现任务。

检查清单：

1. PRD 功能要求和验收标准是否都有任务覆盖。
2. `tasks.csv` 状态是否一致。
3. 每条完成任务是否有验证记录。
4. 每条通过任务是否在 `run.md` 或 `notes` 中有验证摘要。
5. 有独立产物的任务是否有 evidence 路径。
6. HITL、真实链路未覆盖、失败、阻塞、跳过是否都有解释。
7. `git_state` 是否已有归档前结论；存在 `pending` 或 `blocked` 时，只记录为归档前待处理问题。

REVIEW 发现缺口时，只记录问题、更新状态，并按需要请求用户确认。

## 8. 硬约束

- `tasks.csv` 始终是计划和状态源。
- 状态字段只能通过 `workline_csv.py set` 更新，不手工编辑。
- 不把 `run.md` 或聊天记录当作任务状态源。
- 不重新解释目标、功能要求或验收标准。
- 不用假数据、空跑、只读代码或“看起来可以”冒充通过。
