#!/usr/bin/env python3
"""Validate and update Workline tasks.csv."""

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
    "acceptance_criteria",
    "verification",
    "dev_state",
    "verify_state",
    "git_state",
    "refs",
    "notes",
]

MODES = {"AFK", "HITL"}
DEV_STATES = {"todo", "doing", "done", "blocked", "skipped"}
VERIFY_STATES = {"pending", "passed", "failed", "blocked", "skipped"}
GIT_STATES = {"pending", "done", "blocked"}
TERMINAL_DEV_STATES = {"done", "blocked", "skipped"}
EVIDENCE_TAG_PATTERN = re.compile(r"\[evidence:([A-Za-z0-9_-]+)\]")
DEFAULT_EVIDENCE_LEVELS = [
    "local",
    "sim",
    "target",
    "real",
    "manual",
]


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


def is_closed(row: dict[str, str]) -> bool:
    return row["dev_state"] == "done" and row["verify_state"] == "passed"


def dep_satisfied(row: dict[str, str]) -> bool:
    return is_closed(row) or row["dev_state"] == "skipped"


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
        if row["dev_state"] not in DEV_STATES:
            raise WorklineCsvError(f"{task_id}: invalid dev_state {row['dev_state']!r}")
        if row["verify_state"] not in VERIFY_STATES:
            raise WorklineCsvError(
                f"{task_id}: invalid verify_state {row['verify_state']!r}"
            )
        if row["git_state"] not in GIT_STATES:
            raise WorklineCsvError(f"{task_id}: invalid git_state {row['git_state']!r}")

        if task_id != "REVIEW":
            if not row["acceptance_criteria"]:
                raise WorklineCsvError(f"{task_id}: acceptance_criteria is required")
            if not row["verification"]:
                raise WorklineCsvError(f"{task_id}: verification is required")
        if row["verify_state"] == "passed" and row["dev_state"] != "done":
            raise WorklineCsvError(f"{task_id}: verify_state=passed requires dev_state=done")
        if row["dev_state"] == "done" and row["verify_state"] in {"failed", "blocked"}:
            raise WorklineCsvError(
                f"{task_id}: dev_state=done conflicts with verify_state={row['verify_state']}"
            )

    if ids[-1] != "REVIEW":
        raise WorklineCsvError("last row must be REVIEW")
    if ids.count("REVIEW") != 1:
        raise WorklineCsvError("REVIEW must appear exactly once")

    id_set = set(ids)
    for row in rows:
        task_id = row["id"]
        for dep in split_deps(row["depends_on"]):
            if dep not in id_set:
                raise WorklineCsvError(f"{task_id}: unknown dependency {dep}")
            if dep == task_id:
                raise WorklineCsvError(f"{task_id}: cannot depend on itself")

    non_review_ids = ids[:-1]
    review_deps = set(split_deps(rows[-1]["depends_on"]))
    if review_deps != set(non_review_ids):
        missing = sorted(set(non_review_ids) - review_deps)
        extra = sorted(review_deps - set(non_review_ids))
        raise WorklineCsvError(
            f"REVIEW must depend on all non-REVIEW tasks; missing={missing}, extra={extra}"
        )


def validate_file(path: Path) -> list[dict[str, str]]:
    rows = read_rows(path)
    validate_rows(rows)
    return rows


def find_row(rows: list[dict[str, str]], task_id: str) -> dict[str, str]:
    for row in rows:
        if row["id"] == task_id:
            return row
    raise WorklineCsvError(f"unknown task id: {task_id}")


def require_note_for_exception(row: dict[str, str], updates: dict[str, str]) -> None:
    effective_notes = updates.get("notes", row["notes"])
    exception_values = {
        updates.get("dev_state", row["dev_state"]),
        updates.get("verify_state", row["verify_state"]),
        updates.get("git_state", row["git_state"]),
    }
    if exception_values & {"blocked", "skipped", "failed"} and not effective_notes.strip():
        raise WorklineCsvError("blocked/skipped/failed updates require notes")


def validate_transition(row: dict[str, str], updates: dict[str, str]) -> None:
    for key, allowed in {
        "dev_state": DEV_STATES,
        "verify_state": VERIFY_STATES,
        "git_state": GIT_STATES,
    }.items():
        if key in updates and updates[key] not in allowed:
            raise WorklineCsvError(f"invalid {key}: {updates[key]}")

    old_dev = row["dev_state"]
    new_dev = updates.get("dev_state", old_dev)
    new_verify = updates.get("verify_state", row["verify_state"])

    if old_dev == "todo" and new_dev == "done":
        raise WorklineCsvError("cannot change dev_state directly from todo to done; set doing first")
    if new_verify == "passed" and new_dev != "done":
        raise WorklineCsvError("verify_state=passed requires dev_state=done")
    if new_dev == "done" and new_verify in {"failed", "blocked"}:
        raise WorklineCsvError(f"dev_state=done conflicts with verify_state={new_verify}")
    require_note_for_exception(row, updates)


def command_validate(args: argparse.Namespace) -> int:
    rows = validate_file(Path(args.csv_path))
    print(f"OK: {len(rows)} rows")
    return 0


def command_set(args: argparse.Namespace) -> int:
    path = Path(args.csv_path)
    rows = validate_file(path)
    row = find_row(rows, args.task_id)

    updates: dict[str, str] = {}
    for key in ("dev_state", "verify_state", "git_state", "refs", "notes"):
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

    validate_transition(row, updates)
    row.update(updates)
    validate_rows(rows)
    write_rows_atomic(path, rows)
    print(f"OK: updated {args.task_id}")
    return 0


def command_next(args: argparse.Namespace) -> int:
    rows = validate_file(Path(args.csv_path))
    by_id = {row["id"]: row for row in rows}

    for row in rows:
        if row["id"] == "REVIEW":
            non_review = rows[:-1]
            ready = all(dep_satisfied(item) for item in non_review)
            if ready and row["dev_state"] in {"todo", "doing"}:
                print(json.dumps(row, ensure_ascii=False))
                return 0
            continue

        if row["dev_state"] not in {"todo", "doing"}:
            continue
        deps = [by_id[dep] for dep in split_deps(row["depends_on"])]
        if all(dep_satisfied(dep) for dep in deps):
            print(json.dumps(row, ensure_ascii=False))
            return 0

    blocked = [
        row["id"]
        for row in rows
        if row["dev_state"] in {"todo", "doing"}
        and any(by_id[dep]["dev_state"] == "blocked" for dep in split_deps(row["depends_on"]))
    ]
    if blocked:
        print(json.dumps({"next": None, "blocked": blocked}, ensure_ascii=False))
    else:
        print(json.dumps({"next": None}, ensure_ascii=False))
    return 0


def evidence_levels(row: dict[str, str]) -> set[str]:
    text = f"{row['refs']} {row['notes']}"
    return {match.group(1) for match in EVIDENCE_TAG_PATTERN.finditer(text)}


def build_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    non_review = [row for row in rows if row["id"] != "REVIEW"]
    final_review = find_row(rows, "REVIEW")
    warnings: list[dict[str, str]] = []
    evidence_level_counts = {level: 0 for level in DEFAULT_EVIDENCE_LEVELS}
    tasks_with_evidence_refs = 0

    for row in non_review:
        task_id = row["id"]
        refs_and_notes = f"{row['refs']} {row['notes']}"
        has_evidence_ref = "evidence/" in refs_and_notes.replace("\\", "/")
        levels = evidence_levels(row)

        if has_evidence_ref:
            tasks_with_evidence_refs += 1
        for level in levels:
            evidence_level_counts[level] = evidence_level_counts.get(level, 0) + 1

        if is_closed(row) and not levels:
            warnings.append(
                {
                    "code": "missing-evidence-level",
                    "task_id": task_id,
                    "message": "done/passed task has no [evidence:*] level tag",
                }
            )
        if has_evidence_ref and not levels:
            warnings.append(
                {
                    "code": "evidence-ref-without-level",
                    "task_id": task_id,
                    "message": "evidence reference has no [evidence:*] level tag",
                }
            )
        if (
            row["mode"] == "HITL"
            and row["dev_state"] in TERMINAL_DEV_STATES
            and not (levels & {"manual", "target", "real"})
        ):
            warnings.append(
                {
                    "code": "hitl-without-manual-target-or-real-evidence",
                    "task_id": task_id,
                    "message": "HITL task has no manual, target, or real evidence tag",
                }
            )
        if "target" in levels and "real" not in levels:
            warnings.append(
                {
                    "code": "target-without-real",
                    "task_id": task_id,
                    "message": "target evidence is present but real evidence is not",
                }
            )
        if row["git_state"] == "pending" and row["dev_state"] in TERMINAL_DEV_STATES:
            warnings.append(
                {
                    "code": "git-pending",
                    "task_id": task_id,
                    "message": "git_state is still pending",
                }
            )
        if (
            row["dev_state"] in {"blocked", "skipped"}
            or row["verify_state"] in {"failed", "blocked", "skipped"}
            or row["git_state"] == "blocked"
        ):
            warnings.append(
                {
                    "code": "skipped-or-blocked",
                    "task_id": task_id,
                    "message": "task contains skipped, blocked, or failed state",
                }
            )

    return {
        "rows_total": len(rows),
        "non_review_total": len(non_review),
        "closed": {
            "count": sum(1 for row in non_review if is_closed(row)),
            "ids": [row["id"] for row in non_review if is_closed(row)],
        },
        "todo_or_doing": {
            "count": sum(1 for row in non_review if row["dev_state"] in {"todo", "doing"}),
            "ids": [row["id"] for row in non_review if row["dev_state"] in {"todo", "doing"}],
        },
        "blocked": {
            "count": sum(1 for row in non_review if row["dev_state"] == "blocked"),
            "ids": [row["id"] for row in non_review if row["dev_state"] == "blocked"],
        },
        "failed": {
            "count": sum(1 for row in non_review if row["verify_state"] == "failed"),
            "ids": [row["id"] for row in non_review if row["verify_state"] == "failed"],
        },
        "skipped": {
            "count": sum(
                1
                for row in non_review
                if row["dev_state"] == "skipped"
                or row["verify_state"] == "skipped"
            ),
            "ids": [
                row["id"]
                for row in non_review
                if row["dev_state"] == "skipped"
                or row["verify_state"] == "skipped"
            ],
        },
        "git_pending": {
            "count": sum(1 for row in non_review if row["git_state"] == "pending"),
            "ids": [row["id"] for row in non_review if row["git_state"] == "pending"],
        },
        "final_review": {
            "dev_state": final_review["dev_state"],
            "verify_state": final_review["verify_state"],
            "git_state": final_review["git_state"],
        },
        "evidence_refs": {
            "count": tasks_with_evidence_refs,
            "total": len(non_review),
        },
        "evidence_levels": evidence_level_counts,
        "warnings": warnings,
    }


def format_summary(summary: dict[str, object]) -> str:
    closed = summary["closed"]
    todo_or_doing = summary["todo_or_doing"]
    blocked = summary["blocked"]
    failed = summary["failed"]
    skipped = summary["skipped"]
    git_pending = summary["git_pending"]
    final_review = summary["final_review"]
    evidence_refs = summary["evidence_refs"]
    evidence_levels = summary["evidence_levels"]
    warnings = summary["warnings"]

    level_text = ", ".join(
        f"{level}={count}" for level, count in sorted(evidence_levels.items())
    )
    lines = [
        f"OK: {summary['rows_total']} rows",
        f"closed: {closed['count']}/{summary['non_review_total']} non-review tasks",
        f"todo_or_doing: {todo_or_doing['count']}",
        f"blocked: {blocked['count']}",
        f"failed: {failed['count']}",
        f"skipped: {skipped['count']}",
        f"git_pending: {git_pending['count']}",
        f"final_review: {final_review['dev_state']}/{final_review['verify_state']}/{final_review['git_state']}",
        f"evidence_refs: {evidence_refs['count']}/{evidence_refs['total']} non-review tasks",
        f"evidence_levels: {level_text}",
        f"warnings: {len(warnings)}",
    ]
    for warning in warnings:
        lines.append(
            f"- {warning['code']}: {warning['task_id']} - {warning['message']}"
        )
    return "\n".join(lines)


def command_summary(args: argparse.Namespace) -> int:
    rows = validate_file(Path(args.csv_path))
    summary = build_summary(rows)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_summary(summary))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workline CSV helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate tasks.csv")
    validate_parser.add_argument("csv_path")
    validate_parser.set_defaults(func=command_validate)

    set_parser = subparsers.add_parser("set", help="update one task row")
    set_parser.add_argument("csv_path")
    set_parser.add_argument("task_id")
    set_parser.add_argument("--dev_state")
    set_parser.add_argument("--verify_state")
    set_parser.add_argument("--git_state")
    set_parser.add_argument("--refs")
    set_parser.add_argument("--append-refs")
    set_parser.add_argument("--notes")
    set_parser.add_argument("--append-notes")
    set_parser.set_defaults(func=command_set)

    next_parser = subparsers.add_parser("next", help="print next runnable task as JSON")
    next_parser.add_argument("csv_path")
    next_parser.set_defaults(func=command_next)

    summary_parser = subparsers.add_parser("summary", help="print task status and evidence summary")
    summary_parser.add_argument("csv_path")
    summary_parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    summary_parser.set_defaults(func=command_summary)
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





