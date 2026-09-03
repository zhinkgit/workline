# Workline

Workline 是一套独立、轻量、可审计的长任务工作流。它把一个粗略需求推进为可执行任务，再按 `tasks.csv` 持续执行和恢复，最后把可复用的项目知识沉淀下来。

它刻意不复用 OpenSpec、Trellis、Mission、`to-prd` 或 `to-issues` 的目录结构和状态机。Workline 的核心判断是：需求澄清、任务拆分、执行记录和归档应当分开，避免一个大 skill 同时主导所有阶段。

四条设计原则贯穿全流程：

1. **物料先于提问**。完成任务所需的材料由用户主动收集，澄清阶段先评估够不够，再决定问什么。
2. **决策要核对**。能查证的自己查，只问仓库永远回答不了的判断；现有做法是候选方案，不是决策。
3. **每步可验证**。任务拆到能单独实现、单独验证、单独记录状态，无人值守任务的验证必须机器可判定。
4. **结论要沉淀**。过程记录进归档，可复用的项目约定和坑进 `.workline/notes/`，供新会话直接读取。

## 源码结构

```text
workline/
├── README.md
├── tools/
│   ├── check_script_sync.py
│   └── test_workline_csv.py
├── workline-init/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── templates/brief.md
│   ├── templates/run.md
│   └── scripts/init_workline.py
├── workline-grill/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── templates/prd.md
├── workline-review/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── scripts/workline_csv.py
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
    ├── agents/openai.yaml
    ├── scripts/workline_csv.py
    └── templates/
        ├── notes-index.md
        └── note.md
```

## 六个 Skill

| Skill | 职责 | 交接点 |
| --- | --- | --- |
| `workline-init` | 创建 `.workline/active/<timestamp-slug>/`、`brief.md`、带「阶段门禁」的 `run.md` 和空的 `references/` | 用户收集材料后交给 `$workline-grill` |
| `workline-grill` | 分诊需求规模、评估材料充分性、逐问逐答澄清并生成带 FR/NFR 编号的 `prd.md` | 必须交给 `$workline-review` 审查 PRD |
| `workline-review` | 独立复核 `prd.md` 或 `tasks.csv`，结论写入 `run.md` 的「阶段门禁」 | 必审一次；换 agent 再审是可选的第二次 |
| `workline-tasks` | 在 `prd-review=PASS` 之后拆分任务，生成并校验 `tasks.csv` | 必须交给 `$workline-review` 审查任务表 |
| `workline-run` | 在 `tasks-review=PASS` 且 `execute=CONFIRMED` 之后按 CSV 执行 | 产出已更新的 `tasks.csv` 和 `run.md` |
| `workline-archive` | `archive-check` 通过后沉淀知识，再把活动目录移动到 archive | 归档核心过程文件和新增知识条目 |

各 Skill 文档中的 `<SKILL_DIR>` 指该 SKILL.md 所在目录的绝对路径。Skill 安装位置随平台不同（`.claude/skills`、`.cursor`、`.codex` 等），命令示例一律不假设当前工作目录下存在 skill 源码目录。

`workline-tasks`、`workline-run`、`workline-review`、`workline-archive` 各自带一份 `workline_csv.py`，四份必须逐字一致。`workline-review` 自带脚本，是为了换一个 agent 做额外他审时仍能单独安装。`workline-archive` 自带脚本，是为了搬运前的硬检查不依赖其它 skill。

脚本调不到时必须停止并报告，禁止跳过校验继续执行。

## 项目内目录

```text
.workline/
├── notes/
│   ├── index.md
│   └── <主题>.md
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

活动目录命名为 `YYYY-MM-DD-HHMM-brief-slug`，归档按年月分组。slug 由粗需求自动生成，支持中英文混合，在词边界截断到 40 字符以内；`--slug` 显式指定时优先使用它。

`brief.md` 由 `$workline-init` 基于模板创建，脚本只填充创建时间和目录标题，其余内容由用户手动填写。`run.md` 同时创建，内含「阶段门禁」表，四扇门初始为未确认 / 未审查。`references/` 默认创建为空目录，由用户主动放入 PRD / grill 阶段的输入材料。放入什么、为什么放，在 `brief.md` 的登记表里写清楚。

`evidence/` 是执行阶段的可选产物目录，只在任务自然产生构建日志、截图、配置快照、部署包、板端烟测记录等可复查产物时才创建，目录名为 `evidence/<任务 ID>-<短名>/`，内部结构自便，路径写进任务的 `refs`。

## 知识层

`.workline/notes/` 是跨任务复用的项目知识层，由 `$workline-archive` 在归档前写入，由 `$workline-grill` 在澄清开始时读取。

它和归档目录的分工：归档目录保留**过程记录**（这次做了什么、怎么验证的），notes 保留**结论**（本项目是怎样的、为什么）。新会话读 notes 就能快速了解代码库，不必翻二十份历史 PRD。

`index.md` 是发现面，一行一条：文件、主题、什么时候需要读。正文写在主题文件里，每条知识一个二级小节，包含结论、原因、适用范围和来源归档路径。

只沉淀同时满足三条的内容：跨任务复用、不是过程记录、有原因。没有值得沉淀的内容时明确说明，不为了填充而写。与已有条目冲突时停止询问，不静默覆盖。

## 阶段门禁

阶段转换状态写在 `run.md` 的 `## 阶段门禁` 表里，不另建文件。它和 `tasks.csv` 分开，也不会被 PRD 收敛冲掉。执行阶段只往 `run.md` 后面追加任务日志，不得改这一节。

```md
## 阶段门禁

| 门 | 状态 | 时间 | 审查方 | 备注 |
| --- | --- | --- | --- | --- |
| materials | 未确认 |  |  |  |
| prd-review | 未审查 |  |  |  |
| tasks-review | 未审查 |  |  |  |
| execute | 未确认 |  |  |  |
```

| 门 | 允许的状态 | 谁写入 | 谁检查 |
| --- | --- | --- | --- |
| `materials` | `未确认` / `CONFIRMED` / `WAIVED` | `$workline-grill` | `$workline-tasks`、`$workline-archive` |
| `prd-review` | `未审查` / `PASS` / `REVISE` / `BLOCKED` | `$workline-review` | `$workline-tasks`、`$workline-archive` |
| `tasks-review` | `未审查` / `PASS` / `REVISE` / `BLOCKED` | `$workline-review` | `$workline-run`、`$workline-archive` |
| `execute` | `未确认` / `CONFIRMED` | `$workline-review` 或 `$workline-run` | `$workline-run`、`$workline-archive` |

`$workline-review` 有两种用法：grill 之后和 tasks 之后各**必审一次**（当前会话即可）；用户如果还想换一个 agent 再审，再调一次，后写覆盖先写。`prd-review` 写成 `PASS` 时，脚本默认重置 `tasks-review` 和 `execute`。只有 PRD 加审且正文未改时才用 `--keep-downstream`。

对话里说 `PASS` 不算过门。下一阶段只认 `run.md` 的「阶段门禁」。

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
| `title` | 一句话标识任务目标，必填 |
| `description` | 要改什么、覆盖什么范围；验证命令覆盖不到的完成标准也写这里 |
| `verification` | 验证手段 + 期望结果；AFK 任务的命令必须用反引号包裹 |
| `state` | 任务状态 |
| `commit` | 7–64 位十六进制提交哈希、`no-change` 或留空 |
| `refs` | 本任务的材料加载清单 |
| `notes` | 阻塞原因、跳过依据等短备注 |

`state` 枚举：

| 值 | 含义 | 满足后继依赖 |
| --- | --- | --- |
| `todo` | 未开始 | 否 |
| `doing` | 进行中，含验证失败后正在修 | 否 |
| `done` | 实现完成且验证通过，唯一成功终态 | 是 |
| `blocked` | 验证未通过或条件不足，当前暂停；属于哪种情况写在 `notes` | 否 |
| `skipped` | 经用户确认或 PRD 允许跳过 | 是 |

`skipped` 是例外收口：只有用户确认或 PRD 明确允许时才可使用，且必须在 `notes` 和 `run.md` 中说明依据。它可以满足后续依赖，但不等同于已完成。依赖被跳过的后继任务会得到 `skipped-unblocks` warning。

`done` 和 `skipped` 是终态，回退必须 `set --force`。

`commit` 不参与依赖判断。哈希必须能在本仓库 `git cat-file` 中核验；编造的哈希会被拒绝。没有业务改动写 `no-change`。`done` 但日志不完整、或 commit 为空且没有 notes 时，`validate` / `next` 直接失败。commit 为空但 notes 已说明原因时允许继续执行，`archive-check` 仍会拒绝归档。

`REVIEW` 行必须是最后一行，`depends_on` 留空。它隐式依赖全部任务，中途新增任务不需要回来修改这一行。新增任务用 `add` 子命令，不要手改 CSV。

## refs 是加载清单

`refs` 决定执行某条任务时加载哪些材料，不是自由文本备注。只允许三类，空格分隔：

| 形式 | 含义 |
| --- | --- |
| `FR-2` / `NFR-1` | `prd.md` 中对应要求小节 |
| `references/proto-v2.md` | `references/` 下的输入材料 |
| `evidence/T001-smoke/` | 前序任务产物，由 `--append-refs` 追加 |

**不写源码路径。** 执行阶段的 agent 有搜索和读文件能力，源码它自己会找；`refs` 要给的是它不知道去哪找的东西。非法项会得到 `refs-invalid`。

`prd.md` 的功能要求必须写成 `### FR-<序号> <标题>`，需要单独拆任务的非功能要求写成 `### NFR-<序号> <标题>`。不要用项目符号代替这些标题，否则覆盖性检查不会运行。

## 校验与调度

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv> --allow-empty-refs
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234def56
python <SKILL_DIR>/scripts/workline_csv.py add <tasks.csv> T012 --mode AFK --title "..." --description "..." --verification "`pytest`" --refs "FR-2"
python <SKILL_DIR>/scripts/workline_csv.py gates <active-dir>
python <SKILL_DIR>/scripts/workline_csv.py gates-set <active-dir> --gate prd-review --status PASS --actor same-session
python <SKILL_DIR>/scripts/workline_csv.py require-gates <active-dir> --require prd-review=PASS
python <SKILL_DIR>/scripts/workline_csv.py archive-check <tasks.csv>
```

`validate` 检查结构：表头、状态枚举、标题/描述/验证非空、`commit` 格式、依赖存在、普通任务不依赖 `REVIEW`、无自依赖、无依赖环、`REVIEW` 位置与空依赖。`state=done` 时还硬检查：`run.md` 对应小节含非空的「实现 / 验证 / 输出」；commit 为空且无 notes 会失败；非 `no-change` 的哈希必须存在于 git。结构或收口错误退出码为 1。

`next` 在可执行任务里优先返回 AFK，避免 HITL 等人挡住独立的自动任务。返回对象带 `hitl` 和 `on_complete`。没有可执行任务时返回 `reason`（`all-closed` 或 `needs-attention`）。

`set` 写入 `state=done` 时有硬门禁：完整日志、可核验的 commit。`todo` 不能直接跳到 `done`。离开 `done` / `skipped` 必须 `--force`。

## Warning 回查

`validate`、`set`、`next` 都会输出 `warnings`，不影响退出码：

| 代码 | 含义 | 谁该处理 |
| --- | --- | --- |
| `verification-weak` | `mode=AFK` 但 `verification` 里没有反引号命令 | `$workline-tasks` 补命令或改 `HITL` |
| `refs-missing` | 任务 `refs` 为空 | `$workline-tasks` 补清单或用 `--allow-empty-refs` |
| `refs-invalid` / `refs-not-found` / `req-id-padded` | refs 非法、文件不存在或编号带前导零 | `$workline-tasks` 改正 |
| `fr-headings-missing` | PRD 功能要求没有 `### FR-N` | `$workline-grill` 补编号 |
| `fr-uncovered` / `nfr-uncovered` | PRD 的某条 FR/NFR 没被任何任务引用 | `$workline-tasks` 补任务 |
| `exception-state` | 存在 `blocked` / `skipped` 任务 | 按 `notes` 判断能否继续 |
| `skipped-unblocks` | 后继依赖被跳过的任务 | 确认不是空地基施工 |
| `worktree-dirty` | 工作区有非 `.workline` 的脏文件 | 任务级提交不要捎上 |

`verification-weak` 只认反引号里的命令，避免 “检查 python 代码” 或 “make sure” 被当成可执行验证。

## Git 提交

任务级提交由 `$workline-run` 在每条任务验证通过后自动尝试，提交范围限于当前任务相关的业务代码、测试、文档或配置文件。**不要暂存 `.workline/`。** 工作区里未经本次任务改动的脏文件不得静默纳入提交。生成提交信息前先看一眼 `git log --oneline -5`，融入仓库已有风格。

Workline 过程文件由 `$workline-archive` 在移动到 `.workline/archive/<YYYY-MM>/<slug>/` 后统一提交，范围是 `brief.md`、`prd.md`、`tasks.csv`、`run.md`，加上本次新增或修改的 `.workline/notes/` 文件。`references/` 和 `evidence/` 作为过程材料保留在归档目录中。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-init/templates/brief.md` | `workline-init` | 生成 `brief.md` |
| `workline-init/templates/run.md` | `workline-init` | 生成带阶段门禁的 `run.md` |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-archive/templates/notes-index.md` | `workline-archive` | 首次创建 `.workline/notes/index.md` |
| `workline-archive/templates/note.md` | `workline-archive` | 新建知识主题文件 |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务 |
| `workline-review/scripts/workline_csv.py` | `workline-review` | 独立复核时校验 CSV 并写门禁 |
| `workline-archive/scripts/workline_csv.py` | `workline-archive` | 归档前硬检查 |

四份 `workline_csv.py` 是同步副本，必须逐字一致。这条约束不靠注释和记性维持，发布前运行：

```bash
python tools/check_script_sync.py
python tools/test_workline_csv.py
```

副本不一致或测试失败时退出码为 1。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，手动填写 `brief.md`，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录。它先分诊、评估材料并写入 `materials` 门禁，再逐问逐答生成 `prd.md`，收尾时执行一次 PRD 收敛。
3. **必须**使用 `$workline-review` 审查 `prd.md`，把结论写入 `prd-review`。同一会话跑即可。
4. `PASS` 后使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，运行 CSV 校验并处理全部 warning。
5. **必须**使用 `$workline-review` 审查 `tasks.csv`，把结论写入 `tasks-review`。`PASS` 后再请求执行确认，写入 `execute`。
6. 确认后按 `$workline-run` 执行 `.workline/active/<slug>/tasks.csv`。有 `/goal` 的环境可以把这条作为 `/goal` 提示。
7. 使用 `$workline-archive` 跑 `archive-check`、沉淀知识、归档活动目录。

步骤 3 和 5 还可以再换一个 agent 调用一次 `$workline-review`。那是加审，不是替代必审。

## 用户必须参与的转换点

这些不是可选礼节。除材料确认外，审查结论和执行确认都落在 `run.md` 的「阶段门禁」：

| 门 | 位置 | 为什么必需 |
| --- | --- | --- |
| 材料确认 | grill 评估材料充分性之后 | 材料不足时开始澄清，会把本该由文件回答的问题变成向用户提问 |
| PRD 必审 | grill 之后、tasks 之前 | 同一 agent 写 PRD 不能自己宣布可以拆任务 |
| 任务必审 | tasks 之后、执行之前 | 任务表必须被当作审查对象看过一遍 |
| 执行确认 | 任务审查 PASS 之后 | 用户最初说“帮我实现 X”是需求描述，不是执行许可 |

## 审查与多 AI 复核

阶段必审和使用另一个模型加审，用的是同一个 `$workline-review`。它自带校验脚本，可以单独安装。

审查不产出独立报告文件：修订点写入 `prd.md` 或任务行，阶段结论写入 `run.md` 的「阶段门禁」。外部 AI 和人工的审查意见按输入材料对待，放在 `references/` 下。

执行末尾的 `REVIEW` 行负责最终审计和知识沉淀候选的提取，`$workline-archive` 在搬运前用 `archive-check` 确认闭环并写入知识层。三者不重复承担同一职责。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。
