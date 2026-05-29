---
name: workline-archive
description: "归档已完成的 Workline 活动目录。Use when the user provides a Workline active directory and wants to check process completeness, ensure tasks.csv and run.md are closed, check reviews when present, verify REVIEW and git_state conclusions, then move the directory to .workline/archive without copying external symlink targets."
---

# Workline Archive

## 目标

在不补做任务、不伪造日志的前提下，检查 Workline 过程文件是否闭环，将活动目录从 `.workline/active/<slug>/` 移动到 `.workline/archive/<slug>/`，并在归档后只提交核心过程文件。

用户必须提供活动目录路径；不要猜测当前 active 任务。

## 归档前检查

确认活动目录包含：

- `brief.md`
- `prd.md`
- `tasks.csv`
- `run.md`
- `references/`
- `evidence/`，如果执行阶段产生了需要保留的过程物

运行 CSV 校验：

```bash
python workline-run/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
```

`summary` warnings 不会让命令失败，但归档前必须逐项判断是否已经解释。尤其关注：

- `git-pending`：归档前必须有提交状态结论。
- `skipped-or-blocked` 中的 `git_state=blocked`：任务验证已通过但自动提交未闭环，归档前必须人工处理。
- `skipped-or-blocked`：必须在 `run.md` 中说明用户确认、客观阻塞或跳过依据。
- `missing-evidence-level` / `evidence-ref-without-level`：已完成任务必须能从 `refs` 或 `notes` 看到 `[evidence:*]` 证据等级；如果引用了过程物，也必须带证据等级。
- `hitl-without-manual-target-or-real-evidence`：HITL 任务必须有人工、目标环境或真实链路证据。
- `target-without-real`：如果只有目标环境烟测，归档说明不能扩大为真实设备联调完成。

检查 `run.md`：

- 已包含最终 REVIEW 结论。
- 已说明阻塞、跳过、失败项。
- 已说明每条任务的 `git_state` 最终状态；归档前不允许留下 `pending` 或 `blocked`。
- 已说明 `summary` warnings 的处理结论；如果 warning 未解释，停止归档。

检查 `tasks.csv`：

- 不存在 `todo` 或 `doing`。
- 不存在未解释的 `blocked`。
- 不存在 `verify_state=failed`。
- 不存在 `git_state=pending` 或 `git_state=blocked`。
- 所有 `skipped` 都在 `run.md` 中解释。
- `REVIEW` 行已执行并闭环。
- 已完成任务的 `refs` 或 `notes` 必须包含 `[evidence:*]` 标签；如果任务产生了过程物，还必须包含 `evidence/` 路径。

如果存在 `reviews/`，检查：

- 如果存在 `prd-review-*.md` 或 `tasks-review-*.md`，最新阶段结论不能是未解释的 `REVISE` 或 `BLOCKED`。
- 如果用户明确跳过审查，`run.md` 或归档输出中必须说明跳过原因。

## 移动目录

1. 计算目标路径 `.workline/archive/<slug>/`。
2. 如果目标路径已存在，停止；不要覆盖。
3. 使用移动操作移动活动目录；不要复制 `references/` 或 `evidence/` 下软链接、Junction 指向的外部内容。
4. 移动后确认 active 路径不存在、archive 路径存在。

PowerShell 示例：

```powershell
Move-Item -LiteralPath ".workline\active\<slug>" -Destination ".workline\archive\<slug>"
```

## 归档提交

移动目录后，尝试提交 Workline 核心过程文件。只提交以下四个文件在归档目录中的副本：

- `.workline/archive/<slug>/brief.md`
- `.workline/archive/<slug>/prd.md`
- `.workline/archive/<slug>/tasks.csv`
- `.workline/archive/<slug>/run.md`

不要提交 `references/`、`evidence/`、`reviews/` 或其它过程材料。不要使用 `git add .`。

推荐命令形态：

```powershell
git add -- ".workline/archive/<slug>/brief.md" ".workline/archive/<slug>/prd.md" ".workline/archive/<slug>/tasks.csv" ".workline/archive/<slug>/run.md"
git commit -m "workline: archive <slug>"
```

如果归档提交失败，不回滚已经完成的目录移动；停止并报告失败原因，让用户处理 Git 状态后重试提交。

## 硬约束

- 不伪造日志。
- 不覆盖已有归档目录。
- 如果闭环条件不满足，停止并列出具体缺口。
- 不提交 `references/`、`evidence/`、`reviews/`。

## 输出

完成时说明：

- 归档源路径。
- 归档目标路径。
- CSV、`summary` warnings、`reviews/`、`run.md`、`evidence/`（如存在）和 REVIEW 检查结果。
- 归档提交结果；如果提交失败，给出需要用户处理的 Git 状态。

