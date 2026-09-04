---
name: workline-init
description: "判断粗需求是否需要 Workline，并在需要时初始化长任务过程目录。Use when the user wants to decide whether a request needs Workline, start a new long-task workflow, create a timestamped directory under .workline/active, or prepare brief.md, run.md and references before PRD grilling."
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

## 入口分流

建目录前先判断这个需求是否值得进入 Workline：

- **直接改**：单文件、单点修改，一轮内能实现并验证。不创建 `.workline/` 活动目录，告知用户本次不进入后续 Workline 流程，然后按普通编码任务处理。
- **进入 Workline**：需要多步实现、跨文件修改、边界澄清、人工参与或跨会话恢复。继续下面的初始化。

这里只做二分判断，不再划分“轻量 / 完整”。一旦创建活动目录，后续统一走完整 Workline。

## 步骤

1. 定位项目根目录。
2. 运行初始化脚本创建 `.workline/active/<YYYY-MM-DD-HHMM-slug>/`；脚本会把用户的粗需求写入 `brief.md`。
3. 确认新目录包含：
   - `brief.md`
   - `run.md`
   - `references/`
4. 返回活动目录路径，提示用户检查 `brief.md`，并在「材料清单及用途」表中登记完成任务需要的材料。

登记方式按材料所在位置决定，不是所有材料都要搬进 `references/`：

- 外部零散材料（协议文档、网页保存件、外部审查意见、参考仓库软链接）放进 `references/` 再登记路径。
- 本项目已有的文件或目录直接登记仓库内相对路径，例如 `src/driver/uart.c`，不要复制一份。
- 体积大或有独立版本管理、不便进仓库的材料登记外部绝对路径。

材料由用户主动收集，本 Skill 不代替用户判断需要哪些材料。材料够不够由 `$workline-grill` 在澄清开始前评估并指出缺口。

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
- `brief.md` 已写入创建时间和用户提供的原始粗需求。
- `run.md` 已创建，内含「阶段门禁」表，四扇门都是未确认 / 未审查。
- `references/` 已创建为空目录。
- 请检查 `brief.md` 中的原始粗需求，并在“材料清单及用途”表中登记每份材料的路径和用途：外部材料先放进 `references/`，仓库内已有的文件或目录直接写相对路径，其余写外部绝对路径。
- 材料收集齐后使用 `$workline-grill`；它会先评估材料是否够用并指出缺口，再开始逐问逐答澄清。
