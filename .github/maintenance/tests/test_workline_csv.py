#!/usr/bin/env python3
"""Stdlib tests for workline_csv.py. Run: python .github/maintenance/run_tests.py"""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
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

    def write_run(self, body: str, directory: Path | None = None) -> None:
        directory = directory or self.tmpdir
        template = (ROOT / "workline-init" / "templates" / "run.md").read_text(
            encoding="utf-8"
        )
        text = template.replace("{{title}}", "test").replace("{{created_at}}", "now")
        (directory / "run.md").write_text(text + "\n" + body, encoding="utf-8")

    def approve_execution(self, directory: Path | None = None) -> None:
        directory = directory or self.tmpdir
        commands = [
            ["gates-set", str(directory), "--gate", "materials", "--status", "CONFIRMED", "--actor", "user"],
            ["gates-set", str(directory), "--gate", "prd-review", "--status", "PASS", "--actor", "same-session"],
            ["gates-set", str(directory), "--gate", "tasks-review", "--status", "PASS", "--actor", "same-session"],
            ["gates-set", str(directory), "--gate", "execute", "--status", "CONFIRMED", "--actor", "user"],
        ]
        for command in commands:
            code, _, err = self.run_cmd(command)
            self.assertEqual(code, 0, err)

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
        self.assertIn("done 任务收口检查未通过", err)

    def test_set_rejects_incomplete_log_and_fake_hash_without_git(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="doing"), REVIEW])
        self.write_run("## T001 stub\n")
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "deadbeef"]
        )
        self.assertEqual(code, 1)
        self.assertIn("不完整", err)

        self.write_run(complete_log())
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "deadbeef"]
        )
        self.assertEqual(code, 1)
        self.assertTrue("git" in err.lower() or "提交" in err)

    def test_set_accepts_complete_log_and_no_change(self) -> None:
        write_csv(self.csv_path, [task(id="T001", state="doing"), REVIEW])
        self.write_run(complete_log())
        self.approve_execution()
        code, out, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("OK: 已更新 T001", out)

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
        self.write_run(complete_log())
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.assertEqual(code, 1)
        self.assertIn("todo 不能直接跳到 done", err)

    def test_empty_title_rejected(self) -> None:
        write_csv(self.csv_path, [task(id="T001", title=""), REVIEW])
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("title 必填", err)

    def test_afk_without_backticks_is_valid(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(
                    id="T001",
                    verification="keil build 成功且 errors=0",
                ),
                REVIEW,
            ],
        )
        code, out, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertNotIn("verification-weak", out)

    def test_refs_invalid_and_fr_padding(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001", refs="D:/outside/spec.pdf FR-01"), REVIEW],
        )
        (self.tmpdir / "prd.md").write_text("### FR-1 导入\n### FR-2 校验\n", encoding="utf-8")
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertIn("refs-invalid", out)
        self.assertIn("req-id-padded", out)
        self.assertIn("fr-uncovered", out)

    def test_repo_relative_refs_resolve_against_project_root(self) -> None:
        active = self.tmpdir / ".workline" / "active" / "2026-05-28-0915-example"
        active.mkdir(parents=True)
        (active / "prd.md").write_text("### FR-1 导入\n", encoding="utf-8")
        (self.tmpdir / "src").mkdir()
        (self.tmpdir / "src" / "main.c").write_text("int main(void)\n", encoding="utf-8")
        csv_path = active / "tasks.csv"
        write_csv(
            csv_path,
            [task(id="T001", refs="FR-1 src/main.c docs/missing.md"), REVIEW],
        )
        _, out, _ = self.run_cmd(["validate", str(csv_path)])
        self.assertNotIn("refs-invalid", out)
        self.assertIn("引用路径不存在：docs/missing.md", out)
        self.assertNotIn("引用路径不存在：src/main.c", out)

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
        self.write_run(complete_log())
        self.approve_execution()
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
        self.write_run(complete_log() + "\n" + complete_log("REVIEW"))
        self.approve_execution()
        self.run_cmd(["set", str(self.csv_path), "REVIEW", "--state", "doing"])
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "done", "--commit", "no-change"]
        )
        (self.tmpdir / "brief.md").write_text("# b\n", encoding="utf-8")
        (self.tmpdir / "references").mkdir(exist_ok=True)
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("commit 为空", err)

    def test_add_inserts_before_review(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        self.approve_execution()
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
        self.assertEqual(rows[-1]["state"], "todo")
        gate_rows = M.read_gates(self.tmpdir / "run.md")
        by_id = {row["gate"]: row for row in gate_rows}
        self.assertEqual(by_id["tasks-review"]["status"], "未审查")
        self.assertEqual(by_id["execute"]["status"], "未确认")

    def test_gates_require_and_prd_pass_resets_downstream(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        self.run_cmd(
            ["gates-set", str(self.tmpdir), "--gate", "materials", "--status", "CONFIRMED", "--actor", "user"]
        )
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
        self.assertEqual(code, 1)
        self.assertIn("缺少 ## 阶段门禁", err)
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
                "--init",
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
        self.assertIn("bulk import", (active / "brief.md").read_text(encoding="utf-8"))

        write_csv(
            self.csv_path,
            [task(id="T001", state="doing"), REVIEW],
        )
        (self.tmpdir / "brief.md").write_text("# brief\n", encoding="utf-8")
        self.write_run(complete_log() + "\n" + complete_log("REVIEW"))
        (self.tmpdir / "references").mkdir(exist_ok=True)
        self.approve_execution()
        self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "done", "--commit", "no-change"]
        )
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "doing"]
        )
        self.run_cmd(
            ["set", str(self.csv_path), "REVIEW", "--state", "done", "--commit", "no-change"]
        )
        code, out, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertIn("archive-check 通过", out)

        self.run_cmd(
            ["gates-set", str(self.tmpdir), "--gate", "execute", "--status", "未确认"]
        )
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("execute 不是 CONFIRMED", err)

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
        self.write_run(complete_log(), repo)
        self.approve_execution(repo)
        code, _, err = self.run_cmd(
            ["set", str(csv_path), "T001", "--state", "done", "--commit", digest[:12]]
        )
        self.assertEqual(code, 0, err)

    def test_gate_order_and_artifact_freshness_are_enforced(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        code, _, err = self.run_cmd(
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
        self.assertEqual(code, 1)
        self.assertIn("prd-review", err)

        self.approve_execution()
        (self.tmpdir / "prd.md").write_text("### FR-1 changed\n", encoding="utf-8")
        code, _, err = self.run_cmd(
            [
                "require-gates",
                str(self.tmpdir),
                "--require",
                "materials=CONFIRMED,WAIVED",
                "--require",
                "prd-review=PASS",
                "--require",
                "tasks-review=PASS",
                "--require",
                "execute=CONFIRMED",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("prd-review 已失效", err)

    def test_task_plan_change_invalidates_review_and_execute(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        self.approve_execution()
        rows = M.read_rows(self.csv_path)
        rows[0]["description"] = "changed after approval"
        write_csv(self.csv_path, rows)
        code, _, err = self.run_cmd(
            ["require-gates", str(self.tmpdir), "--require", "execute=CONFIRMED"]
        )
        self.assertEqual(code, 1)
        self.assertIn("tasks-review 已失效", err)

    # 以下四条锁住「让工具当规范」的前提：错误消息必须自带完整正确答案。
    # 消息被削成只说"你错了"而不说"该怎样"时，这些用例失败。

    def test_refs_invalid_message_lists_allowed_forms(self) -> None:
        write_csv(self.csv_path, [task(id="T001", refs="../evil"), REVIEW])
        code, out, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        for fragment in ("FR-2", "references/", "evidence/", ".workline/notes/", "绝对路径"):
            self.assertIn(fragment, out)

    def test_blocked_message_explains_every_prefix(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "blocked", "--notes", "等一下"]
        )
        self.assertEqual(code, 1)
        for fragment in ("wait-user", "env-missing", "verify-failed", "环境缺失", "验证未通过"):
            self.assertIn(fragment, err)

    def test_verification_message_says_how_to_write_it(self) -> None:
        write_csv(self.csv_path, [task(id="T001", verification=""), REVIEW])
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        for fragment in ("怎样算过", "Skill", "退出码"):
            self.assertIn(fragment, err)

    def test_warning_output_separates_blocking_from_advisory(self) -> None:
        write_csv(self.csv_path, [task(id="T001", refs="../evil"), REVIEW])
        code, out, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertIn("[阻断] refs-invalid", out)
        self.assertIn("gates-set tasks-review=PASS", out)

        write_csv(self.csv_path, [task(id="T001", refs=""), REVIEW])
        code, out, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        self.assertIn("[提示] refs-missing", out)
        self.assertNotIn("[阻断] refs-missing", out)

    def test_mode_message_states_the_judgement_rule(self) -> None:
        write_csv(self.csv_path, [task(id="T001", mode="MANUAL"), REVIEW])
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        for fragment in ("AFK", "HITL", "判定权"):
            self.assertIn(fragment, err)

    def test_blocked_requires_reason_prefix(self) -> None:
        write_csv(self.csv_path, [task(id="T001"), REVIEW])
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T001", "--state", "blocked", "--notes", "等一下"]
        )
        self.assertEqual(code, 1)
        self.assertIn("分类前缀", err)

        code, _, err = self.run_cmd(
            [
                "set",
                str(self.csv_path),
                "T001",
                "--state",
                "blocked",
                "--notes",
                "wait-user: 等用户确认导入页提示",
            ]
        )
        self.assertEqual(code, 0, err)

    def test_next_reports_blocked_reasons(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", state="blocked", notes="wait-user: 等人确认"),
                task(id="T002", state="blocked", notes="env-missing: 没装 keil"),
                task(id="T003", state="blocked", notes="没写前缀的历史备注"),
                REVIEW,
            ],
        )
        code, out, err = self.run_cmd(["next", str(self.csv_path)])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertIsNone(payload["next"])
        self.assertEqual(payload["blocked"]["wait-user"], ["T001"])
        self.assertEqual(payload["blocked"]["env-missing"], ["T002"])
        self.assertEqual(payload["blocked"]["unclassified"], ["T003"])
        self.assertIn("blocked(wait-user)", payload["detail"]["T001"])

    def test_archive_check_groups_blocked_by_reason(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(id="T001", state="blocked", notes="env-missing: 没有探针"),
                task(id="REVIEW", title="review", description="audit", verification="", refs="", state="todo"),
            ],
        )
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("还有 blocked 任务（env-missing）：T001", err)

    def test_set_rejects_unsatisfied_dependencies(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001"), task(id="T002", depends_on="T001"), REVIEW],
        )
        self.approve_execution()
        code, _, err = self.run_cmd(
            ["set", str(self.csv_path), "T002", "--state", "doing"]
        )
        self.assertEqual(code, 1)
        self.assertIn("依赖未满足", err)

    def test_review_refs_do_not_cover_requirements(self) -> None:
        write_csv(
            self.csv_path,
            [task(id="T001", refs="references/input.md"), task(id="REVIEW", refs="FR-1")],
        )
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertIn("fr-uncovered", out)

    def test_archive_blocks_dangling_refs(self) -> None:
        references = self.tmpdir / "references"
        references.mkdir(exist_ok=True)
        material = references / "input.md"
        material.write_text("input\n", encoding="utf-8")
        write_csv(
            self.csv_path,
            [
                task(id="T001", state="done", commit="no-change", refs="FR-1 references/input.md"),
                task(id="REVIEW", state="done", commit="no-change", refs=""),
            ],
        )
        (self.tmpdir / "brief.md").write_text("# brief\n", encoding="utf-8")
        self.write_run(complete_log() + "\n" + complete_log("REVIEW"))
        self.approve_execution()
        material.unlink()
        code, _, err = self.run_cmd(["archive-check", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("refs-not-found", err)

    def test_invalid_task_id_is_rejected(self) -> None:
        write_csv(self.csv_path, [task(id="bad id"), REVIEW])
        code, _, err = self.run_cmd(["validate", str(self.csv_path)])
        self.assertEqual(code, 1)
        self.assertIn("id 非法", err)

    def test_ref_paths_cannot_escape_or_use_ambiguous_separators(self) -> None:
        write_csv(
            self.csv_path,
            [
                task(
                    id="T001",
                    refs=r"FR-1 references/../secret evidence/./result references\outside",
                ),
                REVIEW,
            ],
        )
        _, out, _ = self.run_cmd(["validate", str(self.csv_path)])
        self.assertGreaterEqual(out.count("refs-invalid"), 3)


if __name__ == "__main__":
    unittest.main()
