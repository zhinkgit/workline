#!/usr/bin/env python3
"""Stdlib tests for workline_csv.py. Run: python tools/test_workline_csv.py"""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "workline-tasks" / "scripts" / "workline_csv.py"
INIT = ROOT / "workline-init" / "scripts" / "init_workline.py"


def load_module():
    spec = importlib.util.spec_from_file_location("workline_csv", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


M = load_module()
HEADERS = M.HEADERS


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            full = {key: "" for key in HEADERS}
            full.update(row)
            writer.writerow(full)


def task(**kwargs) -> dict[str, str]:
    row = {
        "id": "T001",
        "depends_on": "",
        "mode": "AFK",
        "title": "title",
        "description": "desc",
        "verification": "`pytest`",
        "state": "todo",
        "commit": "",
        "refs": "FR-1",
        "notes": "",
    }
    row.update(kwargs)
    return row


REVIEW = task(id="REVIEW", title="review", description="audit", verification="", refs="")


def complete_log(task_id: str = "T001") -> str:
    return (
        f"## {task_id} title\n\n"
        "- 实现：改了导入校验\n"
        "- 验证：`pytest tests/test_import.py` 退出码 0\n"
        "- 输出：1 passed\n"
        "- 限制：无\n"
    )


class WorklineCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wltest-"))
        self.csv_path = self.tmpdir / "tasks.csv"
        (self.tmpdir / "prd.md").write_text("### FR-1 导入\n", encoding="utf-8")
        (self.tmpdir / "run.md").write_text(
            (ROOT / "workline-init" / "templates" / "run.md")
            .read_text(encoding="utf-8")
            .replace("{{title}}", "test")
            .replace("{{created_at}}", "now"),
            encoding="utf-8",
        )

    def run_cmd(self, argv: list[str]) -> tuple[int, str, str]:
        parser = M.build_parser()
        args = parser.parse_args(argv)
        from io import StringIO

        stdout = StringIO()
        stderr = StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout, stderr
        try:
            code = args.func(args)
        except M.WorklineCsvError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            code = 1
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        return code, stdout.getvalue(), stderr.getvalue()

    def test_hitl_doing_does_not_starve_afk(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", mode="HITL", state="doing", verification="板测"),
                task(id="T002", mode="AFK", state="todo"),
                REVIEW,
            ],
        )
        code, out, _ = self.run_cmd(["next", str(self.csv_path)])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["id"], "T002")
        self.assertFalse(payload["hitl"])

    def test_afk_preferred_over_ready_hitl(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", mode="HITL", state="todo", verification="板测"),
                task(id="T002", mode="AFK", state="todo"),
                REVIEW,
            ],
        )
        _, out, _ = self.run_cmd(["next", str(self.csv_path)])
        self.assertEqual(json.loads(out)["id"], "T002")

    def test_hitl_selected_when_only_ready_work(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", mode="HITL", state="todo", verification="板测"),
                REVIEW,
            ],
        )
        _, out, _ = self.run_cmd(["next", str(self.csv_path)])
        payload = json.loads(out)
        self.assertEqual(payload["id"], "T001")
        self.assertTrue(payload["hitl"])

    def test_skipped_unblocks_with_warning(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", state="skipped", notes="prd allows"),
                task(id="T002", depends_on="T001", state="todo"),
                REVIEW,
            ],
        )
        _, out, _ = self.run_cmd(["next", str(self.csv_path)])
        payload = json.loads(out)
        self.assertEqual(payload["id"], "T002")
        codes = [item["code"] for item in payload["warnings"]]
        self.assertIn("skipped-unblocks", codes)

    def test_validate_rejects_done_without_complete_log(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001", state="done", commit="no-change"), REVIEW],
        )
        (self.tmpdir / "run.md").write_text("## T001 stub\n", encoding="utf-8")
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("不完整", err)

    def test_next_rejects_forged_done_and_does_not_continue(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", state="done", commit="no-change"),
                task(id="T002", state="todo"),
                REVIEW,
            ],
        )
        code, _, err = self.run_cmd(["next", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("done-state checks failed", err)

    def test_set_rejects_incomplete_log_and_fake_hash_without_git(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="doing"), REVIEW])
        (self.tmpdir / "run.md").write_text("## T001 stub\n", encoding="utf-8")
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "deadbeef"]
        )
        self.assertEqual(code, 1)
        self.assertIn("不完整", err)

        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "deadbeef"]
        )
        self.assertEqual(code, 1)
        self.assertTrue("git" in err.lower() or "提交" in err)

    def test_set_accepts_complete_log_and_no_change(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="doing"), REVIEW])
        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, out, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("OK: updated T001", out)

    def test_terminal_state_requires_force(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001", state="done", commit="no-change"), REVIEW],
        )
        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "todo"]
        )
        self.assertEqual(code, 1)
        self.assertIn("--force", err)
        code, _, _ = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "todo", "--force"]
        )
        self.assertEqual(code, 0)

    def test_todo_cannot_jump_to_done(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="todo"), REVIEW])
        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.assertEqual(code, 1)
        self.assertIn("todo to done", err)

    def test_empty_title_rejected(self) -> None:
        write_csv(self.csv_path, [task(id="T001", title=""), REVIEW])
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("title is required", err)

    def test_verification_weak_requires_backticks(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(
                    id="T001",
                    verification="检查 python 代码逻辑是否正确 make sure",
                ),
                REVIEW,
            ],
        )
        code, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 0)
        self.assertIn("verification-weak", out)

        write_csv(
            self.csv_path,
            [task(id="T001", verification="`pytest tests/test_import.py` 期望退出码 0"), REVIEW],
        )
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertNotIn("verification-weak", out)

    def test_refs_invalid_and_fr_padding(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001", refs="src/main.c FR-01"), REVIEW],
        )
        (self.tmpdir / "prd.md").write_text("### FR-1 导入\n### FR-2 校验\n", encoding="utf-8")
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertIn("refs-invalid", out)
        self.assertIn("req-id-padded", out)
        self.assertIn("fr-uncovered", out)

    def test_fr_headings_missing_warning(self) -> None:
        (self.tmpdir / "prd.md").write_text(
            "## 功能要求\n\n- 做导入\n- 做校验\n", encoding="utf-8"
        )
        write_csv(self.csv_path, [task(id="T001", refs=""), REVIEW])
        _, out, _ = self.run_cmd(["validate", str(self.csv_path), "--allow-empty-refs"])
        self.assertIn("fr-headings-missing", out)

    def test_nfr_coverage(self) -> None:
        (self.tmpdir / "prd.md").write_text(
            "### FR-1 导入\n### NFR-1 超时 200ms\n", encoding="utf-8"
        )
        write_csv(self.csv_path, [task(id="T001", refs="FR-1"), REVIEW])
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertIn("nfr-uncovered", out)

    def test_empty_commit_with_notes_allows_next_but_blocks_archive(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="doing"), REVIEW])
        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            [
                "set",
                str(self.csv_path),
                "T001",
                "--state",
                "done",
                "--commit",
                "",
                "--notes",
                "not a git repo",
            ]
        )
        self.assertEqual(code, 0, err)
        code, out, err = self.run_cmd(["next", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["id"], "REVIEW")
        (self.tmpdir / "run.md").write_text(
            complete_log() + "\n" + complete_log("REVIEW"), encoding="utf-8"
        )
        self.run_cmd(["set", str(self.csv_path), "REVIEW", "--state", "doing"])
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "done", "--commit", "no-change"]
        )
        (self.tmpdir / "brief.md").write_text("# b\n", encoding="utf-8")
        (self.tmpdir / "references").mkdir(exist_ok=True)
        for gate, status in [
            ("materials", "CONFIRMED"),
            ("prd-review", "PASS"),
            ("tasks-review", "PASS"),
            ("execute", "CONFIRMED"),
        ]:
            extra = ["--keep-downstream"] if gate == "prd-review" else []
            self.run_cmd(
                ["gates-set", str(self.tmpdir), "--gate", gate, "--status", status, *extra]
            )
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("commit empty", err)

    def test_add_inserts_before_review(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        code, _, err = self.run_cmd(
            [
                "add",
                str(self.csv_path),
                "T002",
                "--mode",
                "AFK",
                "--title",
                "第二步",
                "--description",
                "实现校验",
                "--verification",
                "`pytest`",
                "--refs",
                "FR-1",
            ]
        )
        self.assertEqual(code, 0, err)
        rows = M.read_rows(self.csv_path)
        self.assertEqual([row["id"] for row in rows], ["T001", "T002", "REVIEW"])

    def test_gates_require_and_prd_pass_resets_downstream(self) -> None:
        code, _, err = self.run_cmd(
            [
                "gates-set",
                str(self.tmpdir),
                "--gate",
                "prd-review",
                "--status",
                "PASS",
                "--actor",
                "same-session",
            ]
        )
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cmd(
            ["require-gates", str(self.tmpdir), "--require", "prd-review=PASS"]
        )
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cmd(
            ["require-gates", str(self.tmpdir), "--require", "tasks-review=PASS"]
        )
        self.assertEqual(code, 1)
        self.assertIn("tasks-review", err)

        self.run_cmd(
            [
                "gates-set",
                str(self.tmpdir),
                "--gate",
                "tasks-review",
                "--status",
                "PASS",
                "--actor",
                "same-session",
            ]
        )
        self.run_cmd(
            [
                "gates-set",
                str(self.tmpdir),
                "--gate",
                "prd-review",
                "--status",
                "PASS",
                "--actor",
                "external-agent",
            ]
        )
        code, _, err = self.run_cmd(
            ["require-gates", str(self.tmpdir), "--require", "tasks-review=PASS"]
        )
        self.assertEqual(code, 1)

    def test_gates_set_preserves_task_logs(self) -> None:
        (self.tmpdir / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            [
                "gates-set",
                str(self.tmpdir),
                "--gate",
                "materials",
                "--status",
                "CONFIRMED",
                "--actor",
                "user",
            ]
        )
        self.assertEqual(code, 0, err)
        text = (self.tmpdir / "run.md").read_text(encoding="utf-8")
        self.assertIn("## 阶段门禁", text)
        self.assertIn("| materials | CONFIRMED |", text)
        self.assertTrue(
            text.index("## 阶段门禁") < text.index("## T001 title")
        )
        sections = M.read_run_sections(self.csv_path)
        self.assertIn("T001", sections)
        self.assertTrue(M.run_section_is_complete(sections["T001"]))

    def test_archive_check_and_init_create_run_md(self) -> None:
        root = self.tmpdir / "proj"
        result = subprocess.run(
            [sys.executable, str(INIT), "--root", str(root), "--brief", "bulk import", "--now", "2026-09-03-0915"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        active = Path(result.stdout.strip())
        self.assertTrue((active / "run.md").exists())
        self.assertFalse((active / "gates.csv").exists())
        self.assertIn("阶段门禁", (active / "run.md").read_text(encoding="utf-8"))
        self.assertTrue((active / "brief.md").exists())
        self.assertTrue((active / "references").is_dir())

        write_csv(
            self.csv_path,
            [task(id="T001", state="doing"), REVIEW],
        )
        (self.tmpdir / "brief.md").write_text("# brief\n", encoding="utf-8")
        (self.tmpdir / "run.md").write_text(
            complete_log() + "\n" + complete_log("REVIEW"), encoding="utf-8"
        )
        (self.tmpdir / "references").mkdir(exist_ok=True)
        self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "doing"]
        )
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "done", "--commit", "no-change"]
        )
        for gate, status in [
            ("materials", "CONFIRMED"),
            ("prd-review", "PASS"),
            ("tasks-review", "PASS"),
            ("execute", "CONFIRMED"),
        ]:
            extra = ["--keep-downstream"] if gate == "prd-review" else []
            self.run_cmd(
                ["gates-set", str(self.tmpdir), "--gate", gate, "--status", status, *extra]
            )
        code, out, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertIn("archive-check passed", out)

        self.run_cmd(
            ["gates-set", str(self.tmpdir), "--gate", "execute", "--status", "未确认"]
        )
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("execute is not CONFIRMED", err)

    def test_git_hash_accepted_in_real_repo(self) -> None:
        repo = self.tmpdir / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "wl@test"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "wl"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
        digest = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        csv_path = repo / "tasks.csv"
        write_csv(csv_path, [task(id="T001", state="doing"), REVIEW])
        (repo / "prd.md").write_text("### FR-1 x\n", encoding="utf-8")
        (repo / "run.md").write_text(complete_log(), encoding="utf-8")
        code, _, err = self.run_cmd(
            ["set", str(csv_path), "T001", "--state", "done", "--commit", digest[:12]]
        )
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
