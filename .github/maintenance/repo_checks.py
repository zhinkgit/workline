#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", "dist"}
SCRIPT_COPIES = [
    "workline-tasks/scripts/workline_csv.py",
    "workline-run/scripts/workline_csv.py",
    "workline-review/scripts/workline_csv.py",
    "workline-archive/scripts/workline_csv.py",
]


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def matching_files(root: Path, pattern: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(pattern)
        if path.is_file()
        and not any(
            part in SKIP_DIRECTORIES for part in path.relative_to(root).parts
        )
    )


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise ValueError("missing frontmatter enclosed by ---")

    values: dict[str, str] = {}
    block_key: str | None = None
    for line in match.group(1).splitlines():
        if line[:1].isspace() and block_key:
            continuation = line.strip()
            if continuation:
                values[block_key] = " ".join(
                    part for part in (values[block_key], continuation) if part
                )
            continue

        block_key = None
        key, separator, value = line.partition(":")
        if separator:
            key = key.strip()
            value = value.strip()
            if value in {">", ">-", ">+", "|", "|-", "|+"}:
                values[key] = ""
                block_key = key
            else:
                values[key] = value
    return values


def check_skill_metadata(root: Path) -> list[str]:
    errors: list[str] = []
    for path in matching_files(root, "SKILL.md"):
        try:
            metadata = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue

        expected_name = path.parent.name
        if metadata.get("name") != expected_name:
            errors.append(
                f"{path.relative_to(root)}: name must be {expected_name!r}"
            )
        if not metadata.get("description"):
            errors.append(f"{path.relative_to(root)}: description must not be empty")
    return errors


def check_python_syntax(root: Path) -> list[str]:
    errors: list[str] = []
    for path in matching_files(root, "*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors


def check_json(root: Path) -> list[str]:
    errors: list[str] = []
    for path in matching_files(root, "*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors


def local_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return unquote(parsed.path)


def check_markdown_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in matching_files(root, "*.md"):
        text = path.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(text):
            target = local_link_target(match.group(1))
            if target is None:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(root)}: local link escapes repository: {target}"
                )
                continue
            if not resolved.exists():
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{path.relative_to(root)}:{line}: local link does not exist: {target}"
                )
    return errors


def skill_directories(root: Path) -> list[str]:
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )


def check_readme_skills(root: Path) -> list[str]:
    errors: list[str] = []
    readme = root / "README.md"
    if not readme.is_file():
        return ["missing README.md"]

    text = readme.read_text(encoding="utf-8")
    for skill in skill_directories(root):
        if f"`{skill}`" not in text:
            errors.append(f"README.md does not list skill: {skill}")
    return errors


def check_script_copies(root: Path) -> list[str]:
    errors: list[str] = []
    missing = [name for name in SCRIPT_COPIES if not (root / name).is_file()]
    if missing:
        for name in missing:
            errors.append(f"missing script copy: {name}")
        return errors

    hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in SCRIPT_COPIES
    }
    unique = set(hashes.values())
    if len(unique) != 1:
        for name, value in hashes.items():
            errors.append(f"script copy diverged: {value[:16]}  {name}")
    return errors


def run_checks(root: Path) -> list[str]:
    errors: list[str] = []
    checks = [
        check_skill_metadata,
        check_python_syntax,
        check_json,
        check_markdown_links,
        check_readme_skills,
        check_script_copies,
    ]
    for check in checks:
        current = check(root)
        print(f"{check.__name__}: {'PASS' if not current else 'FAIL'}")
        errors.extend(current)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the workline repository")
    parser.add_argument("--root", type=Path, default=repository_root())
    args = parser.parse_args()

    root = args.root.resolve()
    errors = run_checks(root)
    if errors:
        print("\nValidation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("\nAll repository checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
