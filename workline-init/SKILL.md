---
name: workline-init
description: "判断粗需求是否需要 Workline，并在需要时初始化长任务过程目录。Use when the user wants to decide whether a request needs Workline, start a new long-task workflow, create a timestamped directory under .workline/active, or prepare brief.md and run.md before PRD grilling."
disable-model-invocation: true
---

# Workline Init

## 目标

创建一个新的 Workline 活动目录，让用户先有稳定材料入口，再进入需求澄清。

本 Skill 只由用户显式调用（`/workline-init` 或 `$workline-init`），不要在用户只是描述需求时自行触发。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

## 输入

- 用户的粗略需求文本。
- 活动目录 slug：**必须全英文**，小写 kebab-case，只允许 `a-z0-9-`。用户需求是中文时，由 agent 把它翻译概括成英文 slug 后用 `--slug` 传入，不要让脚本从中文里瞎猜。
- 可选项目根目录；未提供时使用当前工作目录。

## 入口分流

建目录前先判断这个需求是否值得进入 Workline：

- **直接改**：单文件、单点修改，一轮内能实现并验证。不创建 `.workline/` 活动目录，告知用户本次不进入后续 Workline 流程，然后按普通编码任务处理。
- **进入 Workline**：需要多步实现、跨文件修改、边界澄清、人工参与或跨会话恢复。继续下面的初始化。

这里只做二分判断，不再划分「轻量 / 完整」。一旦创建活动目录，后续统一走完整 Workline。

## 步骤

1. 定位项目根目录。
2. 先想好英文 slug：用 3 个左右的英文小写单词概括这次需求，用 `-` 连接，例如 `modify-agc-module`、`bulk-import`。中文需求必须在这一步翻译成英文，**不要**把中文塞进目录名。
3. 运行初始化脚本创建 `.workline/active/<YYYY-MM-DD-HHMM-slug>/`，并显式传 `--slug`；脚本会把用户的粗需求原文（可以是中文）写入 `brief.md`。
4. 确认新目录包含：
   - `brief.md`
   - `run.md`
5. 确认 `.workline/` 下已有独立的过程文档 Git 仓库（脚本自动建，见「两套版本管理」）。
6. 返回活动目录路径，并按下节告诉用户他需要准备什么。

示例：

```bash
python <SKILL_DIR>/scripts/init_workline.py --root . --slug bulk-import --brief "为现有工具增加批量导入流程"
python <SKILL_DIR>/scripts/init_workline.py --root . --slug modify-agc-module --brief "根据方案修改AGC模块"
```

目录名里的英文只是标识，`brief.md`、`run.md` 等文件内容和与用户的对话仍然全部用中文。

## 两套版本管理

过程文档和业务代码**分属两个 Git 仓库**，脚本在初始化时自动落位：

| 仓库 | 位置 | 管什么 | 谁提交 |
| --- | --- | --- | --- |
| 文档库 | `.workline/.git` | `brief.md`、`prd.md`、`tasks.csv`、`run.md`、`notes/` | `$workline-archive` |
| 代码库 | `brief.md` 材料清单里用途标 `[仓库]` 的路径 | 业务代码 | `$workline-run` 的提交收口 |

这样 workline 打开在哪一层都不影响流程：打开在代码仓库根目录可以，打开在 `C:/Users/Public/RK3568` 这种父目录、代码散在 `project/commagc/agcavc` 子目录里也可以。

脚本在 `.workline/` 下 `git init`（已存在则跳过），并把新建的活动目录提交一次作为基线；失败只提示不阻断。

## 材料清单

`brief.md` 只有一张「## 材料清单」表，两列：`位置`、`用途`。

- `位置` 直接写材料在哪：本地绝对路径、相对 workline 根的路径、URL、`user@host` 都行，材料不复制进活动目录。
- **代码仓库也登记在这张表里，用途以 `[仓库]` 开头**，例如 `| project/commagc/agcavc | [仓库] agcavc 模块源码 |`。这决定了后续 `tasks.csv` 里的提交哈希去哪核验：
  - workline 打开在代码仓库根目录 → 不标也行，脚本自动认这个仓库。
  - 打开在父目录 → **必须标**，否则真实哈希一律无法核验，只能写 `no-change`。
  - 一次任务动多个仓库 → 标多行，脚本逐个仓库找哈希。
  - 纯文档 / 调研任务 → 不标，所有任务的 `commit` 写 `no-change`。

**只让用户登记仓库里没有的东西。本项目已有的文件和目录不用用户手动登记**：`$workline-grill` 会扫描仓库，把相关的仓库内路径作为候选行追加进这张表，由用户确认或剔除。不要让用户替 agent 干查证的活。

材料够不够由 `$workline-grill` 在澄清开始前评估并指出缺口。

## 硬约束

- **活动目录名必须全英文**：`<YYYY-MM-DD-HHMM-slug>` 中的 slug 只能由 `a-z`、`0-9` 和 `-` 组成，不得出现中文、大写字母、空格或下划线。脚本会丢弃非 ASCII 字符，slug 为空时直接报错退出。
- 粗需求含中文等非 ASCII 字符却没传 `--slug` 时，脚本直接报错退出，不会拿需求里夹带的零星英文词凑名字。
- slug 被脚本拒绝时，重新翻译出英文 slug 再传 `--slug`，不得手工 `mkdir` 中文目录绕过。
- 目标目录已存在时停止并报告。
- 脚本不可用时停止并报告实际路径问题，不得改用手工建目录绕过。

## 输出

用简短中文说明：

- 新建活动目录路径（目录名为全英文 slug）。
- `brief.md` 已写入创建时间和用户提供的原始粗需求。
- `run.md` 已创建，内含「阶段门禁」表，四扇门都是未确认 / 未审查。
- `.workline/` 下已建立独立的过程文档 Git 仓库，业务代码的版本管理仍归代码仓库自己；若脚本提示 git 不可用或提交失败，如实转达。
- 请检查 `brief.md` 中的原始粗需求；材料清单现在是空的，**只需登记仓库里没有的外部材料**，直接填位置和用途，不必复制。代码在子目录的仓库时，用途以 `[仓库]` 开头登记，否则后续提交哈希无法核验。
- 仓库内已有的文件目录不必手工登记，`$workline-grill` 会扫出候选清单请你确认。
- 外部材料登记好后使用 `$workline-grill`；它会先补全候选材料清单、评估是否够用，再开始分轮澄清。
