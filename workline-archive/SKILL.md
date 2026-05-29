---
name: workline-archive
description: "归档已完成的 Workline 活动目录。Use when the user provides a Workline active directory and wants to check process completeness, ensure tasks.csv and run.md are closed, check reviews when present, verify REVIEW and git_state conclusions, then move the directory to .workline/archive without copying external symlink targets."
---

# Workline Archive

## 目标

在不补做任务、不伪造日志的前提下，检查 Workline 过程文件是否闭环，并将活动目录从 `.workline/active/<slug>/` 移动到 `.workline/archive/<slug>/`。

用户必须提供活动目录路径；不要猜测当前 active 任务。

## 归档前检查

确认活动目录包含：

- `brief.md`
- `prd.md`
- `tasks.csv`
- `run.md`
- `references/`
- `evidence/`，如果执行阶段产生了证据

运行 CSV 校验：

```bash
python workline-run/scripts/workline_csv.py validate .workline/active/<slug>/tasks.csv
python workline-run/scripts/workline_csv.py summary .workline/active/<slug>/tasks.csv
```

`summary` warnings 不会让命令失败，但归档前必须逐项判断是否已经解释。尤其关注：

- `git-pending`：归档前必须有提交状态结论。
- `skipped-or-blocked`：必须在 `run.md` 中说明用户确认、客观阻塞或跳过依据。
- `missing-evidence-ref` / `missing-evidence-level`：已完成任务必须能从 `refs` 或 `notes` 追溯到验证产物，并带有 `[evidence:*]` 证据等级。
- `hitl-without-manual-or-board-evidence`：HITL 任务必须有人工、板端或真实设备证据。
- `board-smoke-without-real-device`：如果只有板端烟测，归档说明不能扩大为真实设备联调完成。

检查 `run.md`：

- 已包含最终 REVIEW 结论。
- 已说明阻塞、跳过、失败项。
- 已说明每条任务的 `git_state` 最终状态，尤其是用户手动提交或无需提交的原因。
- 已说明 `summary` warnings 的处理结论；如果 warning 未解释，停止归档。

检查 `tasks.csv`：

- 不存在 `todo` 或 `doing`。
- 不存在未解释的 `blocked`。
- 不存在 `verify_state=failed`。
- 所有 `skipped` 都在 `run.md` 中解释。
- `REVIEW` 行已执行并闭环。
- 已完成任务的 `refs` 或 `notes` 必须包含 `evidence/` 路径和 `[evidence:*]` 标签。

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

## 硬约束

- 不伪造日志。
- 不覆盖已有归档目录。
- 如果闭环条件不满足，停止并列出具体缺口。

## 输出

完成时说明：

- 归档源路径。
- 归档目标路径。
- CSV、`summary` warnings、`reviews/`、`run.md`、`evidence/`（如存在）和 REVIEW 检查结果。

