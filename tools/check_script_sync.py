#!/usr/bin/env python3
"""校验 workline_csv.py 的多份副本逐字一致。

每个 Skill 自包含一份脚本，副本一致性不能靠文件头注释和记性维持。
发布前运行：python tools/check_script_sync.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


COPIES = [
    "workline-tasks/scripts/workline_csv.py",
    "workline-run/scripts/workline_csv.py",
    "workline-review/scripts/workline_csv.py",
    "workline-archive/scripts/workline_csv.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    missing = [name for name in COPIES if not (root / name).is_file()]
    if missing:
        print("ERROR: missing script copies:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    hashes = {name: digest(root / name) for name in COPIES}
    unique = set(hashes.values())

    if len(unique) == 1:
        print(f"OK: {len(COPIES)} copies identical, sha256={unique.pop()[:16]}")
        return 0

    print("ERROR: script copies diverged:", file=sys.stderr)
    for name, value in hashes.items():
        print(f"  {value[:16]}  {name}", file=sys.stderr)
    print(
        "\n修复：以正确的一份为准覆盖其余副本，再重新运行本校验。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
