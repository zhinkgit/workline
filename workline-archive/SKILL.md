---
name: workline-archive
description: "归档已完成的 Workline 活动目录并沉淀项目知识。Use when the user provides a Workline active directory and wants to check process completeness, ensure tasks.csv and run.md are closed, verify REVIEW and commit conclusions, write reusable knowledge into .workline/notes, then move the directory to .workline/archive without copying external symlink targets."
---

# Workline Archive

## 目标

确认 Workline 过程文件已闭环，把本次任务产生的可复用项目知识写入 `.workline/notes/`，将活动目录从 `.workline/active/<slug>/` 移动到 `.workline/archive/<YYYY-MM>/<slug>/`，并在归档后提交。

用户必须提供活动目录路径。如果是归档移动后提交失败的重试，也可提供已移动的 archive 目录。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

本 Skill 自带 `<SKILL_DIR>/scripts/workline_csv.py`，不要去其它 skill 目录找脚本。

## 归档前检查

先确认活动目录包含：`brief.md`、`prd.md`、`tasks.csv`、`run.md`、`references/`。任何一项缺失都停止，不得移动目录。

最终审计由 `REVIEW` 行负责。本 Skill 只做搬运前硬检查：

```bash
python <SKILL_DIR>/scripts/workline_csv.py archive-check .workline/active/<slug>/tasks.csv
```

`archive-check` 失败即停止，列出具体缺口，不做移动。它会核验：

1. 必需路径存在。
2. `REVIEW` 为 `done`，且 `run.md` 有完整的 `## REVIEW` 小节。
3. 不存在 `todo` / `doing` / `blocked` 任务；`skipped` 必须有 `notes`。
4. 所有 `done` 任务的日志完整、commit 可核验。
5. `run.md`「阶段门禁」中 `materials` 为 `CONFIRMED` 或 `WAIVED`，`prd-review` 与 `tasks-review` 为 `PASS`，`execute` 为 `CONFIRMED`。
6. 不存在未覆盖的 `FR-` / `NFR-` 编号。
7. PRD 和任务计划与门禁中保存的产物摘要一致。
8. `references/` / `evidence/` 的引用合法且实际存在；`REVIEW` 行不能代替普通任务覆盖 FR/NFR。

`refs-missing`、`skipped-unblocks` 不阻止归档，但要在输出中列出。`refs-invalid`、`refs-not-found`、`req-id-padded` 会阻止归档。

## 知识沉淀

归档前把本次任务产生的可复用知识写入 `.workline/notes/`。这一步的目的是让新会话能快速了解本代码库，而不必去翻归档目录。

### 判断标准

只沉淀满足全部三条的内容：

- **跨任务复用**：下一个任务或新会话会用到。
- **不是过程记录**：不是“本次改了什么”，而是“本项目是怎样的”。
- **有原因**：光有结论没有原因的条目，下次会被推翻重来。

典型该沉淀的：项目约定、踩过的坑及规避方式、关键技术决策及其取舍、外部依赖的非显然行为、环境和工具链的特殊配置。

典型不该沉淀的：本次任务的实现细节、一次性的临时决定、已经写在代码注释或项目文档里的内容、通用编程知识。

候选条目来自 `run.md` 的 `## REVIEW` 小节；REVIEW 没有列出候选时，自己通读 `run.md` 和 `prd.md` 判断一次。没有值得沉淀的内容时明确说明“本次无新增知识”，不要为了填充而写。

### 写入

1. `.workline/notes/` 不存在时创建，并用 `<SKILL_DIR>/templates/notes-index.md` 创建 `index.md`。
2. 对每条知识，判断归入哪个已有主题文件；没有合适主题时用 `<SKILL_DIR>/templates/note.md` 新建 `.workline/notes/<主题>.md`。
3. 以二级小节**追加**写入，不改写已有条目：

   ```md
   ## <条目标题>

   - 结论：<是什么>
   - 原因：<为什么>
   - 适用范围：<什么情况下适用，什么情况下不适用>
   - 来源：`.workline/archive/<YYYY-MM>/<slug>/`
   ```

4. 新建主题文件时，在 `index.md` 的表格追加一行：文件、主题、什么时候需要读。
5. 与已有条目冲突时不要静默覆盖：停止并向用户说明冲突的两条结论，由用户决定保留、修订还是并存。

`index.md` 是发现面，保持一行一条；正文写在主题文件里，不要把结论堆进索引。

## 移动目录

1. 从 slug 前缀取出年月，计算目标路径 `.workline/archive/<YYYY-MM>/<slug>/`。
2. 如果目标路径已存在，停止并报告。
3. 目标父目录不存在时先创建。
4. 使用移动操作移动活动目录，保留 `references/` 或 `evidence/` 下链接本体，不复制外部软链接目标。
5. 移动后确认 active 路径不存在、archive 路径存在。

PowerShell 示例：

```powershell
New-Item -ItemType Directory -Force -Path ".workline\archive\<YYYY-MM>" | Out-Null
Move-Item -LiteralPath ".workline\active\<slug>" -Destination ".workline\archive\<YYYY-MM>\<slug>"
```

POSIX 示例：

```bash
mkdir -p ".workline/archive/<YYYY-MM>"
mv ".workline/active/<slug>" ".workline/archive/<YYYY-MM>/<slug>"
```

## 归档提交

移动目录后，提交 Workline 核心过程文件和本次新增的知识条目：

- `.workline/archive/<YYYY-MM>/<slug>/brief.md`
- `.workline/archive/<YYYY-MM>/<slug>/prd.md`
- `.workline/archive/<YYYY-MM>/<slug>/tasks.csv`
- `.workline/archive/<YYYY-MM>/<slug>/run.md`
- `.workline/notes/` 下本次新增或修改的文件

`references/` 和 `evidence/` 作为过程材料保留在归档目录中，不进入这次提交。

这意味着它们默认只保证当前工作区可追溯，不保证重新克隆后仍可用。需要跨机器审计时，先检查体积和敏感信息，再由用户明确决定把相关材料加入 Git 或外部制品库。

```powershell
git add -- ".workline/archive/<YYYY-MM>/<slug>/brief.md" ".workline/archive/<YYYY-MM>/<slug>/prd.md" ".workline/archive/<YYYY-MM>/<slug>/tasks.csv" ".workline/archive/<YYYY-MM>/<slug>/run.md" ".workline/notes/index.md" ".workline/notes/<主题>.md"
git commit -m "workline: archive <slug>"
```

如果归档提交失败，不回滚已经完成的目录移动；停止并报告失败原因，让用户处理 Git 状态后重试提交。

### 移动后恢复

用户重试时如果 active 路径已不存在，但根据 slug 计算出的 archive 路径已存在，视为“移动完成、提交未完成”的恢复入口：

1. 对 archive 目录中的 `tasks.csv` 重跑 `archive-check`。
2. 查看 Git diff，确认知识条目没有被重复追加。
3. 只重试“归档提交”，不再移动目录、不重复写 notes。

## 硬约束

- 日志以已有真实记录为准。
- 归档目标必须是新目录。
- `archive-check` 失败时停止并列出具体缺口。
- 知识条目必须有原因，不得只写结论。
- 知识冲突时停止询问，不静默覆盖已有条目。
- 归档提交范围限于四个核心过程文件和本次变更的 notes 文件。
- 校验脚本不可用时停止并报告，禁止跳过校验直接归档。

## 输出

完成时说明：

- 归档源路径和目标路径。
- `archive-check` 的结果。
- 不阻塞归档但值得注意的 warning。
- 写入 `.workline/notes/` 的条目清单；无新增时明确说明。
- 归档提交结果；如果提交失败，给出需要用户处理的 Git 状态。
