---
name: workline-init
description: "判断粗需求是否需要 Workline，并在需要时初始化长任务过程目录。Use when the user wants to decide whether a request needs Workline, start a new long-task workflow, create a timestamped directory under .workline/active, or prepare brief.md, run.md and references before PRD grilling."
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
- 可选活动目录 slug。
- 可选项目根目录；未提供时使用当前工作目录。

## 入口分流

建目录前先判断这个需求是否值得进入 Workline：

- **直接改**：单文件、单点修改，一轮内能实现并验证。不创建 `.workline/` 活动目录，告知用户本次不进入后续 Workline 流程，然后按普通编码任务处理。
- **进入 Workline**：需要多步实现、跨文件修改、边界澄清、人工参与或跨会话恢复。继续下面的初始化。

这里只做二分判断，不再划分「轻量 / 完整」。一旦创建活动目录，后续统一走完整 Workline。

## 步骤

1. 定位项目根目录。
2. 运行初始化脚本创建 `.workline/active/<YYYY-MM-DD-HHMM-slug>/`；脚本会把用户的粗需求写入 `brief.md`。
3. 确认新目录包含：
   - `brief.md`
   - `run.md`
   - `references/`
4. 返回活动目录路径，并按下节告诉用户他需要准备什么。

示例：

```bash
python <SKILL_DIR>/scripts/init_workline.py --root . --brief "为现有工具增加批量导入流程"
python <SKILL_DIR>/scripts/init_workline.py --root . --slug bulk-import --brief "为现有工具增加批量导入流程"
```

## 用户只负责仓库外的材料

`brief.md` 的「材料清单及用途」表初始为空。**只让用户准备仓库里没有的东西**，两种登记方式二选一，不必都搬进 `references/`：

- **放进 `references/` 再登记相对路径**：需要随归档保存、或要被 `tasks.csv` 的 `refs` 引用的材料，例如协议文档、网页保存件、外部审查意见、参考仓库软链接。
- **直接在表里填外部绝对路径**：体积大、有独立版本管理、或只在澄清阶段用一次的材料，不必复制进活动目录。这类路径不能进 `refs`，需要它的结论要在澄清阶段固化进 `prd.md`。

**本项目已有的文件和目录不用用户手动登记**：`$workline-grill` 会扫描仓库，把相关的仓库内路径作为候选行追加进这张表，由用户确认或剔除。不要让用户替 agent 干查证的活。

材料够不够由 `$workline-grill` 在澄清开始前评估并指出缺口。

## 硬约束

- 目标目录已存在时停止并报告。
- 脚本不可用时停止并报告实际路径问题，不得改用手工建目录绕过。

## 输出

用简短中文说明：

- 新建活动目录路径。
- `brief.md` 已写入创建时间和用户提供的原始粗需求。
- `run.md` 已创建，内含「阶段门禁」表，四扇门都是未确认 / 未审查。
- `references/` 已创建为空目录。
- 请检查 `brief.md` 中的原始粗需求；材料表现在是空的，**只需准备仓库里没有的外部材料**：需要随归档保存或被 `refs` 引用的放进 `references/` 再登记相对路径，其余直接在表里填外部绝对路径即可，不必复制。
- 仓库内已有的文件目录不必手工登记，`$workline-grill` 会扫出候选清单请你确认。
- 外部材料放好后使用 `$workline-grill`；它会先补全候选材料清单、评估是否够用，再开始分轮澄清。
