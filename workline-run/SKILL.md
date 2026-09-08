---
name: workline-run
description: "Workline 长任务执行规则包。Use when the user asks to execute a Workline active directory or tasks.csv, needs execution to follow tasks.csv state and dependencies, update task states with workline_csv.py, write run.md verification notes, resume a long task, or execute the final REVIEW row."
disable-model-invocation: true
---

# Workline Run

按 `tasks.csv` 执行 Workline 任务：取下一任务、加载材料、更新状态、记录执行日志，并处理最终 REVIEW。只由用户显式调用。

**开始前先读 `<SKILL_DIR>/REFERENCE.md`**：脚本拒绝时说不出来的那几条（`mode` 判定权、`verification` 可判定性、`refs` 的两条语义、`skipped` 的调度影响）在那里。结构、状态迁移、门禁顺序、`refs` 合法形式、阻断项这些，直接按脚本的错误消息改，消息里带着完整的正确答案。本会话已经读过就不必重复读。

| 文件 | 作用 |
| --- | --- |
| `tasks.csv` | 唯一状态源；任务选择、恢复和 REVIEW 都以它为准 |
| `prd.md` | 需求和验收来源 |
| `run.md` | 阶段门禁 + 执行日志 |
| `evidence/` | 可选；只在有日志、截图、包、快照等独立产物时创建 |

## 入口

用户必须提供活动目录或 `tasks.csv` 路径：

```text
按 $workline-run 执行 .workline/active/<slug>/tasks.csv
```

在提供 `/goal` 的环境里可以 `/goal 根据 $workline-run 规范 执行 <路径>`；没有 `/goal` 时直接按本 Skill 执行，不要假装这个入口不存在就改去实现。

给的是 `tasks.csv` 时用它的父目录作为活动目录。缺 `prd.md` / `tasks.csv` / `run.md` 先停止并说明；`run.md` 必须含 `## 阶段门禁`。

## 启动或恢复

```bash
python <SKILL_DIR>/scripts/workline_csv.py require-gates <active-dir> --require materials=CONFIRMED,WAIVED --require prd-review=PASS --require tasks-review=PASS --require execute=CONFIRMED
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
```

`execute` 尚未确认时先请求用户确认，同意后写门禁再重新 `require-gates`：

```bash
python <SKILL_DIR>/scripts/workline_csv.py gates-set <active-dir> --gate execute --status CONFIRMED --actor user
```

1. `require-gates` 或 `validate` 失败时不开始实现。门禁 PASS 后改过 PRD 或任务定义，必须回到对应审查阶段。
2. `next` 返回的任务就是本轮执行对象；`on_complete` 列出的收尾动作必须真实执行。
3. `next` 优先选 AFK。`hitl=true` 时先请求用户，本轮无法参与则标 `blocked` 写 `wait-user:`，不要保持 `doing`。
4. `next` 的 `blocked` 字段按前缀归类当前阻塞任务。报告用户时按类说，不要笼统说「有几个 blocked」；`unclassified` 是历史遗留，补上前缀。
5. `warnings` 先处理再继续，`[阻断]` 的不改掉归档会失败。`worktree-dirty` 特别注意：任务级提交不要把非 `.workline` 的脏文件捎上。
6. `next` 返回 `{"next": null}` 时按 `reason` 处理：`all-closed` 全部闭环；`needs-attention` 按 `detail` 和 `blocked` 说明并请求用户决策。
7. `run.md` 由 `$workline-init` 创建，只追加任务小节，**不要重写或删除 `## 阶段门禁`**。文件或门禁表缺失时停止回到 init；只有明确执行恢复时才用 `gates-set --init` 补建，且所有门重新确认。

## 加载 refs 材料

按 `refs` 取材料，不要通读整个 `prd.md` 和 `references/`：

| 形式 | 加载动作 |
| --- | --- |
| `FR-2` / `NFR-1` | 读 `prd.md` 对应小节，以及「验收标准」「约束条件」中相关条目 |
| `references/xxx.md` | 读活动目录下该文件 |
| `evidence/T00X-xxx/` | 前序任务产物，需要复查时才读 |
| `src/driver/uart.c` | 读项目根下该文件或目录，作为参考材料 |
| `.workline/notes/xxx.md` | 已沉淀的项目约定和坑，实现前必读，与它冲突时停下说明 |

`refs` 为空时读 `prd.md` 的「目标」「功能要求」「验收标准」兜底，并在 `run.md` 记录这条任务没有材料清单。

`refs` 里的仓库内路径是「要读的参考材料」，不是「要改的目标文件」——改哪些源码由你自己搜索定位。

## 普通任务执行

`id=REVIEW` 跳到「REVIEW 行」。其余按下面走。

**标记开始**：`set <tasks.csv> T001 --state doing`。

**HITL**：先请求用户参与，只记录已经真实发生的人工确认、人手操作和外部 ACK。本轮等不到人就标 `blocked` + `wait-user:`，让无依赖的 AFK 继续。AFK 任务即使涉及编译器、探针、串口也直接按 `verification` 调用，不要改去等人。

**实现**：按 `prd.md`、任务描述和 `verification` 做最小必要实现。不扩大范围，不改验收，发现任务定义和 PRD 冲突时停止。

**验证**：

- 点名命令行或其它可执行工具：执行它，对照期望退出码或输出。
- 点名 Skill（keil、jlink、serial 等）：先读该 Skill 的 `SKILL.md`，按其流程操作，用结构化结果对照期望。未安装或缺环境标 `blocked` + `env-missing:`。
- `HITL`：只记录已经真实发生的人工检查。

记录必须包含：实际调用的命令/Skill/人工检查、真实输出摘要、失败原因或未覆盖范围。

**范围纪律自检**：对照 `on_complete` 核对——没有顺手重构、没有为当前不存在的场景加抽象或配置、没有加投机性兜底、没有改范围外文件、在行为真正所在的位置修。发现偏差在本任务内收回。

**写入 run.md**：小节标题必须是 `## <任务 ID> <title>`（ID 后直接跟空格和标题，不要加冒号）。追加在「阶段门禁」和「入口」之后。`实现` / `验证` / `输出` 三条必须非空，不能写「无」或占位符，**否则 `set --state done` 会被拒绝**。

```md
## T001 <title>

- 实现：<改了什么>
- 验证：<命令或人工检查>
- 输出：<真实输出摘要>
- 限制：<未覆盖项；没有则写“无”>
```

**evidence 产物**：只有任务自然产生可复查产物时才建 `evidence/<任务 ID>-<短名>/`，然后 `set <tasks.csv> T001 --append-refs "evidence/T001-smoke/"`。

## 提交收口

验证通过后自动尝试提交本任务的业务改动。

1. `git status --short`；未在本次任务中改过的文件不得静默纳入。
2. **不要暂存 `.workline/`**，过程文件留到 `$workline-archive`。
3. `git log --oneline -5`，提交信息融入已有风格并带上任务 ID，如 `workline: T003 完成批量导入校验`。
4. 用显式路径暂存，提交后 `commit` 写 `git rev-parse --short=12 HEAD` 的真实哈希；脚本会在 git 中核验，编造的哈希会被拒绝。
5. 没有业务改动写 `no-change`；环境无法安全提交时用 `--commit "" --notes "<原因>"`，后续任务可继续，但 `archive-check` 会失败直到补上。

**标记完成**：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234def56
```

脚本写入前强制回查完整的 `run.md` 小节和 commit 真实性。不要为了通过校验伪造日志或哈希。

## 失败与阻塞

验证失败不得标 `done`。能继续修就保持 `doing`；本轮不再推进则标 `blocked`，`notes` 必须带分类前缀：

```bash
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T003 --state blocked --notes "verify-failed: pytest 3 failed，边界用例未过"
```

`skipped` 只能来自用户确认或 PRD 明确允许。

## 执行中新增任务

当前任务范围内的必要步骤直接做；PRD 已有但漏拆的新增任务；PRD 里没有的新需求停止并回 `$workline-grill`。

用户确认后用 `add` 插入，不要手改 CSV：

```bash
python <SKILL_DIR>/scripts/workline_csv.py add <tasks.csv> T012 --mode AFK --title "..." --description "..." --verification "pytest tests/test_import.py 退出码 0" --refs "FR-2"
```

`add` 会把 `REVIEW` 退回 `todo` 并重置 `tasks-review` / `execute`。重新 `validate`，在 `run.md` 记录新增依据，交给 `$workline-review` 重审，用户再确认执行后恢复。

## REVIEW 行

只在所有非 `REVIEW` 任务闭环或已确认跳过后执行，只做检查和结论，不实现任务。`run.md` 的 `## REVIEW` 同样需要非空三条：「实现」写审查做了什么，「验证」写核对过哪些门禁和覆盖项，「输出」写结论。

覆盖检查：

1. PRD 的 FR / NFR 是否都有任务覆盖。
2. 每条完成任务是否有真实验证记录和完整 `run.md` 小节。
3. 有独立产物的任务是否有 `evidence/` 路径。
4. HITL、阻塞、跳过是否都有解释，`blocked` 是否都带分类前缀。
5. `commit` 为空的任务是否已记录原因。

候选知识条目交给 `$workline-archive` 写入 `.workline/notes/`。

## 硬约束

- `tasks.csv` 始终是计划和状态源，状态字段只用 `workline_csv.py set` 更新。
- 四扇门按顺序通过且产物摘要仍然有效，否则不得开工。
- 通过结论必须有真实验证依据；先写完整 `run.md` 小节再标 `done`。
- 任务级提交不得包含 `.workline/`；执行阶段不扩展需求范围。
- 同一活动目录只允许一个执行者写入；外部审查与执行必须串行。

## 输出

- 当前任务 ID 和状态更新结果，加载了哪些 `refs` 材料。
- `run.md` 记录位置和 evidence 产物路径（如有）。
- 验证命令或人工检查结论，`commit` 结论；为空时说明原因。
- 当前阻塞任务按 `wait-user` / `env-missing` / `verify-failed` 分类列出。
- warnings 及处理情况。
- 执行 REVIEW 时另说明最终检查结论、知识沉淀候选条目和归档前待处理问题。
