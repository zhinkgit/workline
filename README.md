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

| Skill | 职责 | 不做什么 |
| --- | --- | --- |
| `workline-init` | 创建 `.workline/active/<timestamp-slug>/`、`brief.md` 和 `references/` | 不追问、不写 PRD、不拆任务、不审查、不执行代码 |
| `workline-grill` | 读取 `brief.md` 和 `references/`，逐问逐答澄清需求并生成 `prd.md` | 不生成 `tasks.csv`，不执行代码 |
| `workline-review` | 可选审查 `prd.md` 或 `tasks.csv`，把阶段结论写入按需创建的 `reviews/` | 不实现代码，不把审查报告当作新需求源，不替代修订阶段 |
| `workline-tasks` | 只根据 `prd.md` 拆分任务，生成并校验 `tasks.csv` | 不实现代码，不把未确认问题伪装成任务 |
| `workline-run` | 作为 `/goal` 执行规则包，约束任务选择、状态更新、日志和 REVIEW | 不重新实现调度器，不替代 `/goal` |
| `workline-archive` | 检查过程文件闭环后，将活动目录移动到 archive | 不补做任务，不伪造日志，不覆盖归档目录 |

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

`references/` 默认保持浅层结构，只放进入 PRD / grill 阶段所需的输入材料，例如参考仓库软链接、旧实现、网页资料、协议文档和用户文件。它不再承载执行阶段产生的日志、截图、部署包或烟测记录。

`evidence/` 不是默认目录。只有 `$workline-run` 在执行阶段产生需要保留的过程物时才创建它，例如测试日志、构建日志、截图、配置快照、部署包、板端烟测记录。普通任务使用 `evidence/T003-config-manager/` 这类任务编号目录；多轮实机验证或多次尝试时，在任务目录下继续按尝试分组，例如：

```text
evidence/T012-board-check/
├── attempt-01-timeout/
├── attempt-02-new-ip/
└── smoke/
```

`tasks.csv` 的 `refs` 字段可以同时引用 `prd.md`、`references/...` 和 `evidence/...`。

执行证据应使用轻量标签标明证据等级。为了让 `summary` 可以稳定检查，机读证据标签必须写入 `tasks.csv` 的 `refs` 或 `notes`；如果存在过程物路径，也写入 `refs` 或 `notes`。`run.md` 只负责展开说明过程、命令输出和判断依据。推荐标签：

| 标签 | 含义 |
| --- | --- |
| `[evidence:local]` | 本地自动化测试、构建、静态检查或 dry-run |
| `[evidence:sim]` | mock、仿真、模拟协议或模拟外部依赖 |
| `[evidence:target]` | 已在目标环境或板端烟测，但未覆盖真实外设、真实服务或真实 ACK |
| `[evidence:real]` | 真实设备、真实服务、真实 ACK 或现场链路验证 |
| `[evidence:manual]` | 人工检查、截图复核、HITL 操作确认 |

同一任务可以有多个证据等级。证据等级只帮助复盘和审查，不替代 `tasks.csv` 状态字段。

`reviews/` 也不是默认目录。只有用户主动调用 `$workline-review`，或要求保存人工/其它 AI 审查意见时才创建。审查报告不是新的需求源；它只指出 `prd.md` 或 `tasks.csv` 是否需要回到上一个阶段修订。

## CSV 状态源

`tasks.csv` 是执行阶段的唯一任务计划和状态源，固定表头为：

```csv
id,depends_on,mode,title,description,acceptance_criteria,verification,dev_state,verify_state,git_state,refs,notes
```

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
- 工作区混有不相关改动、改动归属不清、提交失败或不是 Git 仓库：`git_state=blocked`，原因写入 `notes` 和 `run.md`。

`git_state=blocked` 不改变 `dev_state=done` / `verify_state=passed` 的验证结论，也不阻止继续执行后续任务，但归档前必须处理完。

`REVIEW` 行必须是最后一行，且依赖所有非 `REVIEW` 任务。它检查 PRD 覆盖、CSV 状态、验证记录、`run.md` 证据、失败/跳过解释和提交状态结论，不能补做实现任务。

三类检查的职责边界固定如下：

| 检查点 | 时间 | 结论载体 | 职责 |
| --- | --- | --- | --- |
| `$workline-review` | 用户主动要求复核时 | `reviews/*.md` | 可选阶段门禁，只判断是否能进入下一阶段 |
| `REVIEW` 行 | `/goal` 执行末尾 | `tasks.csv` + `run.md` | 最终审计，只检查执行闭环，不补做实现 |
| `$workline-archive` | 归档前 | 归档输出 | 搬运前核对，只确认闭环条件满足并移动目录 |

## 复盘摘要

`workline_csv.py summary` 用于快速复盘 `tasks.csv` 状态和证据质量。它只读取 `tasks.csv`，不写入文件，不成为新的状态源。

```bash
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv --json
```

默认输出给人阅读，`--json` 输出机器可读结果，方便 `$workline-review` 和 `$workline-archive` 复用。

`summary` 的 warnings 是提醒型体检结果，不让命令因为 warning 失败。它只读取 `tasks.csv`，因此 `[evidence:*]` 标签必须在 `refs` 或 `notes` 中出现；如果有过程物路径，也应在 `refs` 或 `notes` 中出现。真正是否 `PASS`、`REVISE`、`BLOCKED`，仍由 `$workline-review` 或 `$workline-archive` 根据 PRD、`tasks.csv`、`run.md`、`reviews/` 和证据上下文判断。

当前 warning 类型：

| Warning | 触发条件 |
| --- | --- |
| `missing-evidence-level` | 非 `REVIEW` 任务已 `done/passed`，但没有 `[evidence:*]` 标签 |
| `evidence-ref-without-level` | 引用了 `evidence/`，但没有 `[evidence:*]` 标签 |
| `hitl-without-manual-target-or-real-evidence` | `mode=HITL` 的终态任务没有 `manual`、`target` 或 `real` 证据标签 |
| `target-without-real` | 有 `target` 证据，但没有 `real` 证据 |
| `git-pending` | 非 `REVIEW` 终态任务 `git_state=pending` |
| `skipped-or-blocked` | 任务存在 `skipped`、`blocked` 或 `failed` 状态 |

## Git 提交

任务级提交由 `$workline-run` 在每条任务验证通过后自动尝试，只提交当前任务相关的业务代码、测试、文档或配置文件。任务级提交不提交 `.workline/active/...`、`.workline/archive/...`、`references/`、`evidence/` 或其它 Workline 过程材料。

Workline 过程文件由 `$workline-archive` 在移动到 `.workline/archive/<slug>/` 后统一提交，并且只提交以下四个文件：

- `.workline/archive/<slug>/brief.md`
- `.workline/archive/<slug>/prd.md`
- `.workline/archive/<slug>/tasks.csv`
- `.workline/archive/<slug>/run.md`

不提交 `references/`、`evidence/`、`reviews/`。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务、生成复盘摘要 |

两份 `workline_csv.py` 必须保持实现一致。修改其中一份时，直接同步另一份，并用文件哈希或 diff 确认一致后再分别运行校验。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录，逐问逐答生成 `prd.md`。
3. 使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，并运行 CSV 校验。
4. 使用 `/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv` 进入实现阶段。
5. 使用 `$workline-archive` 检查闭环后归档活动目录。

## 审查与多 AI 复核

阶段审查是可选步骤。用户主动要求审查 PRD、审查 `tasks.csv`、汇总人工意见或交给其它 AI 工具复核时，统一使用 `$workline-review`，并把审查报告写入活动目录的 `reviews/`。

人工审查意见也可以保存到 `reviews/`，再由 `$workline-review` 汇总判断。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。

