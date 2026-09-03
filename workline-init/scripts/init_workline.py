#!/usr/bin/env python3
"""Initialize a Workline active directory."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


MAX_TOKEN_CHARS = 16
MAX_SLUG_CHARS = 40


def slugify(value: str, fallback: str = "workline") -> str:
    """ASCII 词按词切分，CJK 连续段按字符截断，避免中文需求全部回退到 fallback。"""
    tokens = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff\u3040-\u30ff]+", value.lower())
    parts: list[str] = []
    length = 0
    for token in tokens[:8]:
        token = token[:MAX_TOKEN_CHARS]
        cost = len(token) + (1 if parts else 0)
        if length + cost > MAX_SLUG_CHARS:
            break
        parts.append(token)
        length += cost
    return "-".join(parts) or fallback


def read_brief_source(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.brief:
        parts.append(args.brief.strip())
    if args.brief_text:
        parts.append(" ".join(args.brief_text).strip())
    if args.brief_file:
        parts.append(Path(args.brief_file).read_text(encoding="utf-8").strip())
    return "\n\n".join(part for part in parts if part).strip()


def skill_template(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / name


def render_brief_template(created_at: str, title: str, brief: str) -> str:
    template = skill_template("brief.md").read_text(encoding="utf-8")
    return (
        template.replace("{{created_at}}", created_at)
        .replace("{{title}}", title)
        .replace("{{brief}}", brief or "<!-- 请补充原始粗需求。 -->")
    )


def render_run_template(created_at: str, title: str) -> str:
    template = skill_template("run.md").read_text(encoding="utf-8")
    return template.replace("{{created_at}}", created_at).replace("{{title}}", title)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create .workline/active/<timestamp-slug>/")
    parser.add_argument("brief_text", nargs="*", help="rough requirement text")
    parser.add_argument("--root", default=".", help="project root, default: current directory")
    parser.add_argument("--brief", help="rough requirement text")
    parser.add_argument("--brief-file", help="path to a UTF-8 text file containing the rough requirement")
    parser.add_argument("--slug", help="activity slug; defaults to a slug from the brief")
    parser.add_argument("--now", help="timestamp override in YYYY-MM-DD-HHMM format, mainly for tests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    brief_text = read_brief_source(args)
    timestamp = args.now or datetime.now().strftime("%Y-%m-%d-%H%M")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", timestamp):
        print("ERROR: --now must use YYYY-MM-DD-HHMM format", file=sys.stderr)
        return 2

    slug_source = args.slug or brief_text
    slug = slugify(slug_source)
    active_dir = root / ".workline" / "active" / f"{timestamp}-{slug}"
    archive_dir = root / ".workline" / "archive"

    if active_dir.exists():
        print(f"ERROR: active directory already exists: {active_dir}", file=sys.stderr)
        return 1

    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        rendered_brief = render_brief_template(created_at, active_dir.name, brief_text)
        run_text = render_run_template(created_at, active_dir.name)
    except OSError as exc:
        print(f"ERROR: cannot read Workline templates: {exc}", file=sys.stderr)
        return 1

    active_dir.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = active_dir.with_name(f".{active_dir.name}.tmp")
    if staging_dir.exists():
        print(f"ERROR: staging directory already exists: {staging_dir}", file=sys.stderr)
        return 1

    try:
        (staging_dir / "references").mkdir(parents=True)
        (staging_dir / "brief.md").write_text(rendered_brief, encoding="utf-8")
        (staging_dir / "run.md").write_text(run_text, encoding="utf-8")
        staging_dir.replace(active_dir)
    except OSError as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        print(f"ERROR: cannot create active directory: {exc}", file=sys.stderr)
        return 1

    print(active_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
