# PRD: Workline 简洁长任务工作流

## 1. 背景

当前已经尝试过 OpenSpec、Trellis、Mission、外部 CSV 执行流等多种工作流，但它们存在几个共同问题：

- 流程偏重，容易让工具模型反过来主导需求表达。
- 需求澄清、任务拆分、执行验证、归档之间边界不够清楚。
- 计划文档过复杂时，反而降低执行质量。
- 单个大 skill 容易把 grill、PRD、任务拆分、执行和归档耦合在一起，后续难维护。
- 长任务执行需要可恢复状态源，单纯 Markdown checklist 不够稳定。

因此需要一个独立、轻量、可审计的工作流：先对齐需求，再拆成可验证任务，再通过 `/goal` 长任务执行，最后归档过程文件。

## 2. 产品目标

Workline 的目标是提供一套“简洁但必要”的长任务工作流，使一个粗略需求可以稳定推进到完成：

1. 先初始化一个可手工填充的工作目录，避免在没有材料入口时直接追问。
2. 通过 grill 式逐问逐答澄清需求。
3. 生成一份简洁但足够明确的 PRD。
4. 根据 PRD 拆分出可单独验证的任务。
5. 生成 `tasks.csv`，同时作为人类审阅文件和 `/goal` 执行状态源。
6. 执行阶段必须真实实现、真实调试、真实验证，并持续更新 CSV 状态。
7. 完成后归档 PRD、任务、执行日志、REVIEW 结论、参考资料和运行产物。

## 3. 非目标

Workline 不做以下事情：

- 不复用 OpenSpec、Trellis、Mission、`to-prd`、`to-issues` 的目录结构、状态机或执行模型。
- 不做一个大而全的单 skill。
- 不替代项目自身的测试、构建、提交规范。
- 不在执行阶段重新解释目标、功能要求或验收标准。
- 不为了状态闭环而隐藏失败、跳过验证或伪造通过。

## 4. 用户与使用场景

主要用户是希望让 Codex 长时间执行复杂任务的个人开发者。

典型场景：

- 有一个模糊需求，需要先被追问清楚。
- 希望先创建一个固定过程目录，再手工补充初始需求和参考资料。
- 需求比较复杂，不希望 agent 直接开写代码。
- 想把 PRD 拆成一条条可以验证的小任务。
- 希望 `/goal` 能根据 CSV 状态持续执行和恢复。
- 需要保留过程文档和运行产物，方便复盘、归档或交给另一个 agent。
- 经常需要放参考代码库软链接、旧实现、网页资料、协议文档或任务执行产物。

## 5. 核心设计

Workline 是一个独立工作流目录。

源码结构：

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

设计原则：

- 每个 Skill 尽量自包含，避免依赖顶层共享脚本目录。
- `prd.md` 模板归 `workline-grill`，因为 PRD 是 grill 阶段产物。
- `tasks.csv` 模板归 `workline-tasks`，因为任务 CSV 是 tasks 阶段产物。
- `workline_csv.py` 在 `workline-tasks` 和 `workline-run` 下各保留一份：前者用于生成后校验，后者用于 `/goal` 执行期间校验、更新和恢复。
- 两份 `workline_csv.py` 必须保持实现一致；修改其中一份时必须直接同步另一份。

项目内过程目录最终形态：

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

活动目录命名格式为 `YYYY-MM-DD-HHMM-brief-slug`，避免同一天多个任务重名。

`references/` 默认只保留一级目录，用于放参考仓库软链接、旧代码、网页资料、协议文档、用户提供的文件，以及运行过程中产生的中间产物或验证产物。若某个任务产生多个关联文件，允许创建按任务编号命名的浅层目录，例如 `references/T003-build/`，避免把多文件产物摊平成一堆难追踪文件。

输入资料的来源、用途和是否需要归档，记录在 `prd.md` 末尾的“参考资料记录”章节中，不额外增加 `references.md`。运行过程中产生的 build log、截图、验证结果、临时文件和其它产物，不写入 `prd.md`；应登记到 `run.md`，必要时在 `tasks.csv` 的 `refs` 字段中引用。

## 6. Skill 划分

### 6.1 workline-init

职责：

- 接收用户粗需求。
- 创建 `.workline/active/<timestamp-slug>/`。
- 创建 `brief.md`，写入用户原始粗需求、创建时间和待补充材料提示，供用户继续手工补充。
- 创建一级 `references/`。
- 返回新建活动目录路径，提示用户把参考资料、旧代码、协议文档或其它输入材料放入 `references/`。

硬约束：

- 不生成 `prd.md`。
- 不生成 `tasks.csv`。
- 不执行代码。
- 不主动追问需求。
- 不调用其它规划工作流。
- 不覆盖已有活动目录。

### 6.2 workline-grill

职责：

- 读取用户指定的活动目录。
- 读取 `brief.md` 和 `references/`。
- 使用 `workline-grill/templates/prd.md` 作为 PRD 模板。
- 通过逐问逐答澄清需求。
- 将澄清结论、关键决策和必要问答写入 `prd.md`。
- 补充 `prd.md` 末尾的“参考资料记录”。

硬约束：

- `brief.md` 和 `references/` 是澄清阶段的输入材料；`brief.md` 中的原始需求不得被覆盖，只能追加整理后的补充信息。
- 不生成 `tasks.csv`。
- 不执行代码。
- 不调用其它规划工作流。
- 每次只问一个关键问题。
- 能从仓库或参考资料判断的问题，先自行查证。
- 每个问题都应给出推荐答案或推荐取舍，避免只把问题抛回给用户。
- 不单独生成 `grill.md`；必要的澄清记录进入 `prd.md` 的“关键决策与澄清记录”章节。
- 可参考 `grill-with-docs` 的逐问逐答、查证优先和推荐答案风格，但不引入 `CONTEXT.md`、ADR 或其它外部文档体系。

### 6.3 workline-tasks

职责：

- 读取 `prd.md`。
- 使用 `workline-tasks/templates/tasks.csv` 生成 `tasks.csv`。
- 将需求拆成可实现、可验证、可回归的小任务。
- 添加最终 `REVIEW` 任务。
- 使用 `workline-tasks/scripts/workline_csv.py` 校验生成后的 `tasks.csv`。

硬约束：

- `prd.md` 是唯一需求源。
- 不实现代码。
- 不把未确认问题伪装成任务。
- 每条任务必须有验收标准、验证方式、依赖关系和所需工具。
- 生成后的 `tasks.csv` 必须能通过 `workline-tasks/scripts/workline_csv.py validate`。

### 6.4 workline-run

职责：

- 读取 `prd.md`、`tasks.csv` 和 `references/`。
- 作为 `/goal` 执行阶段的规则包，约束 `/goal` 如何按 CSV 顺序和依赖关系执行任务。
- 使用 `workline-run/scripts/workline_csv.py` 校验和更新 `tasks.csv`。
- 写入 `run.md`，记录执行过程、验证结果、阻塞项、跳过项和最终 REVIEW。
- 执行 `REVIEW` 行，并把 review 结论追加到 `run.md`。

硬约束：

- `tasks.csv` 是执行状态源。
- `workline-run` 是 `/goal` 的执行规则包，不是执行器；它不重新实现调度器，不替代 `/goal`，只提供 `/goal` 必须遵守的执行规则、状态更新规则和日志规则。
- 每条任务必须真实实现、真实验证、真实回归。
- 不用假数据、空跑、只读代码或“看起来可以”冒充通过。
- 不吞错、不删除测试、不绕过校验、不降低验收标准。
- 发现任务缺陷时记录并请求确认，不擅自扩大范围。

推荐执行方式：

```text
/goal 根据 workline-run 规范 执行 .workline/active/<slug>/tasks.csv
```

实现方式：

- `workline-run/SKILL.md` 明确写成 `/goal` 执行规则：先读 `prd.md`、`tasks.csv`，再按可解析 CSV 的状态逐条推进。
- 用户主动调用 Skill 时必须带上活动目录或 `tasks.csv` 路径，例如 `.workline/active/2026-05-28-0915-example/`，Skill 不需要猜测当前 active 任务。
- 进入 `/goal` 前，必须运行 `workline-run/scripts/workline_csv.py validate`；校验失败时先修复 CSV，不开始执行。
- 每次任务状态变化必须通过 CSV 脚本更新，减少手工编辑导致的转义错误和状态漂移。
- `/goal` 执行时只把 `tasks.csv` 当作任务计划和状态源；人类审阅也直接审阅 `tasks.csv`。
- `/goal` 的职责是执行任务本身，`workline-run` 的职责是规定执行前检查、下一任务选择、状态更新、日志记录、失败停止和恢复入口。

### 6.5 workline-archive

职责：

- 检查 Workline 过程文件是否完整。
- 检查 CSV 状态是否已闭环或已确认跳过。
- 检查 `run.md` 是否说明阻塞、跳过、失败项和最终 REVIEW 结论。
- 将目录从 `.workline/active/<slug>/` 移动到 `.workline/archive/<slug>/`。

硬约束：

- 不补做任务。
- 不伪造日志。
- 不覆盖已有归档目录。
- 不复制 `references/` 软链接或 Junction 指向的外部内容。

## 7. PRD 要求

`prd.md` 必须包含：

```md
# PRD: <标题>

## 背景

## 目标

### 目标概述

### 典型流程

### 功能要求

## 非目标

## 约束条件

## 关键决策与澄清记录

## 验收标准

## 风险与待确认问题

## 参考资料记录
```

进入任务拆分前，`prd.md` 必须满足：

- 目标明确。
- 非目标明确。
- 功能要求可执行。
- 验收标准可验证。
- 关键决策有来源。
- 关键决策与澄清记录只保留影响需求、边界、验收和取舍的关键问答，不保存完整聊天流水。
- 每个输入资料都有来源、用途和是否需要归档的说明。
- 风险与待确认问题中不存在阻塞任务拆分的未闭环问题。

“参考资料记录”用于登记进入需求澄清和任务拆分阶段的输入资料，推荐格式：

```md
| 路径 | 类型 | 来源/创建方式 | 用途 | 是否归档 |
| --- | --- | --- | --- | --- |
| references/example.zip | 用户资料 | 用户提供 | 协议字段核对 | 是 |
```

运行阶段新增的 build log、截图、验证结果、临时文件和其它产物应登记在 `run.md`，并可通过 `tasks.csv.refs` 关联到具体任务，不再回写到 `prd.md`。

## 8. CSV 任务模型

固定表头：

```csv
id,depends_on,mode,title,description,acceptance_criteria,verification,dev_state,review_state,git_state,refs,notes
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID，如 `T001`，最后一行为 `REVIEW` |
| `depends_on` | 依赖任务 ID，多个用空格分隔 |
| `mode` | 执行模式，`AFK` 表示可自动执行，`HITL` 表示需要人工参与或确认 |
| `title` | 任务标题 |
| `description` | 任务说明 |
| `acceptance_criteria` | 验收标准摘要 |
| `verification` | 验证命令或人工检查方式 |
| `dev_state` | 开发状态 |
| `review_state` | 初始检查状态 |
| `git_state` | 提交状态，只记录当前任务是否已提交、无需提交或仍待处理 |
| `refs` | 相关 PRD 章节、参考资料或运行产物引用 |
| `notes` | 备注 |

`git_state` 只记录任务级提交状态，用于归档前检查，不参与任务闭环和依赖满足判断。用户可以手动提交；提交完成后，将对应任务的 `git_state` 更新为 `committed`。如果任务没有需要提交的变更，则更新为 `not_needed`。

状态枚举：

```text
dev_state: todo | doing | done | blocked | skipped
review_state: pending | passed | failed | blocked | skipped
git_state: pending | committed | not_needed | blocked | skipped
```

任务闭环条件：

```text
dev_state = done
review_state = passed
```

`git_state` 不属于任务闭环硬条件，但归档前必须说明每条任务的最终提交状态。

状态转换规则：

- 新任务默认 `dev_state=todo`、`review_state=pending`、`git_state=pending`。
- 执行任务前必须先将 `dev_state` 从 `todo` 更新为 `doing`。
- 任务完成实现和验证后，才能将 `dev_state` 更新为 `done`。
- 验证通过且没有发现任务内问题时，才能将 `review_state` 更新为 `passed`。
- 验证失败或初步检查失败时，不得把 `dev_state` 标为 `done`。如果仍可继续修复，保持或更新为 `dev_state=doing`；如果当前条件不足导致无法继续，更新为 `dev_state=blocked`。同时将 `review_state` 更新为 `failed`，并在 `notes` 和 `run.md` 中记录原因。
- `blocked` 表示当前条件不足，后续是否能继续取决于依赖关系；`skipped` 表示经用户确认或 PRD 允许后跳过。
- `HITL` 任务需要人工输入、实机操作、账号权限或关键确认时，不得伪装为 `AFK` 自动完成。

依赖满足规则：

- 依赖任务达到闭环条件时，后续任务视为依赖满足。
- 依赖任务如果是 `skipped`，视为依赖已满足，因为跳过本身必须来自用户确认或 PRD 允许。
- 依赖任务如果是 `blocked`，后续任务不可执行，直到阻塞被解除或任务被用户确认改为 `skipped`。
- `next` 应按 CSV 顺序返回第一条依赖已满足且 `dev_state` 为 `todo` 或 `doing` 的任务。

`REVIEW` 行语义：

- `REVIEW` 必须是最后一行，且依赖所有非 `REVIEW` 任务。
- `REVIEW` 只在所有非 `REVIEW` 任务进入终态后执行，终态包括闭环或已确认的 `skipped`。存在 `blocked` 任务时，`REVIEW` 不可执行。
- `REVIEW` 需要检查 PRD 覆盖、CSV 状态、验证记录、`run.md` 证据、失败/跳过解释和 `git_state` 是否已有归档前结论。
- `REVIEW` 不能补做实现任务；发现缺口时只能记录问题、更新状态，并按需要请求用户确认。

## 9. 模板与脚本

Workline 的模板和脚本放在对应 Skill 目录下，不放顶层共享目录。

模板归属：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-grill/templates/prd.md` | `workline-grill` | 生成 `prd.md` |
| `workline-tasks/templates/tasks.csv` | `workline-tasks` | 生成 `tasks.csv` |

脚本归属：

| 文件 | 归属 | 用途 |
| --- | --- | --- |
| `workline-init/scripts/init_workline.py` | `workline-init` | 创建 `.workline/active/<slug>/`、空 `brief.md` 和 `references/` |
| `workline-tasks/scripts/workline_csv.py` | `workline-tasks` | 生成任务后校验 `tasks.csv` |
| `workline-run/scripts/workline_csv.py` | `workline-run` | `/goal` 执行阶段校验、更新 `tasks.csv`，并输出下一条可执行任务 |

`workline_csv.py` 只负责 CSV 的机械校验和状态更新，不负责理解需求、不负责调度任务。

最小命令：

```text
python workline-tasks/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py set .workline/active/<slug>/tasks.csv T001 --dev_state doing --notes "started"
python workline-run/scripts/workline_csv.py set .workline/active/<slug>/tasks.csv T001 --dev_state done --review_state passed --git_state not_needed
python workline-run/scripts/workline_csv.py next .workline/active/<slug>/tasks.csv
```

CSV 脚本职责：

- 检查表头是否完全匹配固定表头。
- 检查 CSV 是否可被标准 CSV 解析器读取。
- 检查 `id` 唯一，最后一行是 `REVIEW`。
- 检查 `depends_on` 引用的任务存在。
- 检查 `REVIEW` 为最后一行，且依赖所有非 `REVIEW` 任务。
- 检查 `mode` 属于 `AFK` 或 `HITL`。
- 检查状态值属于允许枚举。
- 检查非 `REVIEW` 任务存在验收标准和验证方式。
- `set` 命令检查状态转换是否符合规则，避免从 `todo` 直接跳到 `done` 后缺少执行记录。
- `next` 命令检查依赖满足情况，并按 CSV 顺序输出下一条可执行任务，供 `/goal` 恢复时定位。
- 原子更新单行状态字段，避免手工编辑破坏 CSV 转义。

## 10. 阶段门禁

阶段门禁分两层实现：

- 语义门禁写在各阶段 `SKILL.md` 中，由 agent 按文档内容判断，例如 PRD 是否足够明确、关键问题是否确认。
- 机械门禁交给脚本处理，例如目录创建、CSV 表头、状态枚举、依赖引用和下一任务定位。

### Init -> Grill

允许进入需求澄清的条件：

- 用户明确指定活动目录。
- `brief.md` 存在。
- `references/` 存在。
- 用户已完成必要的手工材料补充，或者明确允许在材料不足时开始澄清。

### Grill -> Tasks

允许进入任务拆分的条件：

- `brief.md` 和 `prd.md` 存在。
- `prd.md` 章节完整。
- 关键问题已确认。
- 非阻塞待确认问题已说明为什么不阻塞。

### Tasks -> Run

允许执行的条件：

- `tasks.csv` 存在。
- CSV 可被标准 CSV 解析器读取。
- 每条非 REVIEW 任务都有验收标准和验证方式。
- 最后一行是 `REVIEW`。
- `REVIEW` 依赖所有非 `REVIEW` 任务。
- CSV 已通过 `workline-run/scripts/workline_csv.py validate`。

### Run -> Archive

允许归档的条件：

- `run.md` 存在。
- `run.md` 已包含最终 REVIEW 结论。
- `tasks.csv` 没有 `todo`、`doing`、`failed`、`blocked`，也没有无解释的 `pending`。
- `skipped` 都在 `run.md` 中解释。
- `run.md` 已说明 `git_state` 的最终状态，尤其是用户手动提交或无需提交的原因。
- `REVIEW` 行已执行。

## 11. README 要求

`workline/README.md` 必须说明：

- Workline 是什么。
- 为什么它是独立工作流。
- 五个子 skill 的职责。
- 项目内 `.workline/` 目录结构。
- CSV 字段和状态闭环规则。
- 各 Skill 自包含的模板和脚本。
- 两份 CSV 校验和更新脚本的同步规则。
- 推荐使用步骤。
- 明确不混用其它工作流。

README 面向人类维护者，`SKILL.md` 面向 agent 执行。

## 12. 成功标准

该工作流完成后，应满足：

- Workline 有独立源码目录。
- 五个 skill 职责清楚，不互相吞并。
- 目录结构浅，不引入不必要的层级。
- PRD、tasks、run 能形成完整证据链。
- `/goal` 可以基于 `tasks.csv` 执行和恢复。
- 失败项不会被隐藏，阻塞项能被追踪。
- 归档后仍能复盘需求、决策、执行和验证过程。

## 13. 风险

- CSV 手写容易转义错误，需要执行前检查可解析性。
- `/goal` 的行为依赖当前 Codex 运行时能力，工作流只能约束输入和过程文件。
- 如果任务拆得太粗，执行阶段仍可能跑偏。
- 如果任务拆得太细，CSV 会变成维护负担。
