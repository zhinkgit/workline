---
name: workline-archive
description: "归档已完成的 Workline 活动目录并沉淀项目知识。Use when the user provides a Workline active directory and wants to check process completeness, ensure tasks.csv and run.md are closed, verify REVIEW and commit conclusions, write reusable knowledge into .workline/notes, then move the directory to .workline/archive without copying external symlink targets."
disable-model-invocation: true
---

# Workline Archive

确认过程文件已闭环，把可复用项目知识写入 `.workline/notes/`，把活动目录移到 `.workline/archive/<YYYY-MM>/<slug>/`，然后提交。只由用户显式调用。

用户必须提供活动目录路径；归档移动后提交失败的重试也可提供已移动的 archive 目录。

**开始前先读 `<SKILL_DIR>/REFERENCE.md`**：脚本拒绝时说不出来的那几条（`mode` 判定权、`verification` 可判定性、`refs` 的两条语义、`skipped` 的调度影响）在那里。结构、状态迁移、门禁顺序、`refs` 合法形式、阻断项这些，直接按脚本的错误消息改，消息里带着完整的正确答案。本会话已经读过就不必重复读。本 Skill 自带 `<SKILL_DIR>/scripts/workline_csv.py`，不要去其它 skill 目录找脚本。

## 归档前检查

先确认活动目录包含 `brief.md`、`prd.md`、`tasks.csv`、`run.md`、`references/`，任何一项缺失都停止，不得移动目录。

最终审计由 `REVIEW` 行负责，本 Skill 只做搬运前硬检查：

```bash
python <SKILL_DIR>/scripts/workline_csv.py archive-check .workline/active/<slug>/tasks.csv
```

它核验：必需路径存在；`REVIEW` 为 `done` 且 `run.md` 有完整的 `## REVIEW` 小节；不存在 `todo` / `doing` / `blocked` 任务（`blocked` 按分类前缀报告），`skipped` 有 `notes`；所有 `done` 任务日志完整、commit 可核验；四扇门都已通过；没有未覆盖的 `FR-` / `NFR-`；PRD 和任务计划与门禁保存的摘要一致；`refs` 路径合法且存在，`REVIEW` 行不代替普通任务覆盖需求。

失败即停止，照消息列出的缺口处理，不做移动。`[提示]` 类 warning 不阻断归档，但要在输出里列出。

## 知识沉淀

归档前把本次任务产生的可复用知识写入 `.workline/notes/`，让新会话不必翻归档目录。

只沉淀满足全部三条的内容：**跨任务复用**（下一个任务或新会话会用到）、**不是过程记录**（不是「本次改了什么」，而是「本项目是怎样的」）、**有原因**（光有结论没有原因的条目下次会被推翻重来）。

该沉淀的典型：项目约定、踩过的坑及规避方式、关键技术决策及其取舍、外部依赖的非显然行为、环境和工具链的特殊配置。不该沉淀的典型：本次任务的实现细节、一次性的临时决定、已写在代码注释或项目文档里的内容、通用编程知识。

候选条目来自 `run.md` 的 `## REVIEW` 小节；REVIEW 没列出候选时自己通读 `run.md` 和 `prd.md` 判断一次。没有值得沉淀的内容时明确说「本次无新增知识」，不要为了填充而写。

### 写入

1. `.workline/notes/` 不存在时创建，并用 `<SKILL_DIR>/templates/notes-index.md` 创建 `index.md`。
2. 每条知识判断归入哪个已有主题文件；没有合适主题时用 `<SKILL_DIR>/templates/note.md` 新建 `.workline/notes/<主题>.md`，并在 `index.md` 表格追加一行（文件、主题、什么时候需要读）。
3. 以二级小节**追加**写入，不改写已有条目：

   ```md
   ## <条目标题>

   - 结论：<是什么>
   - 原因：<为什么>
   - 适用范围：<什么情况下适用，什么情况下不适用>
   - 最后确认：<YYYY-MM-DD>
   - 来源：`.workline/archive/<YYYY-MM>/<slug>/`
   ```

4. 与已有条目冲突时不要静默覆盖：停止并说明冲突的两条结论，由用户决定保留、修订还是并存。修订已有条目时更新它的「最后确认」日期。

`index.md` 是发现面，保持一行一条；正文写在主题文件里。

### 让所有会话都能读到 notes

沉淀的知识只在 Workline 流程里被读到，等于一半场景白写：「直接改」的单点任务根本不走 grill。首次创建 `index.md` 时把它挂进项目的 agent 说明文件：

1. 项目根有 `AGENTS.md` 就用它；没有但有 `CLAUDE.md` 就用 `CLAUDE.md`。
2. 在文件末尾追加一行，不动其它内容：

   ```md
   - 项目约定、踩过的坑和关键技术决策见 `.workline/notes/index.md`，动手前先按索引取用相关主题。
   ```

3. 已有等价指针时跳过，不要重复追加。
4. 两个文件都不存在时**不要新建**：把这一行给用户，让他自己决定挂到哪。

这一行随归档提交一起提交。

### 定期整理

追加写入会让 notes 越攒越长，且没有机制标记结论已经过期。归档时判断一次，满足任一条就向用户提出：单个主题文件超过 10 条或 `index.md` 超过 15 行；发现已有条目与本次任务的事实矛盾，或「最后确认」已超过半年。

整理是一次**允许重写**的合并：同一结论并成一条、已被推翻的删除、仍然成立的更新日期。**必须先说明要合并和删除哪些条目，得到用户确认后再改**，不要在归档流程里静默重写。用户不同意就照常追加，留到下次。

## 移动目录

从 slug 前缀取年月算出 `.workline/archive/<YYYY-MM>/<slug>/`。目标已存在则停止并报告；父目录不存在先创建。用移动操作搬运，保留 `references/` 或 `evidence/` 下链接本体，不复制外部软链接目标。移动后确认 active 路径不存在、archive 路径存在。

```powershell
New-Item -ItemType Directory -Force -Path ".workline\archive\<YYYY-MM>" | Out-Null
Move-Item -LiteralPath ".workline\active\<slug>" -Destination ".workline\archive\<YYYY-MM>\<slug>"
```

```bash
mkdir -p ".workline/archive/<YYYY-MM>" && mv ".workline/active/<slug>" ".workline/archive/<YYYY-MM>/<slug>"
```

## 归档提交

提交范围：归档目录下的 `brief.md`、`prd.md`、`tasks.csv`、`run.md`，`.workline/notes/` 下本次新增或修改的文件，以及本次追加了 notes 指针的 `AGENTS.md` 或 `CLAUDE.md`。

`references/` 和 `evidence/` 作为过程材料保留在归档目录中，不进入这次提交。这意味着它们默认只保证当前工作区可追溯：重新克隆后归档目录里指向 `evidence/` 的 `refs` 会失效。需要跨机器审计时先检查体积和敏感信息，再由用户明确决定是否加入 Git 或外部制品库。

```powershell
git add -- ".workline/archive/<YYYY-MM>/<slug>/brief.md" ".workline/archive/<YYYY-MM>/<slug>/prd.md" ".workline/archive/<YYYY-MM>/<slug>/tasks.csv" ".workline/archive/<YYYY-MM>/<slug>/run.md" ".workline/notes/index.md" ".workline/notes/<主题>.md"
git commit -m "workline: archive <slug>"
```

提交失败时不回滚已完成的目录移动；停止并报告失败原因，让用户处理 Git 状态后重试。

**移动后恢复**：重试时若 active 路径已不存在而算出的 archive 路径已存在，视为「移动完成、提交未完成」——对 archive 目录中的 `tasks.csv` 重跑 `archive-check`，查 Git diff 确认知识条目和 notes 指针没有被重复追加，然后只重试提交，不再移动目录、不重复写 notes。

## 硬约束

- 日志以已有真实记录为准；归档目标必须是新目录。
- `archive-check` 失败时停止并列出具体缺口。
- 知识条目必须有原因；冲突时停止询问，整理合并必须先得到用户确认。
- 两个 agent 说明文件都不存在时不新建，只把指针内容交给用户。
- 归档提交范围限于四个核心过程文件、本次变更的 notes 文件和 notes 指针行。

## 输出

- 归档源路径和目标路径，`archive-check` 结果。
- 不阻塞归档但值得注意的 warning。
- 写入 `.workline/notes/` 的条目清单；无新增时明确说明。
- notes 指针写进了哪个文件，或为什么没写。
- 是否建议整理 notes，以及用户的决定。
- 归档提交结果；失败时给出需要用户处理的 Git 状态。
