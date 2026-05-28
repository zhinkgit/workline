#!/usr/bin/env python3
"""Validate and update Workline tasks.csv."""

from __future__ import annotations

import argparse
import csv
import json
import os
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
    "review_state",
    "git_state",
    "refs",
    "notes",
]

MODES = {"AFK", "HITL"}
DEV_STATES = {"todo", "doing", "done", "blocked", "skipped"}
REVIEW_STATES = {"pending", "passed", "failed", "blocked", "skipped"}
GIT_STATES = {"pending", "committed", "not_needed", "blocked", "skipped"}
TERMINAL_DEV_STATES = {"done", "blocked", "skipped"}


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
    return row["dev_state"] == "done" and row["review_state"] == "passed"


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
        if row["review_state"] not in REVIEW_STATES:
            raise WorklineCsvError(
                f"{task_id}: invalid review_state {row['review_state']!r}"
            )
        if row["git_state"] not in GIT_STATES:
            raise WorklineCsvError(f"{task_id}: invalid git_state {row['git_state']!r}")

        if task_id != "REVIEW":
            if not row["acceptance_criteria"]:
                raise WorklineCsvError(f"{task_id}: acceptance_criteria is required")
            if not row["verification"]:
                raise WorklineCsvError(f"{task_id}: verification is required")
        if row["review_state"] == "passed" and row["dev_state"] != "done":
            raise WorklineCsvError(f"{task_id}: review_state=passed requires dev_state=done")
        if row["dev_state"] == "done" and row["review_state"] in {"failed", "blocked"}:
            raise WorklineCsvError(
                f"{task_id}: dev_state=done conflicts with review_state={row['review_state']}"
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
        updates.get("review_state", row["review_state"]),
        updates.get("git_state", row["git_state"]),
    }
    if exception_values & {"blocked", "skipped", "failed"} and not effective_notes.strip():
        raise WorklineCsvError("blocked/skipped/failed updates require notes")


def validate_transition(row: dict[str, str], updates: dict[str, str]) -> None:
    for key, allowed in {
        "dev_state": DEV_STATES,
        "review_state": REVIEW_STATES,
        "git_state": GIT_STATES,
    }.items():
        if key in updates and updates[key] not in allowed:
            raise WorklineCsvError(f"invalid {key}: {updates[key]}")

    old_dev = row["dev_state"]
    new_dev = updates.get("dev_state", old_dev)
    new_review = updates.get("review_state", row["review_state"])

    if old_dev == "todo" and new_dev == "done":
        raise WorklineCsvError("cannot change dev_state directly from todo to done; set doing first")
    if new_review == "passed" and new_dev != "done":
        raise WorklineCsvError("review_state=passed requires dev_state=done")
    if new_dev == "done" and new_review in {"failed", "blocked"}:
        raise WorklineCsvError(f"dev_state=done conflicts with review_state={new_review}")
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
    for key in ("dev_state", "review_state", "git_state", "refs", "notes"):
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
    set_parser.add_argument("--review_state")
    set_parser.add_argument("--git_state")
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
