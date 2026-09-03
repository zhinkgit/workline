---
name: workline-init
description: "初始化 Workline 长任务过程目录。Use when the user wants to start a new lightweight long-task workflow from a rough requirement, create a timestamped directory under .workline/active, create brief.md and references, or prepare materials before PRD grilling."
---

# Workline Init

## 目标

创建一个新的 Workline 活动目录，让用户先有稳定材料入口，再进入需求澄清。

## 路径约定

`<SKILL_DIR>` 指本 SKILL.md 所在目录的绝对路径。运行环境未提供该变量时，先定位本文件的实际路径再替换。所有命令都在项目根目录下执行。

## 输入

- 用户的粗略需求文本。
- 可选活动目录 slug。
- 可选项目根目录；未提供时使用当前工作目录。

## 步骤

1. 定位项目根目录。
2. 运行初始化脚本创建 `.workline/active/<YYYY-MM-DD-HHMM-slug>/`。
3. 确认新目录包含：
   - `brief.md`
   - `references/`
4. 返回活动目录路径，并提示用户手动填写 `brief.md`，手动把参考资料、旧代码、协议文档或其它输入材料放入 `references/`。

材料由用户主动收集，本 Skill 不代替用户判断需要哪些材料，也不代写 `brief.md`。材料够不够由 `$workline-grill` 在澄清开始前评估并指出缺口。

示例：

```bash
python <SKILL_DIR>/scripts/init_workline.py --root . --brief "为现有工具增加批量导入流程"
python <SKILL_DIR>/scripts/init_workline.py --root . --slug bulk-import --brief "为现有工具增加批量导入流程"
```

## 硬约束

- 目标目录已存在时停止并报告。
- 脚本不可用时停止并报告实际路径问题，不得改用手工建目录绕过。

## 输出

用简短中文说明：

- 新建活动目录路径。
- `brief.md` 已创建为基础模板，创建时间已填充。
- `references/` 已创建为空目录。
- 请按 `brief.md` 模板手动填写原始粗需求，并把参考资料放入 `references/`，同时在“已放入 references/ 的材料及用途”表中登记每份材料的用途。
- 材料收集齐后使用 `$workline-grill`；它会先评估材料是否够用并指出缺口，再开始逐问逐答澄清。
