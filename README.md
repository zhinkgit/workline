# Workline

Workline 是一套独立、轻量、可审计的长任务工作流。它把一个粗略需求推进为可执行任务，再交给 `/goal` 按 `tasks.csv` 持续执行和恢复，最后把可复用的项目知识沉淀下来。

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
│   └── check_script_sync.py
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
    └── templates/
        ├── notes-index.md
        └── note.md
```

## 六个 Skill

| Skill | 职责 | 交接点 |
| --- | --- | --- |
| `workline-init` | 创建 `.workline/active/<timestamp-slug>/`、带基础模板的 `brief.md` 和空的 `references/` | 用户收集材料后交给 `$workline-grill` |
| `workline-grill` | 分诊需求规模、评估材料充分性、逐问逐答澄清并生成带 FR 编号的 `prd.md` | 交给 `$workline-tasks` 拆分任务 |
| `workline-review` | 独立复核 `prd.md` 或 `tasks.csv`，结论直接落到被审查对象里 | 结论为 `PASS` / `REVISE` / `BLOCKED` |
| `workline-tasks` | 根据 `prd.md` 拆分任务，生成并校验 `tasks.csv`，请求执行确认 | 用户确认后交给 `/goal` + `$workline-run` |
| `workline-run` | 作为 `/goal` 执行规则包，约束任务选择、材料加载、状态更新、日志和 REVIEW | 产出已更新的 `tasks.csv` 和 `run.md` |
| `workline-archive` | 确认闭环、沉淀知识到 `.workline/notes/`，再把活动目录移动到 archive | 归档核心过程文件和新增知识条目 |

各 Skill 文档中的 `<SKILL_DIR>` 指该 SKILL.md 所在目录的绝对路径。Skill 安装位置随平台不同（`.claude/skills`、`.cursor`、`.codex` 等），命令示例一律不假设当前工作目录下存在 skill 源码目录。

`workline-tasks`、`workline-run`、`workline-review` 各自带一份 `workline_csv.py`，三份必须逐字一致。`workline-review` 自带脚本是为了让它能被单独安装给另一个 agent 或另一个模型做独立复核。`workline-archive` 自身不带脚本，复用其它三者中的任意一份。

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

`brief.md` 由 `$workline-init` 基于模板创建，脚本只填充创建时间和目录标题，其余内容由用户手动填写。`references/` 默认创建为空目录，由用户主动放入 PRD / grill 阶段的输入材料：参考仓库软链接、旧实现、网页资料、协议文档、用户文件，以及外部 AI 或人工的审查意见。放入什么、为什么放，在 `brief.md` 的登记表里写清楚。

`evidence/` 是执行阶段的可选产物目录，只在任务自然产生构建日志、截图、配置快照、部署包、板端烟测记录等可复查产物时才创建，目录名为 `evidence/<任务 ID>-<短名>/`，内部结构自便，路径写进任务的 `refs`。

## 知识层

`.workline/notes/` 是跨任务复用的项目知识层，由 `$workline-archive` 在归档前写入，由 `$workline-grill` 在澄清开始时读取。

它和归档目录的分工：归档目录保留**过程记录**（这次做了什么、怎么验证的），notes 保留**结论**（本项目是怎样的、为什么）。新会话读 notes 就能快速了解代码库，不必翻二十份历史 PRD。

`index.md` 是发现面，一行一条：文件、主题、什么时候需要读。正文写在主题文件里，每条知识一个二级小节，包含结论、原因、适用范围和来源归档路径。

只沉淀同时满足三条的内容：跨任务复用、不是过程记录、有原因。没有值得沉淀的内容时明确说明，不为了填充而写。与已有条目冲突时停止询问，不静默覆盖。

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

`skipped` 是例外收口：只有用户确认或 PRD 明确允许时才可使用，且必须在 `notes` 和 `run.md` 中说明依据。它可以满足后续依赖，但不等同于已完成。

`commit` 不参与依赖判断，也不阻止后续任务继续执行，但归档前必须处理完。没有业务改动需要提交时写 `no-change`；提交成功写哈希；改动归属不清或提交失败时留空并在 `notes` 说明。

`REVIEW` 行必须是最后一行，`depends_on` 留空。它隐式依赖全部任务，中途新增任务不需要回来修改这一行。

## refs 是加载清单

`refs` 决定执行某条任务时加载哪些材料，不是自由文本备注。三类引用项，空格分隔：

| 形式 | 含义 |
| --- | --- |
| `FR-2` | `prd.md` 中 `### FR-2` 功能要求小节 |
| `references/proto-v2.md` | `references/` 下的输入材料 |
| `evidence/T001-smoke/` | 前序任务产物，由 `--append-refs` 追加 |

**不写源码路径。** 执行阶段的 agent 有搜索和读文件能力，源码它自己会找；`refs` 要给的是它不知道去哪找的东西——需求出处、协议文档、外部资料。把源码塞进 `refs` 只会挤占上下文。

`prd.md` 的功能要求必须写成 `### FR-<序号> <标题>` 三级小节，这样 `refs` 才能硬链接到需求。有了这条链接，"PRD 要求是否都有任务覆盖"就能由脚本回查，而不是靠执行者自述。

## 校验与调度

```bash
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py validate <tasks.csv> --allow-empty-refs
python <SKILL_DIR>/scripts/workline_csv.py next <tasks.csv>
python <SKILL_DIR>/scripts/workline_csv.py set <tasks.csv> T001 --state done --commit abc1234
```

`validate` 检查结构：表头、状态枚举、`verification` 非空、`commit` 格式、依赖存在、普通任务不依赖 `REVIEW`、无自依赖、无依赖环、`REVIEW` 位置与空依赖。结构错误退出码为 1。

`next` 返回下一个可执行任务，附带 `on_complete` 收尾动作清单；没有可执行任务时返回 `reason`（`all-closed` 或 `needs-attention`）和逐任务的 `detail`。

`set` 更新任务行。写入 `state=done` 时有两条**硬门禁**，不满足直接拒绝：

| 门禁 | 规则 |
| --- | --- |
| 日志 | `run.md` 中必须已有 `## <任务 ID>` 小节 |
| 提交 | `commit` 必须非空；无法提交时用 `--commit "" --notes "<原因>"` 显式说明 |

另有一条既有门禁：`todo` 不能直接跳到 `done`，必须先经过 `doing`。

这三条的共同判断是：**收尾是否真的完成由脚本判定，而不是由执行者自述。** 文字提醒挡不住 AI 把待执行动作写成叙述，所以把不变量交给机器执行，而不是交给记性。

## Warning 回查

`validate`、`set`、`next` 都会输出 `warnings`，这是系统侧的事后回查，不影响退出码：

| 代码 | 含义 | 谁该处理 |
| --- | --- | --- |
| `verification-weak` | `mode=AFK` 但 `verification` 中看不到可执行命令 | `$workline-tasks` 补命令或改 `HITL` |
| `refs-missing` | 任务 `refs` 为空，执行时无材料清单可加载 | `$workline-tasks` 补清单或用 `--allow-empty-refs` 豁免 |
| `fr-uncovered` | `prd.md` 的某条 FR 没被任何任务的 `refs` 引用 | `$workline-tasks` 补任务，或说明为什么不需要 |
| `commit-missing` | `state=done` 但 `commit` 为空 | `$workline-run` 补提交，`$workline-archive` 阻止归档 |
| `run-log-missing` | `state=done` 但 `run.md` 中没有对应的 `## <任务 ID>` 小节 | `$workline-run` 补日志，`$workline-archive` 阻止归档 |
| `exception-state` | 存在 `blocked` / `skipped` 任务 | 按 `notes` 判断能否继续 |

`verification-weak` 用启发式检测 `verification` 里有没有可执行命令的痕迹，会有漏判和误判，所以是 warning 不是硬错误。但它指向的问题是真的：`AFK` 意味着无人值守，验证如果不是机器可判定的，整条任务就变成了 AI 自我确认。看到这个 warning 时二选一——补上真实命令，或者承认它需要人判断改成 `HITL`。

## Git 提交

任务级提交由 `$workline-run` 在每条任务验证通过后自动尝试，提交范围限于当前任务相关的业务代码、测试、文档或配置文件。工作区里未经本次会话改动的脏文件不得静默纳入提交。生成提交信息前先看一眼 `git log --oneline -5`，融入仓库已有风格。

Workline 过程文件由 `$workline-archive` 在移动到 `.workline/archive/<YYYY-MM>/<slug>/` 后统一提交，范围是 `brief.md`、`prd.md`、`tasks.csv`、`run.md` 四个核心文件，加上本次新增或修改的 `.workline/notes/` 文件。`references/` 和 `evidence/` 作为过程材料保留在归档目录中。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-init/templates/brief.md` | `workline-init` | 生成 `brief.md` |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-archive/templates/notes-index.md` | `workline-archive` | 首次创建 `.workline/notes/index.md` |
| `workline-archive/templates/note.md` | `workline-archive` | 新建知识主题文件 |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务 |
| `workline-review/scripts/workline_csv.py` | `workline-review` | 独立复核时校验 CSV |

三份 `workline_csv.py` 是同步副本，必须逐字一致。这条约束不靠注释和记性维持，发布前运行：

```bash
python tools/check_script_sync.py
```

副本不一致时退出码为 1，并列出各份的哈希。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，手动填写 `brief.md`，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录。它先分诊需求规模、评估材料是否够用并指出缺口，材料齐备后逐问逐答生成 `prd.md`，收尾时执行一次 PRD 收敛。
3. 使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，运行 CSV 校验并处理全部 warning，然后请求执行确认。
4. 确认后使用 `/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv` 进入实现阶段。
5. 使用 `$workline-archive` 确认闭环、沉淀知识、归档活动目录。

## 三道确认门

Workline 有三个必须由用户参与的转换点，不是可选礼节：

| 门 | 位置 | 为什么必需 |
| --- | --- | --- |
| 材料确认 | grill 评估材料充分性之后 | 材料不足时开始澄清，会把本该由文件回答的问题变成向用户提问 |
| 执行确认 | tasks 交付之后、`/goal` 之前 | 用户最初说“帮我实现 X”是需求描述，不是执行许可。必须在**看过任务表之后**再确认一次 |
| 归档确认 | archive 检查出缺口时 | 闭环条件不满足就停止，不搬运 |

## 审查与多 AI 复核

阶段审查使用 `$workline-review`。它自带校验脚本，设计上可以单独安装给另一个 agent 或另一个模型，做不带原作者偏见的独立复核。

审查不产出独立报告文件：PRD 审查结论写入 `prd.md` 的“风险与待确认问题”和“关键决策与澄清记录”两张表，任务审查结论写入相应任务行的 `notes` 或直接修正任务定义。外部 AI 和人工的审查意见按输入材料对待，放在 `references/` 下供 `$workline-review` 汇总判断。

执行末尾的 `REVIEW` 行负责最终审计和知识沉淀候选的提取，`$workline-archive` 在搬运前确认三条闭环条件并写入知识层。三者不重复承担同一职责。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。
