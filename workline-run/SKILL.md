---
name: workline-run
description: "Workline 长任务执行规则包。Use when the user asks to execute a Workline active directory or tasks.csv, needs execution to follow tasks.csv state and dependencies, update task states with workline_csv.py, write run.md verification notes, resume a long task, or execute the final REVIEW row."
---

# Workline Run

## 目标

按 `tasks.csv` 执行 Workline 任务：读取下一任务、加载材料、更新状态、记录执行日志，并处理最终 REVIEW。

四个文件角色要分清：

| 文件或目录 | 作用 |
| --- | --- |
| `tasks.csv` | 唯一任务状态源；任务选择、恢复和 REVIEW 都以它为准 |
| `prd.md` | 需求和验收来源 |
| `run.md` | 阶段门禁 + 人类复盘日志；没有任务审查 PASS 和执行确认不得开工 |
| `evidence/` | 可选产物目录；只在有日志、截图、包、快照等独立产物时创建 |

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

用户主动调用时必须提供活动目录或 `tasks.csv` 路径。

推荐调用：

```text
按 $workline-run 执行 .workline/active/<slug>/tasks.csv
```

在提供 `/goal` 的环境里也可以：

```text
/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv
```

没有 `/goal` 时直接按本 Skill 执行，不要假装这个入口不存在就改去实现。

## 输入定位

如果用户给的是活动目录：

1. 使用 `<active-dir>/tasks.csv` 作为任务表。
2. 使用 `<active-dir>/prd.md` 作为需求来源。
3. 使用 `<active-dir>/run.md` 作为门禁和执行日志。
4. 按当前任务的 `refs` 读取材料：`references/` 与 `evidence/` 相对活动目录，其它相对路径相对项目根。

如果用户直接给的是 `tasks.csv`：

1. 使用该 CSV 的父目录作为活动目录。
2. 在父目录下寻找 `prd.md`、`run.md`、`references/`。
3. 如果缺少 `prd.md`、`tasks.csv` 或 `run.md`，先停止并说明缺失项。`run.md` 必须含 `## 阶段门禁`。

## 启动或恢复

每次开始或恢复执行都先运行：

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates <active-dir> --require materials=CONFIRMED,WAIVED --require prd-review=PASS --require tasks-review=PASS --require execute=CONFIRMED
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
```

`require-gates` 还会重算 PRD 和任务计划摘要。门禁 PASS 后修改过 PRD 或任务定义，必须回到对应审查阶段。

`execute` 尚未确认时，先请求用户确认，用户同意后再写门禁，然后重新 `require-gates`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set <active-dir> --gate execute --status CONFIRMED --actor user
```

处理规则：

1. `require-gates` 或 `validate` 失败时，不开始实现任务。`validate` 现在把 `done` 但日志不完整、commit 为空或哈希不在 git 中的情况当作错误。
2. 脚本调不到时停止并报告，禁止跳过校验继续执行。
3. `next` 返回的任务对象就是本轮执行对象；它的 `on_complete` 字段列出本任务的收尾动作，必须真实执行。
4. `next` 在可执行任务里**优先选 AFK**。`hitl=true` 时先请求用户；本轮无法参与则 `set --state blocked --notes "等待用户"`，不要保持 `doing`。
5. `warnings` 必须先处理再继续：

   | 代码 | 含义 | 处理 |
   | --- | --- | --- |
   | `exception-state` | 存在 `blocked` / `skipped` 任务 | 按 `notes` 判断能否继续 |
   | `skipped-unblocks` | 后继依赖被跳过的任务 | 确认不是空地基施工 |
   | `refs-missing` / `refs-invalid` / `refs-not-found` | 材料清单有问题 | 补或改正 `refs` |
   | `fr-uncovered` / `nfr-uncovered` / `fr-headings-missing` | 需求覆盖缺口 | 可能漏拆，报告用户 |
   | `worktree-dirty` | 工作区有非 `.workline` 的脏文件 | 任务级提交不要把它们捎上 |

6. `next` 返回 `{"next": null}` 时按 `reason` 处理：`all-closed` 表示全部闭环；`needs-attention` 按 `detail` 说明并请求用户决策。
7. `run.md` 由 `$workline-init` 创建。追加任务小节，**不要重写或删除 `## 阶段门禁`**。若文件或门禁表缺失，默认停止并回到 init；只有明确执行恢复时才可用 `gates-set --init` 补建，且所有门会从初始状态重新确认。

## 读取任务

对 `next` 返回的任务，先读取 `id`、`mode`、`hitl`、`title`、`description`、`verification`、`refs`、`notes`、`on_complete`。

如果任务 `id=REVIEW`，跳到“REVIEW 行”。其它任务按“普通任务执行”处理。

## 加载 refs 材料

实现前按 `refs` 取材料，不要通读整个 `prd.md` 和整个 `references/`：

| 形式 | 加载动作 |
| --- | --- |
| `FR-2` / `NFR-1` | 读 `prd.md` 中对应小节，以及“验收标准”“约束条件”中与之相关的条目 |
| `references/xxx.md` | 读活动目录下的该文件 |
| `evidence/T00X-xxx/` | 前序任务的产物，需要复查时才读 |
| `src/driver/uart.c` | 读项目根下的该文件或目录，作为参考材料 |

`refs` 为空时，读 `prd.md` 的“目标”“功能要求”“验收标准”三节作为兜底，并在 `run.md` 中记录这条任务没有材料清单。

`refs` 里的仓库内路径是「要读的参考材料」，不是「要改的目标文件」。需要改哪些源码由你自己搜索定位，不要把目标文件补进 `refs`。

## 普通任务执行

### 标记开始

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state doing
```

### 处理 HITL

`hitl=true` 或 `mode=HITL` 时，先请求用户参与。人工确认、人手操作和外部 ACK 只记录已经真实发生的结果。本轮等不到人，就标 `blocked`，让无依赖的 AFK 任务继续。

AFK 任务即使涉及编译器、探针、串口，也按 `verification` 直接调用对应命令或 Skill，不要改去等人。工具或环境不具备则 `blocked`。

### 实现

按 `prd.md`、任务描述和 `verification` 做最小必要实现。不扩大范围，不改验收，发现任务定义和 PRD 冲突时停止。

### 验证

实现后按 `verification` 验证。它写的是手段和期望结果，不是必须包反引号的 shell 命令。

- 点名了命令行或其他可执行工具：执行它，对照期望退出码或输出。
- 点名了 Skill（如 keil、jlink、serial）：先读取该 Skill 的 `SKILL.md`，按其流程操作，用结构化结果对照期望。未安装或缺环境则 `blocked`，写清原因。
- `HITL`：只记录已经真实发生的人工检查。

记录必须包含：实际调用的命令/Skill/人工检查、真实输出摘要、失败原因或未覆盖范围。不要因为没有反引号就拒绝 AFK。

### 范围纪律自检

标记完成前对照 `on_complete` 自检：没有顺手重构、没有为当前不存在的场景加抽象或配置、没有加投机性兜底、没有改范围外文件、在行为真正所在的位置修。发现偏差就在本任务内收回。

### 写入 run.md

小节标题必须是 `## <任务 ID> <title>`。追加在「阶段门禁」和「入口」之后，不要改那两节。`实现` / `验证` / `输出` 三条都必须有非空内容，不能写“无”或占位符；**否则 `set --state done` 会被拒绝**。

```md
## T001 <title>

- 实现：<改了什么>
- 验证：<命令或人工检查>
- 输出：<真实输出摘要>
- 限制：<未覆盖项；没有则写“无”>
```

### 处理 evidence 产物

只有任务自然产生可复查产物时，才创建 `evidence/<任务 ID>-<短名>/`，然后：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --append-refs "evidence/T001-smoke/"
```

## 提交收口

任务验证通过后，自动尝试提交本任务的业务改动。

1. 运行 `git status --short`。未在本次任务中改过的文件不得静默纳入提交。
2. **不要暂存 `.workline/`**。`tasks.csv`、`run.md` 等过程文件留到 `$workline-archive`。
3. 运行 `git log --oneline -5`，提交信息融入已有风格，并带上任务 ID。
4. 使用显式路径暂存文件。
5. 没有业务改动时，`commit` 写 `no-change`。
6. 成功提交后，`commit` 写 `git rev-parse --short=12 HEAD` 的真实哈希。脚本会核验该哈希是否存在于本仓库；编造的 `deadbeef` 会被拒绝。
7. 当前环境无法安全提交时，用 `--commit "" --notes "<原因>"` 显式说明。后续任务可以继续，但 `archive-check` 会失败，直到补上真实哈希或 `no-change`。

```text
workline: T003 完成批量导入校验
```

### 标记完成

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234def56
```

脚本在写入前强制回查：完整的 `run.md` 小节；commit 为真实哈希、`no-change`，或空值加 notes。哈希会在 git 中核验。`done` / `skipped` 是终态，回退必须加 `--force`。不要为了通过校验而伪造日志或哈希。

## 失败与阻塞

1. 验证失败时不得把 `state` 标为 `done`。
2. 可以继续修就保持 `doing`。
3. 本轮不再推进则 `blocked`，并在 `notes` 写明原因。HITL 等人属于这种情况。
4. `skipped` 只能来自用户确认或 PRD 明确允许。

## 执行中新增任务

1. 当前任务范围内的必要步骤直接做；PRD 已有但漏拆的，新增任务；PRD 里没有的新需求，停止并回 `$workline-grill`。
2. 用户确认后用 `add` 插入，不要手改 CSV：

```bash
python <SKILL_DIR>/scripts/workline_csv.py add <tasks.csv> T012 --mode AFK --title "..." --description "..." --verification "pytest tests/test_import.py 退出码 0" --refs "FR-2"
```

3. `add` 会自动把 `REVIEW` 退回 `todo`，并重置 `tasks-review` 和 `execute`。
4. 重新 `validate`，在 `run.md` 记录新增依据，然后交给 `$workline-review` 重新审查任务计划，用户再确认执行后恢复。

## REVIEW 行

`REVIEW` 只在所有非 `REVIEW` 任务闭环或已确认跳过后执行。只做检查和结论，不实现任务。`run.md` 的 `## REVIEW` 同样需要非空的实现 / 验证 / 输出三条（这里“实现”写审查做了什么，“验证”写核对过哪些门禁和覆盖项，“输出”写结论）。

覆盖检查：

1. PRD 的 FR / NFR 是否都有任务覆盖。
2. 每条完成任务是否有真实验证记录和完整 `run.md` 小节。
3. 有独立产物的任务是否有 `evidence/` 路径。
4. HITL、阻塞、跳过是否都有解释。
5. `commit` 为空的任务是否已记录原因。

范围纪律与知识沉淀判断保持不变。候选知识条目交给 `$workline-archive` 写入 `.workline/notes/`。

## 硬约束

- `tasks.csv` 始终是计划和状态源。
- 状态字段通过 `workline_csv.py set` 更新。
- 四扇门必须按顺序通过，且 PRD / 任务计划摘要必须仍然有效，否则不得开工。
- 通过结论必须有真实验证依据。
- 先写完整 `run.md` 小节，再标记 `done`。
- 任务级提交不得包含 `.workline/`。
- 执行阶段不扩展需求范围。
- 同一活动目录只允许一个执行者写入；外部审查与执行必须串行。

## 输出

完成或暂停时说明：

- 当前任务 ID 和状态更新结果。
- 加载了哪些 `refs` 材料。
- `run.md` 记录位置，以及 evidence 产物路径（如有）。
- 验证命令或人工检查结论。
- `commit` 结论；如果为空，说明原因。
- 脚本输出的 warnings 及处理情况。
- 如果执行的是 REVIEW，说明最终检查结论、知识沉淀候选条目和归档前待处理问题。
