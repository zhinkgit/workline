---
name: workline-init
description: "初始化 Workline 长任务过程目录。Use when the user wants to start a new lightweight long-task workflow from a rough requirement, create a timestamped directory under .workline/active, create brief.md and references, or prepare materials before PRD grilling. Do not use for PRD writing, task splitting, execution, or archive."
---

# Workline Init

## 目标

创建一个新的 Workline 活动目录，让用户先有稳定材料入口，再进入需求澄清。

## 输入

- 用户的粗略需求文本。
- 可选活动目录 slug。
- 可选项目根目录；未提供时使用当前工作目录。

如果用户没有给出粗略需求，可以创建带 TODO 的 `brief.md`，但要明确提醒用户补充。

## 步骤

1. 定位项目根目录。
2. 运行 `scripts/init_workline.py` 创建 `.workline/active/<YYYY-MM-DD-HHMM-slug>/`。
3. 确认新目录包含：
   - `brief.md`
   - `references/`
4. 返回活动目录路径，并提示用户把参考资料、旧代码、协议文档或其它输入材料放入 `references/`。

示例：

```bash
python workline-init/scripts/init_workline.py --root . --brief "为现有工具增加批量导入流程"
python workline-init/scripts/init_workline.py --root . --slug bulk-import --brief "为现有工具增加批量导入流程"
```

## 硬约束

- 不覆盖已有活动目录；如果目标目录已存在，停止并报告。

## 输出

用简短中文说明：

- 新建活动目录路径。
- `brief.md` 已写入原始粗需求和补充材料提示。
- 下一步应使用 `$workline-grill`，并显式传入活动目录。
