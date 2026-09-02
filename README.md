# Workline

Workline 是一套独立、轻量、可审计的长任务工作流。它把一个粗略需求推进为可执行任务，再交给 `/goal` 按 `tasks.csv` 持续执行和恢复。

它刻意不复用 OpenSpec、Trellis、Mission、`to-prd` 或 `to-issues` 的目录结构和状态机。Workline 的核心判断是：需求澄清、任务拆分、执行记录和归档应当分开，避免一个大 skill 同时主导所有阶段。

## 源码结构

```text
workline/
├── README.md
├── workline-init/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── templates/brief.md
│   └── scripts/init_workline.py
├── workline-grill/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── templates/prd.md
├── workline-review/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── workline-tasks/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── templates/tasks.csv
│   └── scripts/workline_csv.py
├── workline-run/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── scripts/workline_csv.py
└── workline-archive/
    ├── SKILL.md
    └── agents/openai.yaml
```

## 六个 Skill

| Skill | 职责 | 交接点 |
| --- | --- | --- |
| `workline-init` | 创建 `.workline/active/<timestamp-slug>/`、带基础模板的 `brief.md` 和空的 `references/` | 交给 `$workline-grill` 澄清需求 |
| `workline-grill` | 读取 `brief.md` 和 `references/`，逐问逐答澄清需求并生成 `prd.md` | 交给 `$workline-tasks` 拆分任务 |
| `workline-review` | 可选审查 `prd.md` 或 `tasks.csv`，结论直接落到被审查对象里 | 结论为 `PASS` / `REVISE` / `BLOCKED` |
| `workline-tasks` | 根据 `prd.md` 拆分任务，生成并校验 `tasks.csv` | 交给 `/goal` + `$workline-run` 执行 |
| `workline-run` | 作为 `/goal` 执行规则包，约束任务选择、状态更新、日志和 REVIEW | 产出已更新的 `tasks.csv` 和 `run.md` |
| `workline-archive` | 确认闭环后，将活动目录移动到 archive | 归档核心过程文件 |

各 Skill 文档中的 `<SKILL_DIR>` 指该 SKILL.md 所在目录的绝对路径。Skill 安装位置随平台不同（`.claude/skills`、`.cursor`、`.codex` 等），命令示例一律不假设当前工作目录下存在 skill 源码目录。`workline-review` 和 `workline-archive` 自身不带脚本，它们复用 `workline-tasks` 或 `workline-run` 目录下的 `workline_csv.py`，两份实现等价。

脚本调不到时必须停止并报告，禁止跳过校验继续执行。

## 项目内目录

```text
.workline/
├── active/
│   └── 2026-05-28-0915-example/
│       ├── brief.md
│       ├── prd.md
│       ├── tasks.csv
│       ├── run.md
│       └── references/
└── archive/
    └── 2026-05/
        └── 2026-05-28-0915-example/
```

活动目录命名为 `YYYY-MM-DD-HHMM-brief-slug`，归档按年月分组。

`brief.md` 由 `$workline-init` 基于模板创建，脚本只填充创建时间和目录标题，其余内容由用户手动填写。`references/` 默认创建为空目录，用于 PRD / grill 阶段的输入材料：参考仓库软链接、旧实现、网页资料、协议文档、用户文件，以及外部 AI 或人工的审查意见。放入什么、为什么放，在 `brief.md` 的登记表里写清楚。

`evidence/` 是执行阶段的可选产物目录，只在任务自然产生构建日志、截图、配置快照、部署包、板端烟测记录等可复查产物时才创建，目录名为 `evidence/<任务 ID>-<短名>/`，内部结构自便，路径写进任务的 `refs`。

## CSV 状态源

`tasks.csv` 是执行阶段的唯一任务计划和状态源，固定表头为：

```csv
id,depends_on,mode,title,description,verification,state,commit,refs,notes
```

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID。普通任务使用 `T001` 这类稳定编号；最后一行固定为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个用空格分隔；普通任务不得依赖 `REVIEW`，`REVIEW` 行留空 |
| `mode` | `AFK` 表示可自动执行；`HITL` 表示需要人工输入、实机操作、账号权限或关键确认 |
| `title` | 一句话标识任务目标 |
| `description` | 要改什么、覆盖什么范围；验证命令覆盖不到的完成标准也写这里 |
| `verification` | 验证手段 + 期望结果，优先真实可执行命令；无法自动验证时写人工检查方式和判定标准 |
| `state` | 任务状态 |
| `commit` | 7–64 位十六进制提交哈希、`no-change` 或留空 |
| `refs` | PRD 章节、`references/...` 或 `evidence/...` |
| `notes` | 阻塞原因、跳过依据等短备注 |

`state` 枚举：

| 值 | 含义 | 满足后继依赖 |
| --- | --- | --- |
| `todo` | 未开始 | 否 |
| `doing` | 进行中，含验证失败后正在修 | 否 |
| `done` | 实现完成且验证通过，唯一成功终态 | 是 |
| `failed` | 验证已执行且未通过，当前暂停 | 否 |
| `blocked` | 条件不足无法继续 | 否 |
| `skipped` | 经用户确认或 PRD 允许跳过 | 是 |

`skipped` 是例外收口：只有用户确认或 PRD 明确允许时才可使用，且必须在 `notes` 和 `run.md` 中说明依据。它可以满足后续依赖，但不等同于已完成。

`commit` 不参与依赖判断，也不阻止后续任务继续执行，但归档前必须处理完。没有业务改动需要提交时写 `no-change`；提交成功写哈希；改动归属不清或提交失败时留空并在 `notes` 说明。

`REVIEW` 行必须是最后一行，`depends_on` 留空。它隐式依赖全部任务，中途新增任务不需要回来修改这一行。

## 校验与调度

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234
```

`validate` 检查结构：表头、状态枚举、`verification` 非空、`commit` 格式、依赖存在、普通任务不依赖 `REVIEW`、无自依赖、无依赖环、`REVIEW` 位置与空依赖。结构错误退出码为 1。

`next` 返回下一个可执行任务，附带 `on_complete` 收尾动作清单；没有可执行任务时返回 `reason`（`all-closed` 或 `needs-attention`）和逐任务的 `detail`。

`validate`、`set`、`next` 都会输出 `warnings`，这是系统侧的事后回查，不影响退出码：

| 代码 | 含义 |
| --- | --- |
| `commit-missing` | `state=done` 但 `commit` 为空 |
| `run-log-missing` | `state=done` 但 `run.md` 中没有对应的 `## <任务 ID>` 小节 |
| `exception-state` | 存在 `failed` / `blocked` / `skipped` 任务 |

`run-log-missing` 的作用是抓住"声称写了日志但其实没写"。文字提醒挡不住 AI 把待执行动作写成叙述，所以收尾是否真的完成由脚本回查判定，而不是由执行者自述。

## Git 提交

任务级提交由 `$workline-run` 在每条任务验证通过后自动尝试，提交范围限于当前任务相关的业务代码、测试、文档或配置文件。工作区里未经本次会话改动的脏文件不得静默纳入提交。

Workline 过程文件由 `$workline-archive` 在移动到 `.workline/archive/<YYYY-MM>/<slug>/` 后统一提交，只提交 `brief.md`、`prd.md`、`tasks.csv`、`run.md` 四个文件。`references/` 和 `evidence/` 作为过程材料保留在归档目录中。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-init/templates/brief.md` | `workline-init` | 生成 `brief.md` |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务 |

两份 `workline_csv.py` 是同步副本，必须逐字一致，文件头注释已标明这一点。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，手动填写 `brief.md`，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录，逐问逐答生成 `prd.md`，收尾时执行一次 PRD 收敛。
3. 使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，并运行 CSV 校验。
4. 使用 `/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv` 进入实现阶段。
5. 使用 `$workline-archive` 确认闭环后归档活动目录。

## 审查与多 AI 复核

阶段审查是可选步骤。用户主动要求审查 PRD、审查 `tasks.csv`、汇总人工意见或交给其它 AI 工具复核时，统一使用 `$workline-review`。

审查不产出独立报告文件：PRD 审查结论写入 `prd.md` 的"风险与待确认问题"和"关键决策与澄清记录"两张表，任务审查结论写入相应任务行的 `notes` 或直接修正任务定义。外部 AI 和人工的审查意见按输入材料对待，放在 `references/` 下供 `$workline-review` 汇总判断。

执行末尾的 `REVIEW` 行负责最终审计，`$workline-archive` 只在搬运前确认三条闭环条件。三者不重复承担同一职责。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。
