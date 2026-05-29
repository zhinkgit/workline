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
│   ├── agents/openai.yaml
│   └── templates/review.md
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
| `workline-review` | 可选审查 `prd.md` 或 `tasks.csv`，把阶段结论写入按需创建的 `reviews/` | 结论为 `PASS` / `REVISE` / `BLOCKED` |
| `workline-tasks` | 根据 `prd.md` 拆分任务，生成并校验 `tasks.csv` | 交给 `/goal` + `$workline-run` 执行 |
| `workline-run` | 作为 `/goal` 执行规则包，约束任务选择、状态更新、日志和 REVIEW | 产出已更新的 `tasks.csv` 和 `run.md` |
| `workline-archive` | 检查过程文件闭环后，将活动目录移动到 archive | 归档核心过程文件 |

## 项目内目录

```text
.workline/
├── active/
│   └── 2026-05-28-0915-example/
│       ├── brief.md
│       ├── prd.md
│       ├── tasks.csv
│       ├── run.md
│       └── references/          # PRD / grill 输入材料
└── archive/
    └── 2026-05-28-0915-example/
```

活动目录命名为 `YYYY-MM-DD-HHMM-brief-slug`。

`brief.md` 由 `$workline-init` 基于 `workline-init/templates/brief.md` 创建，模板文件是文档结构的真相源；脚本只填充运行时占位符，例如任务目录标题和创建时间。模板中的用户内容主要由用户手动填写。`references/` 默认创建为空目录并保持浅层结构，用于 PRD / grill 阶段输入材料，例如参考仓库软链接、旧实现、网页资料、协议文档和用户文件。

`evidence/` 是执行阶段的可选过程物目录，用于保存测试日志、构建日志、截图、配置快照、部署包、板端烟测记录。普通任务使用 `evidence/T003-config-manager/` 这类任务编号目录；多轮实机验证或多次尝试时，在任务目录下继续按尝试分组，例如：

```text
evidence/T012-board-check/
├── attempt-01-timeout/
├── attempt-02-new-ip/
└── smoke/
```

`tasks.csv` 的 `refs` 字段可以同时引用 `prd.md`、`references/...` 和 `evidence/...`。验证命令、人工检查动作、真实输出摘要和未覆盖范围写入 `run.md`，必要的短备注写入 `notes`。如果存在过程物路径，也写入 `refs`、`notes` 或 `run.md`。

`reviews/` 用于保存 `$workline-review`、人工审查或其它 AI 审查意见。审查报告提供阶段质量反馈，需求源仍是 `prd.md`。

## CSV 状态源

`tasks.csv` 是执行阶段的唯一任务计划和状态源，固定表头为：

```csv
id,depends_on,mode,title,description,acceptance_criteria,verification,dev_state,verify_state,git_state,refs,notes
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID。普通任务使用 `T001` 这类稳定编号；最后一行固定为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个 ID 用空格分隔；依赖满足后任务才可进入执行 |
| `mode` | 执行模式。`AFK` 表示可自动执行；`HITL` 表示需要人工输入、实机操作、账号权限或关键确认 |
| `title` | 任务标题，用一句话标识任务目标 |
| `description` | 任务说明，写清要改什么、覆盖什么范围 |
| `acceptance_criteria` | 验收标准，描述什么结果才算完成 |
| `verification` | 验证方式，优先写真实可执行命令；无法自动验证时写人工检查方式 |
| `dev_state` | 开发状态，表示实现侧进度 |
| `verify_state` | 验证状态，表示验收或检查结果 |
| `git_state` | 提交收口状态，只记录任务相关业务改动是否已提交、无需提交或被阻塞 |
| `refs` | 相关引用，可指向 PRD 章节、`references/...` 输入材料或 `evidence/...` 运行产物 |
| `notes` | 备注，记录阻塞原因、跳过依据、验证摘要、提交哈希等短信息 |

状态枚举：

| 字段 | 允许值 |
| --- | --- |
| `dev_state` | `todo`、`doing`、`done`、`blocked`、`skipped` |
| `verify_state` | `pending`、`passed`、`failed`、`blocked`、`skipped` |
| `git_state` | `pending`、`done`、`blocked` |

正常任务闭环条件是：

```text
dev_state = done
verify_state = passed
```

`skipped` 是例外收口：只有用户确认或 PRD 明确允许时才可使用，且必须在 `notes` 和 `run.md` 中说明依据。`skipped` 可以满足后续依赖，但不等同于已完成。

`git_state` 不参与任务依赖满足判断，也不影响后续任务继续执行。每个任务验证通过后，`$workline-run` 会自动尝试提交本任务的业务改动：

- 没有业务改动需要提交：`git_state=done`。
- 已成功提交任务相关业务改动：`git_state=done`，提交哈希写入 `notes` 或 `run.md`。
- 工作区混有不相关改动、改动归属不清、提交失败或当前目录无 Git 仓库：`git_state=blocked`，原因写入 `notes` 和 `run.md`。

`git_state=blocked` 不改变 `dev_state=done` / `verify_state=passed` 的验证结论，也不阻止继续执行后续任务，但归档前必须处理完。

`REVIEW` 行必须是最后一行，且依赖所有非 `REVIEW` 任务。它检查 PRD 覆盖、CSV 状态、验证记录、`run.md` 验证说明、失败/跳过解释和提交状态结论。

三类检查的职责边界固定如下：

| 检查点 | 时间 | 结论载体 | 职责 |
| --- | --- | --- | --- |
| `$workline-review` | 用户主动要求复核时 | `reviews/*.md` | 可选阶段门禁，只判断是否能进入下一阶段 |
| `REVIEW` 行 | `/goal` 执行末尾 | `tasks.csv` + `run.md` | 最终审计，检查执行闭环 |
| `$workline-archive` | 归档前 | 归档输出 | 搬运前核对，只确认闭环条件满足并移动目录 |

## 状态快照

`workline_csv.py summary` 是可选状态快照工具，用于快速查看 `tasks.csv` 的状态分布。它只读取 `tasks.csv`，状态源仍然是原 CSV 文件。

```bash
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv --json
```

默认输出给人阅读，`--json` 输出机器可读结果。需要快速了解任务状态时运行它。

验证质量和阶段结论由 `$workline-review` 或 `$workline-archive` 根据 PRD、`tasks.csv`、`run.md`、`reviews/` 和实际验证上下文判断。

## Git 提交

任务级提交由 `$workline-run` 在每条任务验证通过后自动尝试，提交范围限于当前任务相关的业务代码、测试、文档或配置文件。

Workline 过程文件由 `$workline-archive` 在移动到 `.workline/archive/<slug>/` 后统一提交，并且只提交以下四个文件：

- `.workline/archive/<slug>/brief.md`
- `.workline/archive/<slug>/prd.md`
- `.workline/archive/<slug>/tasks.csv`
- `.workline/archive/<slug>/run.md`

`references/`、`evidence/`、`reviews/` 作为过程材料保留在归档目录中。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-init/templates/brief.md` | `workline-init` | 生成 `brief.md` |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务、按需生成状态快照 |

两份 `workline_csv.py` 必须保持实现一致。修改其中一份时，直接同步另一份，并用文件哈希或 diff 确认一致后再分别运行校验。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，手动填写 `brief.md`，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录，逐问逐答生成 `prd.md`。
3. 使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，并运行 CSV 校验。
4. 使用 `/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv` 进入实现阶段。
5. 使用 `$workline-archive` 检查闭环后归档活动目录。

## 审查与多 AI 复核

阶段审查是可选步骤。用户主动要求审查 PRD、审查 `tasks.csv`、汇总人工意见或交给其它 AI 工具复核时，统一使用 `$workline-review`，并把审查报告写入活动目录的 `reviews/`。

人工审查意见也可以保存到 `reviews/`，再由 `$workline-review` 汇总判断。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。

