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


def read_brief(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.brief:
        parts.append(args.brief.strip())
    if args.brief_text:
        parts.append(" ".join(args.brief_text).strip())
    if args.brief_file:
        parts.append(Path(args.brief_file).read_text(encoding="utf-8").strip())
    return "\n\n".join(part for part in parts if part).strip()


def build_brief(created_at: str, raw_brief: str) -> str:
    body = raw_brief or "TODO: 在这里补充原始粗需求。"
    return f"""# Workline Brief

## 创建时间

{created_at}

## 原始粗需求

{body}

## 待补充材料

请把参考资料、旧代码、协议文档、网页资料、用户提供文件或其它输入材料放入 `references/`。

后续 `$workline-grill` 会读取本文件和 `references/`，再逐问逐答生成 `prd.md`。
"""


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
    raw_brief = read_brief(args)
    timestamp = args.now or datetime.now().strftime("%Y-%m-%d-%H%M")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", timestamp):
        print("ERROR: --now must use YYYY-MM-DD-HHMM format", file=sys.stderr)
        return 2

    slug_source = args.slug or raw_brief
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
    (active_dir / "brief.md").write_text(build_brief(created_at, raw_brief), encoding="utf-8")

    print(active_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
