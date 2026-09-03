#!/usr/bin/env python3
"""Validate and update Workline tasks.csv.

同步副本：workline-tasks/scripts/、workline-run/scripts/、workline-review/scripts/
三份必须逐字一致，用 tools/check_script_sync.py 校验。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable


HEADERS = [
    "id",
    "depends_on",
    "mode",
    "title",
    "description",
    "verification",
    "state",
    "commit",
    "refs",
    "notes",
]

MODES = {"AFK", "HITL"}
STATES = {"todo", "doing", "done", "blocked", "skipped"}
OPEN_STATES = {"todo", "doing"}
EXCEPTION_STATES = {"blocked", "skipped"}
SATISFYING_STATES = {"done", "skipped"}

RUN_SECTION_RE = re.compile(r"^##\s+(\S+)", re.MULTILINE)
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
FR_HEADING_RE = re.compile(r"^###\s+(FR-\d+)\b", re.MULTILINE)
FR_REF_RE = re.compile(r"\bFR-\d+\b")

# AFK 任务的 verification 应当机器可判定。这是启发式回查，只产生 warning。
COMMAND_HINT_RE = re.compile(
    r"`[^`]+`"
    r"|\b(?:python3?|py|pip|uv|npm|pnpm|yarn|bun|deno|node|pytest|tox|unittest"
    r"|go|cargo|rustc|cmake|make|ninja|gcc|clang|clang-format|arm-none-eabi-\w+"
    r"|dotnet|mvn|gradle|java|git|docker|kubectl|curl|wget|bash|sh|zsh|pwsh"
    r"|powershell|ruby|php|composer|jest|vitest|eslint|ruff|mypy|black|tsc"
    r"|openocd|jlink|probe-rs|tshark|ctest|meson|bazel)\b",
    re.IGNORECASE,
)


class WorklineCsvError(Exception):
    pass


def read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS:
                raise WorklineCsvError(
                    f"invalid header: expected {HEADERS}, got {reader.fieldnames}"
                )
            rows = []
            for index, row in enumerate(reader, start=2):
                if row.get(None):
                    raise WorklineCsvError(f"row {index} has extra fields: {row[None]}")
                normalized = {key: (row.get(key) or "").strip() for key in HEADERS}
                rows.append(normalized)
            return rows
    except csv.Error as exc:
        raise WorklineCsvError(f"CSV parse error: {exc}") from exc
    except OSError as exc:
        raise WorklineCsvError(str(exc)) from exc


def write_rows_atomic(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in HEADERS})
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def split_deps(value: str) -> list[str]:
    return [item for item in value.split() if item]


def dep_satisfied(row: dict[str, str]) -> bool:
    return row["state"] in SATISFYING_STATES


def commit_valid(value: str) -> bool:
    return value == "no-change" or bool(COMMIT_RE.fullmatch(value))


def detect_cycle(rows: list[dict[str, str]]) -> list[str] | None:
    graph = {row["id"]: split_deps(row["depends_on"]) for row in rows}
    color: dict[str, int] = {key: 0 for key in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = 1
        stack.append(node)
        for dep in graph.get(node, []):
            if color.get(dep) == 1:
                return stack[stack.index(dep):] + [dep]
            if color.get(dep) == 0:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        color[node] = 2
        return None

    for node in graph:
        if color[node] == 0:
            found = visit(node)
            if found:
                return found
    return None


def validate_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise WorklineCsvError("tasks.csv must contain at least the REVIEW row")

    ids: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        task_id = row["id"]
        if not task_id:
            raise WorklineCsvError(f"row {index} has empty id")
        if task_id in seen:
            raise WorklineCsvError(f"duplicate id: {task_id}")
        seen.add(task_id)
        ids.append(task_id)

        if row["mode"] not in MODES:
            raise WorklineCsvError(f"{task_id}: invalid mode {row['mode']!r}")
        if row["state"] not in STATES:
            raise WorklineCsvError(f"{task_id}: invalid state {row['state']!r}")
        if row["commit"] and not commit_valid(row["commit"]):
            raise WorklineCsvError(
                f"{task_id}: invalid commit {row['commit']!r}; "
                "expected no-change or a 7-64 character hexadecimal hash"
            )
        if task_id != "REVIEW" and not row["verification"]:
            raise WorklineCsvError(f"{task_id}: verification is required")

    if ids[-1] != "REVIEW":
        raise WorklineCsvError("last row must be REVIEW")
    if ids.count("REVIEW") != 1:
        raise WorklineCsvError("REVIEW must appear exactly once")
    if rows[-1]["depends_on"]:
        raise WorklineCsvError(
            "REVIEW depends_on must be empty; REVIEW implicitly depends on every task"
        )

    id_set = set(ids)
    for row in rows:
        task_id = row["id"]
        for dep in split_deps(row["depends_on"]):
            if dep not in id_set:
                raise WorklineCsvError(f"{task_id}: unknown dependency {dep}")
            if dep == task_id:
                raise WorklineCsvError(f"{task_id}: cannot depend on itself")
            if task_id != "REVIEW" and dep == "REVIEW":
                raise WorklineCsvError(
                    f"{task_id}: cannot depend on REVIEW; "
                    "REVIEW implicitly depends on every non-REVIEW task"
                )

    cycle = detect_cycle(rows)
    if cycle:
        raise WorklineCsvError("dependency cycle: " + " -> ".join(cycle))


def validate_file(path: Path) -> list[dict[str, str]]:
    rows = read_rows(path)
    validate_rows(rows)
    return rows


def read_run_sections(csv_path: Path) -> set[str] | None:
    run_path = csv_path.parent / "run.md"
    try:
        text = run_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read run.md: {exc}") from exc
    return set(RUN_SECTION_RE.findall(text))


def read_prd_requirements(csv_path: Path) -> set[str] | None:
    """返回 prd.md 中 ### FR-N 小节的编号集合；prd.md 不存在时返回 None。"""
    prd_path = csv_path.parent / "prd.md"
    try:
        text = prd_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read prd.md: {exc}") from exc
    return set(FR_HEADING_RE.findall(text))


def build_warnings(
    rows: list[dict[str, str]],
    csv_path: Path,
    allow_empty_refs: bool = False,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    sections = read_run_sections(csv_path)

    for row in rows:
        task_id = row["id"]
        if row["state"] == "done":
            if not row["commit"]:
                warnings.append(
                    {
                        "code": "commit-missing",
                        "task_id": task_id,
                        "message": "state=done 但 commit 为空，提交收口未完成",
                    }
                )
            if sections is None:
                warnings.append(
                    {
                        "code": "run-log-missing",
                        "task_id": task_id,
                        "message": "state=done 但 run.md 不存在",
                    }
                )
            elif task_id not in sections:
                warnings.append(
                    {
                        "code": "run-log-missing",
                        "task_id": task_id,
                        "message": f"state=done 但 run.md 中没有 ## {task_id} 小节",
                    }
                )
        if row["state"] in EXCEPTION_STATES:
            warnings.append(
                {
                    "code": "exception-state",
                    "task_id": task_id,
                    "message": f"state={row['state']}；notes: {row['notes'] or '无说明'}",
                }
            )
        if task_id == "REVIEW":
            continue
        if (
            row["mode"] == "AFK"
            and row["verification"]
            and not COMMAND_HINT_RE.search(row["verification"])
        ):
            warnings.append(
                {
                    "code": "verification-weak",
                    "task_id": task_id,
                    "message": (
                        "mode=AFK 但 verification 中看不到可执行命令；"
                        "无人值守任务的验证必须机器可判定，否则应改为 HITL"
                    ),
                }
            )
        if not allow_empty_refs and not row["refs"]:
            warnings.append(
                {
                    "code": "refs-missing",
                    "task_id": task_id,
                    "message": (
                        "refs 为空，执行时没有任何材料清单可加载；"
                        "确实不需要材料时用 --allow-empty-refs 豁免"
                    ),
                }
            )

    warnings.extend(build_coverage_warnings(rows, csv_path))
    return warnings


def build_coverage_warnings(
    rows: list[dict[str, str]], csv_path: Path
) -> list[dict[str, str]]:
    """回查 prd.md 的 FR 编号是否都被至少一条任务的 refs 引用。"""
    requirements = read_prd_requirements(csv_path)
    if not requirements:
        return []

    covered: set[str] = set()
    for row in rows:
        covered.update(FR_REF_RE.findall(row["refs"]))

    return [
        {
            "code": "fr-uncovered",
            "task_id": fr_id,
            "message": f"prd.md 的 {fr_id} 没有被任何任务的 refs 引用，可能漏拆",
        }
        for fr_id in sorted(requirements - covered, key=lambda item: int(item[3:]))
    ]


def find_row(rows: list[dict[str, str]], task_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == task_id:
            return row
    raise WorklineCsvError(f"unknown task id: {task_id}")


def validate_transition(
    row: dict[str, str], updates: dict[str, str], csv_path: Path
) -> None:
    new_state = updates.get("state", row["state"])
    if new_state not in STATES:
        raise WorklineCsvError(f"invalid state: {new_state}")
    if row["state"] == "todo" and new_state == "done":
        raise WorklineCsvError("cannot change state directly from todo to done; set doing first")

    effective_notes = updates.get("notes", row["notes"])
    if new_state in EXCEPTION_STATES and not effective_notes.strip():
        raise WorklineCsvError(f"state={new_state} requires notes")

    if new_state != "done":
        return

    task_id = row["id"]
    sections = read_run_sections(csv_path)
    if sections is None:
        raise WorklineCsvError(
            f"{task_id}: cannot set state=done because run.md does not exist; "
            f"write the ## {task_id} section first"
        )
    if task_id not in sections:
        raise WorklineCsvError(
            f"{task_id}: cannot set state=done because run.md has no ## {task_id} section; "
            "write the run log before closing the task"
        )

    effective_commit = updates.get("commit", row["commit"]).strip()
    if not effective_commit and not effective_notes.strip():
        raise WorklineCsvError(
            f"{task_id}: cannot set state=done with an empty commit unless notes explain why; "
            "pass --commit <hash|no-change>, or --commit '' together with --notes"
        )


def on_complete_steps(row: dict[str, str]) -> list[str]:
    task_id = row["id"]
    if task_id == "REVIEW":
        return [
            "逐项核对 REVIEW 检查清单",
            "最终结论写入 run.md 的 ## REVIEW 一节",
            "判断本次任务是否产生可复用项目知识，有则交给 $workline-archive 写入 .workline/notes/",
            "set <tasks.csv> REVIEW --state done --commit no-change",
        ]
    return [
        "按 verification 执行验证，记录真实命令与真实输出",
        "自检范围纪律：没有顺手重构、没有为当前不存在的场景加抽象或配置、"
        "没有加投机性兜底分支、没有改任务范围外的文件、在行为真正所在的位置修而不是在调用方打补丁",
        f"在 run.md 追加 ## {task_id} 一节",
        f"set <tasks.csv> {task_id} --state done --commit <hash|no-change>",
    ]


def print_warnings(warnings: list[dict[str, str]]) -> None:
    for warning in warnings:
        print(f"- {warning['code']}: {warning['task_id']} - {warning['message']}")


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path)
    warnings = build_warnings(rows, path, allow_empty_refs=args.allow_empty_refs)
    print(f"OK: {len(rows)} rows, {len(warnings)} warnings")
    print_warnings(warnings)
    return 0


def command_set(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path)
    row = find_row(rows, args.task_id)

    updates: dict[str, str] = {}
    for key in ("state", "commit", "refs", "notes"):
        value = getattr(args, key)
        if value is not None:
            updates[key] = value

    if args.append_notes:
        existing = row["notes"].strip()
        updates["notes"] = f"{existing}; {args.append_notes}" if existing else args.append_notes
    if args.append_refs:
        existing = row["refs"].strip()
        updates["refs"] = f"{existing} {args.append_refs}".strip()

    if not updates:
        raise WorklineCsvError("no updates provided")

    validate_transition(row, updates, path)
    row.update(updates)
    validate_rows(rows)
    write_rows_atomic(path, rows)
    print(f"OK: updated {args.task_id}")
    print_warnings(build_warnings(rows, path))
    return 0


def command_next(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path)
    warnings = build_warnings(rows, path)
    by_id = {row["id"]: row for row in rows}
    non_review = rows[:-1]
    review = rows[-1]

    selected: dict[str, str] | None = None
    for row in non_review:
        if row["state"] not in OPEN_STATES:
            continue
        if all(dep_satisfied(by_id[dep]) for dep in split_deps(row["depends_on"])):
            selected = row
            break

    if selected is None and review["state"] in OPEN_STATES:
        if all(dep_satisfied(row) for row in non_review):
            selected = review

    if selected is not None:
        payload = dict(selected)
        payload["on_complete"] = on_complete_steps(selected)
        payload["warnings"] = warnings
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    unfinished = [row for row in non_review if not dep_satisfied(row)]
    if unfinished:
        detail: dict[str, str] = {}
        for row in unfinished:
            if row["state"] == "blocked":
                detail[row["id"]] = f"state=blocked；{row['notes'] or '无说明'}"
            else:
                unmet = [
                    f"{dep}={by_id[dep]['state']}"
                    for dep in split_deps(row["depends_on"])
                    if not dep_satisfied(by_id[dep])
                ]
                detail[row["id"]] = f"state={row['state']}，未满足依赖：{' '.join(unmet) or '无'}"
        reason = "needs-attention"
    elif review["state"] == "done":
        detail = {}
        reason = "all-closed"
    else:
        detail = {
            "REVIEW": f"state={review['state']}；{review['notes'] or '无说明'}"
        }
        reason = "needs-attention"

    print(
        json.dumps(
            {"next": None, "reason": reason, "detail": detail, "warnings": warnings},
            ensure_ascii=False,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workline CSV helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate tasks.csv")
    validate_parser.add_argument("csv_path")
    validate_parser.add_argument(
        "--allow-empty-refs",
        action="store_true",
        help="suppress refs-missing warnings",
    )
    validate_parser.set_defaults(func=command_validate)

    set_parser = subparsers.add_parser("set", help="update one task row")
    set_parser.add_argument("csv_path")
    set_parser.add_argument("task_id")
    set_parser.add_argument("--state")
    set_parser.add_argument("--commit")
    set_parser.add_argument("--refs")
    set_parser.add_argument("--append-refs")
    set_parser.add_argument("--notes")
    set_parser.add_argument("--append-notes")
    set_parser.set_defaults(func=command_set)

    next_parser = subparsers.add_parser("next", help="print next runnable task as JSON")
    next_parser.add_argument("csv_path")
    next_parser.set_defaults(func=command_next)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except WorklineCsvError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
