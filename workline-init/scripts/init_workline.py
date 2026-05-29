#!/usr/bin/env python3
"""Initialize a Workline active directory."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


def slugify(value: str, fallback: str = "workline") -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    slug = "-".join(words[:8]).strip("-")
    return slug or fallback


def read_slug_source(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.brief:
        parts.append(args.brief.strip())
    if args.brief_text:
        parts.append(" ".join(args.brief_text).strip())
    if args.brief_file:
        parts.append(Path(args.brief_file).read_text(encoding="utf-8").strip())
    return "\n\n".join(part for part in parts if part).strip()


def render_brief_template(created_at: str) -> str:
    template_path = Path(__file__).resolve().parents[1] / "templates" / "brief.md"
    template = template_path.read_text(encoding="utf-8")
    return template.replace("{{created_at}}", created_at)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create .workline/active/<timestamp-slug>/")
    parser.add_argument("brief_text", nargs="*", help="rough requirement text, used only for slug generation")
    parser.add_argument("--root", default=".", help="project root, default: current directory")
    parser.add_argument("--brief", help="rough requirement text, used only for slug generation")
    parser.add_argument("--brief-file", help="path to a UTF-8 text file containing the rough requirement, used only for slug generation")
    parser.add_argument("--slug", help="activity slug; defaults to a slug from the brief")
    parser.add_argument("--now", help="timestamp override in YYYY-MM-DD-HHMM format, mainly for tests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    slug_text = read_slug_source(args)
    timestamp = args.now or datetime.now().strftime("%Y-%m-%d-%H%M")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", timestamp):
        print("ERROR: --now must use YYYY-MM-DD-HHMM format", file=sys.stderr)
        return 2

    slug_source = args.slug or slug_text
    slug = slugify(slug_source)
    active_dir = root / ".workline" / "active" / f"{timestamp}-{slug}"
    archive_dir = root / ".workline" / "archive"

    if active_dir.exists():
        print(f"ERROR: active directory already exists: {active_dir}", file=sys.stderr)
        return 1

    references_dir = active_dir / "references"
    references_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    (active_dir / "brief.md").write_text(render_brief_template(created_at), encoding="utf-8")

    print(active_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
