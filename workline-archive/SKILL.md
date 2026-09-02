---
name: workline-archive
description: "归档已完成的 Workline 活动目录。Use when the user provides a Workline active directory and wants to check process completeness, ensure tasks.csv and run.md are closed, verify REVIEW and commit conclusions, then move the directory to .workline/archive without copying external symlink targets."
---

# Workline Archive

## 目标

确认 Workline 过程文件已闭环，将活动目录从 `.workline/active/<slug>/` 移动到 `.workline/archive/<YYYY-MM>/<slug>/`，并在归档后提交核心过程文件。

用户必须提供活动目录路径。

## 路径约定

`<CSV_SCRIPT>` 指 `workline-tasks` 或 `workline-run` skill 目录下的 `scripts/workline_csv.py`，两份实现等价，任选其一。运行环境未提供 skill 目录变量时，先定位实际路径再替换。所有命令都在项目根目录下执行。

## 归档前检查

先确认活动目录包含以下必需路径：

- `brief.md`
- `prd.md`
- `tasks.csv`
- `run.md`
- `references/`

任何必需路径缺失都必须停止，不得移动目录。

最终审计由 `REVIEW` 行负责，本 Skill 只做搬运前确认，检查三条：

```bash
python <CSV_SCRIPT> validate .workline/active/<slug>/tasks.csv
```

1. `REVIEW` 行 `state=done`，且 `run.md` 中有 `## REVIEW` 小节记录最终结论。
2. 不存在 `todo`、`doing`、`failed`、`blocked` 的任务；`skipped` 任务必须在 `notes` 和 `run.md` 中有依据。
3. 校验输出中不存在 `commit-missing` 和 `run-log-missing` 两类 warning。

任何一条不满足就停止，列出具体缺口，不做移动。

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

## 归档提交

移动目录后，尝试提交 Workline 核心过程文件。只提交以下四个文件在归档目录中的副本：

- `.workline/archive/<YYYY-MM>/<slug>/brief.md`
- `.workline/archive/<YYYY-MM>/<slug>/prd.md`
- `.workline/archive/<YYYY-MM>/<slug>/tasks.csv`
- `.workline/archive/<YYYY-MM>/<slug>/run.md`

`references/` 和 `evidence/` 作为过程材料保留在归档目录中，不进入这次提交。

提交命令使用显式路径：

```powershell
git add -- ".workline/archive/<YYYY-MM>/<slug>/brief.md" ".workline/archive/<YYYY-MM>/<slug>/prd.md" ".workline/archive/<YYYY-MM>/<slug>/tasks.csv" ".workline/archive/<YYYY-MM>/<slug>/run.md"
git commit -m "workline: archive <slug>"
```

如果归档提交失败，不回滚已经完成的目录移动；停止并报告失败原因，让用户处理 Git 状态后重试提交。

## 硬约束

- 日志以已有真实记录为准。
- 归档目标必须是新目录。
- 闭环条件不满足时停止并列出具体缺口。
- 归档提交范围限于四个核心过程文件。
- 校验脚本不可用时停止并报告，禁止跳过校验直接归档。

## 输出

完成时说明：

- 归档源路径和目标路径。
- 必需路径检查和三条闭环检查的结果。
- 归档提交结果；如果提交失败，给出需要用户处理的 Git 状态。
