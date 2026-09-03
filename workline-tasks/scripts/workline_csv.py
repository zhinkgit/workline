#!/usr/bin/env python3
"""Validate and update Workline tasks.csv and run.md stage gates.

同步副本：workline-tasks/scripts/、workline-run/scripts/、
workline-review/scripts/、workline-archive/scripts/
四份必须逐字一致，用 .github/maintenance/repo_checks.py 校验。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
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
PLAN_FIELDS = ("id", "depends_on", "mode", "title", "description", "verification")

GATE_IDS = ("materials", "prd-review", "tasks-review", "execute")
GATE_STATUSES = {
    "materials": {"未确认", "CONFIRMED", "WAIVED"},
    "prd-review": {"未审查", "PASS", "REVISE", "BLOCKED"},
    "tasks-review": {"未审查", "PASS", "REVISE", "BLOCKED"},
    "execute": {"未确认", "CONFIRMED"},
}
GATE_DEFAULT_STATUS = {
    "materials": "未确认",
    "prd-review": "未审查",
    "tasks-review": "未审查",
    "execute": "未确认",
}

MODES = {"AFK", "HITL"}
STATES = {"todo", "doing", "done", "blocked", "skipped"}
OPEN_STATES = {"todo", "doing"}
EXCEPTION_STATES = {"blocked", "skipped"}
SATISFYING_STATES = {"done", "skipped"}
TERMINAL_STATES = {"done", "skipped"}

RUN_SECTION_RE = re.compile(r"^##\s+(\S+)", re.MULTILINE)
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
REQ_HEADING_RE = re.compile(r"^###\s+((?:FR|NFR)-[1-9]\d*)\b", re.MULTILINE)
PADDED_REQ_HEADING_RE = re.compile(r"^###\s+((?:FR|NFR)-0\d+)\b", re.MULTILINE)
REQ_REF_RE = re.compile(r"\b(?:FR|NFR)-[1-9]\d*\b")
PADDED_REQ_REF_RE = re.compile(r"\b(?:FR|NFR)-0\d+\b")
FUNCTION_HEADING_RE = re.compile(r"^##\s+功能要求\s*$", re.MULTILINE)
NEXT_H2_RE = re.compile(r"^##\s+", re.MULTILINE)
REF_TOKEN_RE = re.compile(r"^(?:(?:FR|NFR)-[1-9]\d*|references/\S+|evidence/\S+)$")
TASK_ID_RE = re.compile(r"^T\d{3,}$")
BLOCKING_WARNING_CODES = {
    "fr-headings-missing",
    "fr-uncovered",
    "nfr-uncovered",
    "refs-invalid",
    "refs-not-found",
    "req-id-padded",
}
RUN_FIELD_RE = {
    "实现": re.compile(r"^-\s*实现：\s*(\S.*)$", re.MULTILINE),
    "验证": re.compile(r"^-\s*验证：\s*(\S.*)$", re.MULTILINE),
    "输出": re.compile(r"^-\s*输出：\s*(\S.*)$", re.MULTILINE),
}
PLACEHOLDER_VALUES = {"", "...", "TBD", "待填", "占位"}
GATE_SECTION_RE = re.compile(
    r"^##[ \t]+阶段门禁[ \t]*\r?\n.*?(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)


class WorklineCsvError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        raise WorklineCsvError(f"required artifact not found: {path}") from None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read artifact {path}: {exc}") from exc


def task_plan_digest(rows: list[dict[str, str]]) -> str:
    plan: list[dict[str, object]] = []
    for row in rows:
        item: dict[str, object] = {field: row[field] for field in PLAN_FIELDS}
        item["refs"] = [
            token for token in split_refs(row["refs"]) if not token.startswith("evidence/")
        ]
        plan.append(item)
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def task_plan_digest_from_path(path: Path) -> str:
    rows = read_rows(path)
    validate_rows(rows)
    return task_plan_digest(rows)


def write_text_atomic(path: Path, text: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def write_csv_atomic(path: Path, headers: list[str], rows: Iterable[dict[str, str]]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def read_named_csv(path: Path, headers: list[str], empty_message: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != headers:
                raise WorklineCsvError(
                    f"{path.name}: invalid header: expected {headers}, got {reader.fieldnames}"
                )
            rows = []
            for index, row in enumerate(reader, start=2):
                if row.get(None):
                    raise WorklineCsvError(
                        f"{path.name} row {index} has extra fields: {row[None]}"
                    )
                rows.append({key: (row.get(key) or "").strip() for key in headers})
            return rows
    except FileNotFoundError:
        raise WorklineCsvError(empty_message) from None
    except csv.Error as exc:
        raise WorklineCsvError(f"{path.name} CSV parse error: {exc}") from exc
    except OSError as exc:
        raise WorklineCsvError(str(exc)) from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    return read_named_csv(path, HEADERS, f"tasks.csv not found: {path}")


def write_rows_atomic(path: Path, rows: Iterable[dict[str, str]]) -> None:
    write_csv_atomic(path, HEADERS, rows)


def split_deps(value: str) -> list[str]:
    return [item for item in value.split() if item]


def split_refs(value: str) -> list[str]:
    return [item for item in value.split() if item]


def ref_path_is_safe(token: str) -> bool:
    parts = token.split("/")
    return (
        "\\" not in token
        and len(parts) >= 2
        and all(part not in {"", ".", ".."} for part in parts)
    )


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


def git_repo_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def git_commit_exists(cwd: Path, commit: str) -> bool | None:
    root = git_repo_root(cwd)
    if root is None:
        return None
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", commit],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0 and result.stdout.strip() == "commit"


def git_non_workline_dirty(cwd: Path) -> list[str]:
    root = git_repo_root(cwd)
    if root is None:
        return []
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    dirty: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip().replace("\\", "/")
        if rel.startswith(".workline/") or "/.workline/" in f"/{rel}":
            continue
        dirty.append(rel)
    return dirty


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
        if task_id != "REVIEW" and not TASK_ID_RE.fullmatch(task_id):
            raise WorklineCsvError(
                f"{task_id}: invalid task id; expected T followed by at least three digits"
            )
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
        if task_id != "REVIEW":
            if not row["verification"]:
                raise WorklineCsvError(f"{task_id}: verification is required")
            if not row["title"]:
                raise WorklineCsvError(f"{task_id}: title is required")
            if not row["description"]:
                raise WorklineCsvError(f"{task_id}: description is required")

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


def read_run_text(csv_path: Path) -> str | None:
    run_path = csv_path.parent / "run.md"
    try:
        return run_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read run.md: {exc}") from exc


def read_run_sections(csv_path: Path) -> dict[str, str] | None:
    text = read_run_text(csv_path)
    if text is None:
        return None
    sections: dict[str, str] = {}
    parts = re.split(r"(?m)^(?=##\s+\S)", text)
    for part in parts:
        match = RUN_SECTION_RE.match(part)
        if match:
            sections[match.group(1)] = part
    return sections


def run_section_is_complete(body: str) -> bool:
    for name, pattern in RUN_FIELD_RE.items():
        match = pattern.search(body)
        if not match:
            return False
        value = match.group(1).strip()
        if value in PLACEHOLDER_VALUES:
            return False
        if name in {"实现", "验证", "输出"} and value in {"无", "无。"}:
            return False
    return True


def read_prd_text(csv_path: Path) -> str | None:
    prd_path = csv_path.parent / "prd.md"
    try:
        return prd_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read prd.md: {exc}") from exc


def read_prd_requirements(csv_path: Path) -> set[str] | None:
    text = read_prd_text(csv_path)
    if text is None:
        return None
    return set(REQ_HEADING_RE.findall(text))


def prd_function_section_lacks_headings(text: str) -> bool:
    match = FUNCTION_HEADING_RE.search(text)
    if not match:
        return False
    start = match.end()
    next_heading = NEXT_H2_RE.search(text, start)
    section = text[start: next_heading.start() if next_heading else len(text)]
    if REQ_HEADING_RE.search(section):
        return False
    stripped = re.sub(r"<!--.*?-->", "", section, flags=re.S)
    stripped = re.sub(r"`[^`]+`", "", stripped)
    stripped = re.sub(r"\s+", "", stripped)
    return bool(stripped)


def default_gate_rows() -> list[dict[str, str]]:
    return [
        {
            "gate": gate_id,
            "status": GATE_DEFAULT_STATUS[gate_id],
            "at": "",
            "actor": "",
            "digest": "",
            "notes": "",
        }
        for gate_id in GATE_IDS
    ]


def run_md_from(path: Path) -> Path:
    path = path.resolve()
    if path.is_file():
        if path.name == "run.md":
            return path
        return path.parent / "run.md"
    return path / "run.md"


def _gate_cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip()


def render_gate_section(rows: list[dict[str, str]]) -> str:
    lines = [
        "## 阶段门禁",
        "",
        "| 门 | 状态 | 时间 | 审查方 | 产物摘要 | 备注 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    by_id = {row["gate"]: row for row in rows}
    for gate_id in GATE_IDS:
        row = by_id[gate_id]
        lines.append(
            "| "
            + " | ".join(
                [
                    gate_id,
                    _gate_cell(row.get("status", "")),
                    _gate_cell(row.get("at", "")),
                    _gate_cell(row.get("actor", "")),
                    _gate_cell(row.get("digest", "")),
                    _gate_cell(row.get("notes", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "本表由 `workline_csv.py gates-set` 维护。后面只追加任务日志，不要删改这一节。",
            "",
        ]
    )
    return "\n".join(lines)


def _is_table_separator(cell: str) -> bool:
    return bool(cell) and set(cell) <= {"-", ":"}


def parse_gate_rows(text: str) -> list[dict[str, str]]:
    match = GATE_SECTION_RE.search(text)
    if not match:
        raise WorklineCsvError("run.md 缺少 ## 阶段门禁 小节")
    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in match.group(0).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        gate_id = cells[0]
        if gate_id in {"门", ""} or _is_table_separator(gate_id):
            continue
        if gate_id not in GATE_STATUSES:
            raise WorklineCsvError(f"unknown gate: {gate_id}")
        status = cells[1]
        if status not in GATE_STATUSES[gate_id]:
            raise WorklineCsvError(
                f"{gate_id}: invalid status {status!r}; expected one of {sorted(GATE_STATUSES[gate_id])}"
            )
        if gate_id in seen:
            raise WorklineCsvError(f"duplicate gate: {gate_id}")
        seen.add(gate_id)
        # 兼容旧的五列门禁表；旧 PASS 因无摘要会被判为过期。
        digest = cells[4] if len(cells) >= 6 else ""
        notes = cells[5] if len(cells) >= 6 else cells[4]
        parsed.append(
            {
                "gate": gate_id,
                "status": status,
                "at": cells[2],
                "actor": cells[3],
                "digest": digest,
                "notes": notes,
            }
        )
    missing = [gate_id for gate_id in GATE_IDS if gate_id not in seen]
    if missing:
        raise WorklineCsvError("run.md 阶段门禁 missing rows: " + ", ".join(missing))
    by_id = {row["gate"]: row for row in parsed}
    return [by_id[gate_id] for gate_id in GATE_IDS]


def read_gates(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise WorklineCsvError(f"run.md not found: {path}") from None
    except OSError as exc:
        raise WorklineCsvError(f"cannot read run.md: {exc}") from exc
    return parse_gate_rows(text)


def write_gates(path: Path, rows: list[dict[str, str]]) -> None:
    section = render_gate_section(rows)
    if not path.exists():
        write_text_atomic(path, section)
        return
    text = path.read_text(encoding="utf-8")
    match = GATE_SECTION_RE.search(text)
    if match:
        new_text = text[: match.start()] + section + text[match.end() :]
    else:
        heading = re.match(r"^#(?!#)[^\n]*\n?", text)
        if heading:
            rest = text[heading.end() :].lstrip("\n")
            new_text = heading.group(0) + "\n" + section + rest
        else:
            new_text = section + text.lstrip("\n")
    write_text_atomic(path, new_text)


def find_gate(rows: list[dict[str, str]], gate_id: str) -> dict[str, str]:
    for row in rows:
        if row["gate"] == gate_id:
            return row
    raise WorklineCsvError(f"unknown gate: {gate_id}")


def reset_gate(rows: list[dict[str, str]], gate_id: str, reason: str) -> None:
    row = find_gate(rows, gate_id)
    row["status"] = GATE_DEFAULT_STATUS[gate_id]
    row["at"] = ""
    row["actor"] = ""
    row["digest"] = ""
    row["notes"] = reason


def artifact_digest(active_dir: Path, gate_id: str) -> str:
    if gate_id == "prd-review":
        return file_sha256(active_dir / "prd.md")
    if gate_id in {"tasks-review", "execute"}:
        return task_plan_digest_from_path(active_dir / "tasks.csv")
    return ""


def gate_chain_errors(rows: list[dict[str, str]], active_dir: Path) -> list[str]:
    by_id = {row["gate"]: row for row in rows}
    errors: list[str] = []

    if by_id["prd-review"]["status"] == "PASS":
        if by_id["materials"]["status"] not in {"CONFIRMED", "WAIVED"}:
            errors.append("prd-review=PASS requires materials=CONFIRMED or WAIVED")
    if by_id["tasks-review"]["status"] == "PASS":
        if by_id["prd-review"]["status"] != "PASS":
            errors.append("tasks-review=PASS requires prd-review=PASS")
    if by_id["execute"]["status"] == "CONFIRMED":
        if by_id["tasks-review"]["status"] != "PASS":
            errors.append("execute=CONFIRMED requires tasks-review=PASS")

    for gate_id, active_status in (
        ("prd-review", "PASS"),
        ("tasks-review", "PASS"),
        ("execute", "CONFIRMED"),
    ):
        row = by_id[gate_id]
        if row["status"] != active_status:
            continue
        expected = artifact_digest(active_dir, gate_id)
        if not row.get("digest"):
            errors.append(f"{gate_id} has no artifact digest; review or confirm it again")
        elif row["digest"] != expected:
            errors.append(f"{gate_id} is stale because its reviewed artifact changed")
    return errors


def require_execution_gates(active_dir: Path) -> None:
    rows = read_gates(active_dir / "run.md")
    errors = gate_chain_errors(rows, active_dir)
    required = {
        "materials": {"CONFIRMED", "WAIVED"},
        "prd-review": {"PASS"},
        "tasks-review": {"PASS"},
        "execute": {"CONFIRMED"},
    }
    by_id = {row["gate"]: row for row in rows}
    for gate_id, allowed in required.items():
        if by_id[gate_id]["status"] not in allowed:
            errors.append(
                f"{gate_id} status is {by_id[gate_id]['status']!r}, required one of {sorted(allowed)}"
            )
    if errors:
        raise WorklineCsvError("execution gate check failed:\n- " + "\n- ".join(errors))


def parse_require_item(item: str) -> tuple[str, set[str]]:
    if "=" not in item:
        raise WorklineCsvError(f"invalid --require {item!r}; expected gate=STATUS[,STATUS]")
    gate_id, _, raw_statuses = item.partition("=")
    gate_id = gate_id.strip()
    statuses = {part.strip() for part in raw_statuses.split(",") if part.strip()}
    if gate_id not in GATE_STATUSES:
        raise WorklineCsvError(f"unknown gate: {gate_id}")
    unknown = statuses - GATE_STATUSES[gate_id]
    if unknown:
        raise WorklineCsvError(
            f"{gate_id}: invalid required status {sorted(unknown)}; "
            f"expected one of {sorted(GATE_STATUSES[gate_id])}"
        )
    if not statuses:
        raise WorklineCsvError(f"{gate_id}: no status given")
    return gate_id, statuses


def collect_done_errors(rows: list[dict[str, str]], csv_path: Path) -> list[str]:
    errors: list[str] = []
    sections = read_run_sections(csv_path)
    cwd = csv_path.parent
    for row in rows:
        if row["state"] != "done":
            continue
        task_id = row["id"]
        if not row["commit"]:
            if not row["notes"].strip():
                errors.append(
                    f"{task_id}: state=done 但 commit 为空且 notes 未说明原因"
                )
        elif row["commit"] != "no-change":
            exists = git_commit_exists(cwd, row["commit"])
            if exists is None:
                errors.append(
                    f"{task_id}: commit {row['commit']} 无法在 git 中核验；"
                    "当前目录不是 Git 仓库或 git 不可用"
                )
            elif not exists:
                errors.append(f"{task_id}: commit {row['commit']} 不是本仓库中的提交")
        if sections is None:
            errors.append(f"{task_id}: state=done 但 run.md 不存在")
        elif task_id not in sections:
            errors.append(f"{task_id}: state=done 但 run.md 中没有 ## {task_id} 小节")
        elif not run_section_is_complete(sections[task_id]):
            errors.append(
                f"{task_id}: run.md 的 ## {task_id} 小节不完整，"
                "需要非空的「实现 / 验证 / 输出」三条"
            )
    return errors


def validate_file(path: Path, *, check_done: bool = False) -> list[dict[str, str]]:
    rows = read_rows(path)
    validate_rows(rows)
    if check_done:
        errors = collect_done_errors(rows, path)
        if errors:
            raise WorklineCsvError("done-state checks failed:\n- " + "\n- ".join(errors))
    return rows


def build_warnings(
    rows: list[dict[str, str]],
    csv_path: Path,
    allow_empty_refs: bool = False,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    by_id = {row["id"]: row for row in rows}
    prd_text = read_prd_text(csv_path)
    cwd = csv_path.parent

    if prd_text is not None:
        padded_headings = PADDED_REQ_HEADING_RE.findall(prd_text)
        if padded_headings:
            warnings.append(
                {
                    "code": "req-id-padded",
                    "task_id": padded_headings[0],
                    "message": "prd.md 的需求编号带前导零，必须写成 FR-1 / NFR-1",
                }
            )
        if prd_function_section_lacks_headings(prd_text):
            warnings.append(
                {
                    "code": "fr-headings-missing",
                    "task_id": "PRD",
                    "message": "prd.md 有「功能要求」但没有 ### FR-N 小节，覆盖性检查无法运行",
                }
            )

    for row in rows:
        task_id = row["id"]
        if row["state"] in EXCEPTION_STATES:
            warnings.append(
                {
                    "code": "exception-state",
                    "task_id": task_id,
                    "message": f"state={row['state']}；notes: {row['notes'] or '无说明'}",
                }
            )
        for dep in split_deps(row["depends_on"]):
            parent = by_id.get(dep)
            if parent and parent["state"] == "skipped":
                warnings.append(
                    {
                        "code": "skipped-unblocks",
                        "task_id": task_id,
                        "message": f"依赖 {dep} 为 skipped，后继仍可执行；确认这不是空地基施工",
                    }
                )
        if task_id == "REVIEW":
            continue
        refs = split_refs(row["refs"])
        if not allow_empty_refs and not refs:
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
        for token in refs:
            if PADDED_REQ_REF_RE.search(token):
                warnings.append(
                    {
                        "code": "req-id-padded",
                        "task_id": task_id,
                        "message": f"refs 含带前导零的编号 {token}，无法匹配 FR-1 / NFR-1",
                    }
                )
            elif not REF_TOKEN_RE.fullmatch(token) or (
                token.startswith(("references/", "evidence/"))
                and not ref_path_is_safe(token)
            ):
                warnings.append(
                    {
                        "code": "refs-invalid",
                        "task_id": task_id,
                        "message": (
                            f"refs 项 {token} 不是 FR/NFR 编号、references/ 或 evidence/ 路径"
                        ),
                    }
                )
            elif token.startswith(("references/", "evidence/")):
                if not (cwd / token).exists():
                    warnings.append(
                        {
                            "code": "refs-not-found",
                            "task_id": task_id,
                            "message": f"引用路径不存在：{token}",
                        }
                    )

    dirty = git_non_workline_dirty(csv_path.parent)
    if dirty:
        warnings.append(
            {
                "code": "worktree-dirty",
                "task_id": "GIT",
                "message": "工作区有非 .workline 的未提交改动：" + ", ".join(dirty[:8]),
            }
        )

    warnings.extend(build_coverage_warnings(rows, csv_path))
    return warnings


def build_coverage_warnings(
    rows: list[dict[str, str]], csv_path: Path
) -> list[dict[str, str]]:
    requirements = read_prd_requirements(csv_path)
    if not requirements:
        return []

    covered: set[str] = set()
    for row in rows:
        if row["id"] == "REVIEW":
            continue
        covered.update(
            token for token in split_refs(row["refs"]) if REQ_REF_RE.fullmatch(token)
        )

    def sort_key(item: str) -> tuple[str, int]:
        kind, _, number = item.partition("-")
        return kind, int(number)

    return [
        {
            "code": "fr-uncovered" if item.startswith("FR-") else "nfr-uncovered",
            "task_id": item,
            "message": f"prd.md 的 {item} 没有被任何任务的 refs 引用，可能漏拆",
        }
        for item in sorted(requirements - covered, key=sort_key)
    ]


def find_row(rows: list[dict[str, str]], task_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == task_id:
            return row
    raise WorklineCsvError(f"unknown task id: {task_id}")


def validate_transition(
    rows: list[dict[str, str]],
    row: dict[str, str],
    updates: dict[str, str],
    csv_path: Path,
    *,
    force: bool = False,
) -> None:
    new_state = updates.get("state", row["state"])
    if new_state not in STATES:
        raise WorklineCsvError(f"invalid state: {new_state}")
    if (
        row["state"] in TERMINAL_STATES
        and new_state != row["state"]
        and not force
    ):
        raise WorklineCsvError(
            f"cannot leave terminal state {row['state']} without --force"
        )
    if row["state"] == "todo" and new_state == "done":
        raise WorklineCsvError("cannot change state directly from todo to done; set doing first")

    if new_state in {"doing", "done"}:
        if row["id"] == "REVIEW":
            unfinished = [
                item["id"] for item in rows[:-1] if not dep_satisfied(item)
            ]
            if unfinished:
                raise WorklineCsvError(
                    "REVIEW cannot start before all tasks are closed: " + ", ".join(unfinished)
                )
        else:
            by_id = {item["id"]: item for item in rows}
            unmet = [
                dep
                for dep in split_deps(row["depends_on"])
                if not dep_satisfied(by_id[dep])
            ]
            if unmet:
                raise WorklineCsvError(
                    f"{row['id']}: dependencies are not satisfied: " + ", ".join(unmet)
                )

    effective_notes = updates.get("notes", row["notes"])
    if new_state in EXCEPTION_STATES and not effective_notes.strip():
        raise WorklineCsvError(f"state={new_state} requires notes")

    effective_commit = updates.get("commit", row["commit"]).strip()
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
    if not run_section_is_complete(sections[task_id]):
        raise WorklineCsvError(
            f"{task_id}: run.md 的 ## {task_id} 小节不完整，"
            "先写非空的「实现 / 验证 / 输出」三条再标记完成"
        )

    if not effective_commit and not effective_notes.strip():
        raise WorklineCsvError(
            f"{task_id}: cannot set state=done with an empty commit unless notes explain why; "
            "pass --commit <hash|no-change>, or --commit '' together with --notes"
        )
    if effective_commit and effective_commit != "no-change":
        exists = git_commit_exists(csv_path.parent, effective_commit)
        if exists is None:
            raise WorklineCsvError(
                f"{task_id}: commit {effective_commit} 无法在 git 中核验；"
                "不是 Git 仓库时用 --commit no-change 或 --commit '' --notes"
            )
        if not exists:
            raise WorklineCsvError(
                f"{task_id}: commit {effective_commit} 不是本仓库中的提交"
            )


def on_complete_steps(row: dict[str, str]) -> list[str]:
    task_id = row["id"]
    if task_id == "REVIEW":
        return [
            "逐项核对 REVIEW 检查清单",
            "最终结论写入 run.md 的 ## REVIEW 一节，且包含非空的实现 / 验证 / 输出",
            "判断本次任务是否产生可复用项目知识，有则交给 $workline-archive 写入 .workline/notes/",
            "set <tasks.csv> REVIEW --state done --commit no-change",
        ]
    steps = []
    if row["mode"] == "HITL":
        steps.append(
            "本任务是 HITL：先请求用户参与；本轮无法参与则 set blocked 并写 notes，"
            "不要保持 doing，以免挡住独立 AFK 任务"
        )
    steps.extend(
        [
            "按 verification 执行验证，记录真实命令与真实输出",
            "自检范围纪律：没有顺手重构、没有为当前不存在的场景加抽象或配置、"
            "没有加投机性兜底分支、没有改任务范围外的文件、在行为真正所在的位置修而不是在调用方打补丁",
            f"在 run.md 追加 ## {task_id} 一节，写明实现 / 验证 / 输出",
            "任务级提交不要暂存 .workline/",
            f"set <tasks.csv> {task_id} --state done --commit <hash|no-change>",
        ]
    )
    return steps


def print_warnings(warnings: list[dict[str, str]]) -> None:
    for warning in warnings:
        print(f"- {warning['code']}: {warning['task_id']} - {warning['message']}")


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path, check_done=True)
    warnings = build_warnings(rows, path, allow_empty_refs=args.allow_empty_refs)
    print(f"OK: {len(rows)} rows, {len(warnings)} warnings")
    print_warnings(warnings)
    return 0


def command_set(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path, check_done=False)
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

    new_state = updates.get("state", row["state"])
    if args.state is not None and new_state != "todo":
        require_execution_gates(path.parent)
    validate_transition(rows, row, updates, path, force=args.force)
    row.update(updates)
    validate_rows(rows)
    write_rows_atomic(path, rows)
    print(f"OK: updated {args.task_id}")
    print_warnings(build_warnings(rows, path))
    return 0


def select_next(
    rows: list[dict[str, str]],
) -> tuple[dict[str, str] | None, str, dict[str, str]]:
    by_id = {row["id"]: row for row in rows}
    non_review = rows[:-1]
    review = rows[-1]

    ready_afk: list[dict[str, str]] = []
    ready_hitl: list[dict[str, str]] = []
    for row in non_review:
        if row["state"] not in OPEN_STATES:
            continue
        if not all(dep_satisfied(by_id[dep]) for dep in split_deps(row["depends_on"])):
            continue
        if row["mode"] == "AFK":
            ready_afk.append(row)
        else:
            ready_hitl.append(row)

    selected = (ready_afk or ready_hitl or [None])[0]
    if selected is None and review["state"] in OPEN_STATES:
        if all(dep_satisfied(row) for row in non_review):
            selected = review

    if selected is not None:
        return selected, "", {}

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
        return None, "needs-attention", detail
    if review["state"] == "done":
        return None, "all-closed", {}
    return None, "needs-attention", {
        "REVIEW": f"state={review['state']}；{review['notes'] or '无说明'}"
    }


def command_next(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path, check_done=True)
    warnings = build_warnings(rows, path)
    selected, reason, detail = select_next(rows)

    if selected is not None:
        payload = dict(selected)
        payload["on_complete"] = on_complete_steps(selected)
        payload["warnings"] = warnings
        payload["hitl"] = selected["id"] != "REVIEW" and selected["mode"] == "HITL"
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print(
        json.dumps(
            {"next": None, "reason": reason, "detail": detail, "warnings": warnings},
            ensure_ascii=False,
        )
    )
    return 0


def command_add(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    require_execution_gates(path.parent)
    rows = validate_file(path, check_done=False)
    task_id = args.task_id
    if task_id == "REVIEW":
        raise WorklineCsvError("cannot add REVIEW; it is created with the CSV")
    if any(row["id"] == task_id for row in rows):
        raise WorklineCsvError(f"duplicate id: {task_id}")
    new_row = {
        "id": task_id,
        "depends_on": args.depends_on or "",
        "mode": args.mode,
        "title": args.title,
        "description": args.description,
        "verification": args.verification,
        "state": "todo",
        "commit": "",
        "refs": args.refs or "",
        "notes": args.notes or "",
    }
    review = rows[-1]
    review["state"] = "todo"
    review["commit"] = ""
    review["notes"] = f"reset after adding {task_id}"
    rows.insert(-1, new_row)
    validate_rows(rows)
    write_rows_atomic(path, rows)

    gate_path = path.parent / "run.md"
    gate_rows = read_gates(gate_path)
    reset_gate(gate_rows, "tasks-review", f"reset after adding {task_id}")
    reset_gate(gate_rows, "execute", f"reset after adding {task_id}")
    write_gates(gate_path, gate_rows)
    print(f"OK: added {task_id}")
    print("NOTICE: tasks-review and execute were reset; REVIEW returned to todo")
    print_warnings(build_warnings(rows, path))
    return 0


def command_gates(args: argparse.Namespace) -> int:
    path = run_md_from(Path(args.path))
    rows = read_gates(path)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def command_gates_set(args: argparse.Namespace) -> int:
    path = run_md_from(Path(args.path))
    if not path.exists():
        if not args.init:
            raise WorklineCsvError(f"run.md not found: {path}; pass --init to create it")
        rows = default_gate_rows()
    else:
        try:
            rows = read_gates(path)
        except WorklineCsvError as exc:
            message = str(exc)
            if "缺少 ## 阶段门禁" in message and args.init:
                rows = default_gate_rows()
            else:
                raise

    gate_id = args.gate
    if gate_id not in GATE_STATUSES:
        raise WorklineCsvError(f"unknown gate: {gate_id}")
    if args.status not in GATE_STATUSES[gate_id]:
        raise WorklineCsvError(
            f"{gate_id}: invalid status {args.status!r}; "
            f"expected one of {sorted(GATE_STATUSES[gate_id])}"
        )
    if args.status != GATE_DEFAULT_STATUS[gate_id] and not (args.actor or "").strip():
        raise WorklineCsvError(f"{gate_id}={args.status} requires --actor")

    by_id = {item["gate"]: item for item in rows}
    active_dir = path.parent
    if gate_id == "prd-review" and args.status == "PASS":
        if by_id["materials"]["status"] not in {"CONFIRMED", "WAIVED"}:
            raise WorklineCsvError(
                "cannot set prd-review=PASS before materials is CONFIRMED or WAIVED"
            )
    if gate_id == "tasks-review" and args.status == "PASS":
        if by_id["prd-review"]["status"] != "PASS":
            raise WorklineCsvError("cannot set tasks-review=PASS before prd-review=PASS")
        stale = [
            item
            for item in gate_chain_errors(rows, active_dir)
            if item.startswith("prd-review")
        ]
        if stale:
            raise WorklineCsvError("cannot pass tasks-review:\n- " + "\n- ".join(stale))
        task_path = active_dir / "tasks.csv"
        task_rows = validate_file(task_path, check_done=True)
        blocking = [
            item
            for item in build_warnings(task_rows, task_path)
            if item["code"] in BLOCKING_WARNING_CODES
        ]
        if blocking:
            raise WorklineCsvError(
                "cannot pass tasks-review with blocking warnings:\n- "
                + "\n- ".join(
                    f"{item['code']}: {item['task_id']} - {item['message']}"
                    for item in blocking
                )
            )
    if gate_id == "execute" and args.status == "CONFIRMED":
        stale = [
            item
            for item in gate_chain_errors(rows, active_dir)
            if not item.startswith("execute")
        ]
        if by_id["tasks-review"]["status"] != "PASS" or stale:
            details = stale or ["tasks-review is not PASS"]
            raise WorklineCsvError("cannot confirm execute:\n- " + "\n- ".join(details))

    row = find_gate(rows, gate_id)
    previous_status = row["status"]
    previous_digest = row.get("digest", "")
    new_digest = (
        artifact_digest(active_dir, gate_id)
        if args.status in {"PASS", "CONFIRMED"}
        else ""
    )
    if gate_id == "prd-review" and args.status == "PASS" and args.keep_downstream:
        if previous_status != "PASS" or not previous_digest or previous_digest != new_digest:
            raise WorklineCsvError(
                "--keep-downstream requires an existing current prd-review=PASS for unchanged prd.md"
            )
    row["status"] = args.status
    row["at"] = now_iso()
    row["actor"] = args.actor or ""
    row["digest"] = new_digest
    if args.notes is not None:
        row["notes"] = args.notes

    if gate_id == "materials" and args.status != previous_status:
        for downstream in ("prd-review", "tasks-review", "execute"):
            reset_gate(rows, downstream, f"reset after materials changed to {args.status}")
    if gate_id == "prd-review" and not args.keep_downstream:
        for downstream in ("tasks-review", "execute"):
            reset_gate(rows, downstream, f"reset after prd-review {args.status}")
    if gate_id == "tasks-review":
        if args.status != "PASS" or previous_status != "PASS" or previous_digest != new_digest:
            reset_gate(rows, "execute", f"reset after tasks-review {args.status}")

    write_gates(path, rows)
    print(f"OK: {gate_id}={args.status}")
    return 0


def command_require_gates(args: argparse.Namespace) -> int:
    path = run_md_from(Path(args.path))
    rows = read_gates(path)
    by_id = {row["gate"]: row for row in rows}
    failures: list[str] = []
    failures.extend(gate_chain_errors(rows, path.parent))
    for item in args.require:
        gate_id, allowed = parse_require_item(item)
        actual = by_id[gate_id]["status"]
        if actual not in allowed:
            failures.append(
                f"{gate_id} status is {actual!r}, required one of {sorted(allowed)}"
            )
    if failures:
        raise WorklineCsvError("gate check failed:\n- " + "\n- ".join(failures))
    print("OK: required gates satisfied")
    return 0


def command_archive_check(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv_path)
    rows = validate_file(csv_path, check_done=True)
    warnings = build_warnings(rows, csv_path)
    errors: list[str] = []

    required = ["brief.md", "prd.md", "tasks.csv", "run.md", "references"]
    for name in required:
        target = csv_path.parent / name
        if name == "references":
            if not target.is_dir():
                errors.append("missing references/")
        elif not target.exists():
            errors.append(f"missing {name}")

    review = rows[-1]
    if review["id"] != "REVIEW":
        errors.append("last row is not REVIEW")
    elif review["state"] != "done":
        errors.append(f"REVIEW state is {review['state']!r}, required done")

    open_ids = [
        row["id"] for row in rows[:-1] if row["state"] in {"todo", "doing", "blocked"}
    ]
    if open_ids:
        errors.append("open tasks remain: " + ", ".join(open_ids))

    for row in rows:
        if row["state"] == "skipped" and not row["notes"].strip():
            errors.append(f"{row['id']}: skipped without notes")
        if row["state"] == "done" and not row["commit"]:
            errors.append(
                f"{row['id']}: done but commit empty; archive requires hash or no-change"
            )

    try:
        gate_rows = read_gates(csv_path.parent / "run.md")
        by_id = {row["gate"]: row for row in gate_rows}
        errors.extend(gate_chain_errors(gate_rows, csv_path.parent))
        if by_id["prd-review"]["status"] != "PASS":
            errors.append("prd-review is not PASS")
        if by_id["tasks-review"]["status"] != "PASS":
            errors.append("tasks-review is not PASS")
        if by_id["execute"]["status"] != "CONFIRMED":
            errors.append("execute is not CONFIRMED")
        if by_id["materials"]["status"] not in {"CONFIRMED", "WAIVED"}:
            errors.append("materials is not CONFIRMED or WAIVED")
    except WorklineCsvError as exc:
        errors.append(str(exc))

    blocking_warnings = [
        warning
        for warning in warnings
        if warning["code"] in BLOCKING_WARNING_CODES
    ]
    if blocking_warnings:
        errors.extend(
            f"{item['code']}: {item['task_id']} - {item['message']}"
            for item in blocking_warnings
        )

    if errors:
        raise WorklineCsvError("archive-check failed:\n- " + "\n- ".join(errors))

    print("OK: archive-check passed")
    print_warnings(warnings)
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
    set_parser.add_argument(
        "--force",
        action="store_true",
        help="allow leaving done/skipped",
    )
    set_parser.set_defaults(func=command_set)

    next_parser = subparsers.add_parser("next", help="print next runnable task as JSON")
    next_parser.add_argument("csv_path")
    next_parser.set_defaults(func=command_next)

    add_parser = subparsers.add_parser("add", help="insert a task before REVIEW")
    add_parser.add_argument("csv_path")
    add_parser.add_argument("task_id")
    add_parser.add_argument("--mode", required=True, choices=sorted(MODES))
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--description", required=True)
    add_parser.add_argument("--verification", required=True)
    add_parser.add_argument("--depends-on", dest="depends_on", default="")
    add_parser.add_argument("--refs", default="")
    add_parser.add_argument("--notes", default="")
    add_parser.set_defaults(func=command_add)

    gates_parser = subparsers.add_parser("gates", help="print stage gates from run.md as JSON")
    gates_parser.add_argument("path", help="active directory, tasks.csv, or run.md")
    gates_parser.set_defaults(func=command_gates)

    gates_set_parser = subparsers.add_parser("gates-set", help="update one stage gate in run.md")
    gates_set_parser.add_argument("path")
    gates_set_parser.add_argument("--gate", required=True, choices=GATE_IDS)
    gates_set_parser.add_argument("--status", required=True)
    gates_set_parser.add_argument("--actor", default="")
    gates_set_parser.add_argument("--notes")
    gates_set_parser.add_argument(
        "--init",
        action="store_true",
        help="create run.md with default 阶段门禁 if missing",
    )
    gates_set_parser.add_argument(
        "--keep-downstream",
        action="store_true",
        help="do not reset tasks-review/execute after prd-review PASS",
    )
    gates_set_parser.set_defaults(func=command_gates_set)

    require_parser = subparsers.add_parser("require-gates", help="fail unless gates match")
    require_parser.add_argument("path")
    require_parser.add_argument(
        "--require",
        action="append",
        required=True,
        help="gate=STATUS[,STATUS] ; repeatable",
    )
    require_parser.set_defaults(func=command_require_gates)

    archive_parser = subparsers.add_parser(
        "archive-check", help="hard-fail unless the active directory can be archived"
    )
    archive_parser.add_argument("csv_path")
    archive_parser.set_defaults(func=command_archive_check)
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
