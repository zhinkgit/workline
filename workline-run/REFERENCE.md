# Workline 共用约定

`workline-tasks` / `workline-run` / `workline-review` / `workline-archive` 共用。四份副本逐字一致，由 CI 校验。

这里**只写脚本在拒绝时说不出来的东西**。结构、状态迁移、门禁顺序、产物摘要、`refs` 合法形式、阻断类 warning，脚本拒绝时的消息里就带着完整的正确答案，照它改即可，不必先回来查。

## 路径

`<SKILL_DIR>` 是调用方 SKILL.md 所在目录的绝对路径；环境未提供时先定位该文件。命令都在项目根执行。

脚本是 `<SKILL_DIR>/scripts/workline_csv.py`。**调不到就停止并报告，禁止手改 CSV 或门禁表绕过**——脚本不跑，上面那一整套拒绝一条都不会发生，这套流程就只剩一堆没人执行的文字。

## state 的调度语义

脚本管迁移合法性，不管这一条：

| 状态 | 是否满足后继任务的依赖 |
| --- | --- |
| `done` / `skipped` | 是 |
| `todo` / `doing` / `blocked` | 否 |

`skipped` 会放行后继，等于允许在它的地基上继续施工。看到 `skipped-unblocks` 时必须确认这不是空地基，脚本只会提示，不会替你判断。

`blocked` 的 `notes` 要带 `wait-user:` / `env-missing:` / `verify-failed:` 前缀；漏写或写错，脚本会拒绝并列出三者各自的含义。

## mode 按判定权，不按工具形态

**脚本查不出 mode 标错**：`AFK` 和 `HITL` 都是合法值，标反了不会有任何报错，只会在执行时把本该无人值守的任务卡住等人。

- `AFK`：命令、Skill 或其它工具能自行给出通过/失败。编译器、探针、串口能自判就仍是 `AFK`，碰到板子不是改 `HITL` 的理由。
- `HITL`：判定权在人，或必须人选 / 人手操作 / 外部账号确认。
- 工具或环境不具备是执行时标 `blocked`（`env-missing:`），不是改成 `HITL` 等人补环境。
- `next` 优先调度 `AFK`，所以 `HITL` 必须标对。

## verification 要可判定

**脚本只查 `verification` 非空**：写「验证一下功能正常」照样通过校验，可判定性只能靠拆表时的自检和审查把关。

写「用什么手段、怎样算过」。手段可以是命令行、已安装的 Agent Skill，或其它能给出通过/失败的工具。反引号只是排版，**不要因为没有反引号就把 AFK 改成 HITL**。

- AFK 例：`pytest tests/test_import.py` 退出码 0；jlink flash 成功且 rtt 3s 内出现 boot ok。
- HITL 例：打开导入页上传 samples/bad.csv，人确认错误报告可读。
- 写成「验证一下」这类无法判定的句子，审查按 `REVISE` 处理。

## refs 里脚本查不出的两条

合法形式和解析基准由 `refs-invalid` / `refs-not-found` 的消息给出。脚本查不出的是：

- **不写本任务要修改的目标文件**。`refs` 是「执行时要读的既有材料」，改哪些源码由执行者自己搜索定位。脚本不知道这条任务会改什么，写进去也不报错。
- **领域在 `.workline/notes/` 有主题文件时必须写进 `refs`**。漏引用不报错，但执行阶段不会自己去翻 notes，已沉淀的项目约定就白写了。

空 `refs` 只是提示，确无材料的任务用 `--allow-empty-refs` 豁免。

## 阶段门禁

`materials` → `prd-review` → `tasks-review` → `execute`，写在 `run.md` 的「阶段门禁」表，由 `gates-set` 维护，是跨阶段唯一放行依据；**对话里的「看起来可以」不算**。

顺序、产物摘要新鲜度、阻断项都由脚本强制，违反时消息会说清该回哪个阶段。
