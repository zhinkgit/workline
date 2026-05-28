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

## 五个 Skill

| Skill | 职责 | 不做什么 |
| --- | --- | --- |
| `workline-init` | 创建 `.workline/active/<timestamp-slug>/`、`brief.md` 和 `references/` | 不追问、不写 PRD、不拆任务、不执行代码 |
| `workline-grill` | 读取 `brief.md` 和 `references/`，逐问逐答澄清需求并生成 `prd.md` | 不生成 `tasks.csv`，不执行代码 |
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
│       └── references/
└── archive/
    └── 2026-05-28-0915-example/
```

活动目录命名为 `YYYY-MM-DD-HHMM-brief-slug`。`references/` 默认保持浅层结构，用来放参考仓库软链接、旧实现、网页资料、协议文档、用户文件，以及执行过程中产生的中间产物。多个关联产物可放入 `references/T003-build/` 这类任务编号目录。

## CSV 状态源

`tasks.csv` 是执行阶段的唯一任务计划和状态源，固定表头为：

```csv
id,depends_on,mode,title,description,acceptance_criteria,verification,dev_state,review_state,git_state,refs,notes
```

状态枚举：

| 字段 | 允许值 |
| --- | --- |
| `dev_state` | `todo`、`doing`、`done`、`blocked`、`skipped` |
| `review_state` | `pending`、`passed`、`failed`、`blocked`、`skipped` |
| `git_state` | `pending`、`committed`、`not_needed`、`blocked`、`skipped` |

任务闭环条件是：

```text
dev_state = done
review_state = passed
```

`git_state` 不参与任务依赖满足判断，但归档前必须说明每条任务的最终提交状态。

`REVIEW` 行必须是最后一行，且依赖所有非 `REVIEW` 任务。它检查 PRD 覆盖、CSV 状态、验证记录、`run.md` 证据、失败/跳过解释和提交状态结论，不能补做实现任务。

## 模板和脚本

每个 Skill 尽量自包含，不依赖顶层共享脚本目录：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |
| `workline-init/scripts/init_workline.py` | `workline-init` | 初始化活动目录 |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 任务拆分后校验 CSV |
| `workline-run/scripts/workline_csv.py` | `workline-run` | 执行阶段校验、更新 CSV、定位下一任务 |

两份 `workline_csv.py` 必须保持实现一致。修改其中一份时，直接同步另一份并分别运行校验。

## 推荐步骤

1. 使用 `$workline-init` 创建活动目录，并把参考资料放进 `references/`。
2. 使用 `$workline-grill` 读取活动目录，逐问逐答生成 `prd.md`。
3. 使用 `$workline-tasks` 只根据 `prd.md` 生成 `tasks.csv`，并运行 CSV 校验。
4. 使用 `/goal 根据 $workline-run 规范 执行 .workline/active/<slug>/tasks.csv` 进入实现阶段。
5. 使用 `$workline-archive` 检查闭环后归档活动目录。

Workline 不混用其它规划工作流。若项目已有测试、构建或提交规范，执行阶段继续遵守项目自身规范。
