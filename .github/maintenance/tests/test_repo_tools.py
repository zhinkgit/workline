from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MAINTENANCE_DIR = Path(__file__).resolve().parents[1]
if str(MAINTENANCE_DIR) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE_DIR))

from package_release import build_archives, write_checksums  # noqa: E402
from repo_checks import (  # noqa: E402
    check_readme_skills,
    check_reference_copies,
    check_script_copies,
    check_skill_metadata,
    local_link_target,
    matching_files,
    parse_frontmatter,
)
from run_tests import find_test_directories  # noqa: E402


class RepositoryCheckTests(unittest.TestCase):
    def test_matching_files_ignores_skip_names_above_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dist" / "repo"
            root.mkdir(parents=True)
            expected = root / "README.md"
            expected.write_text("content", encoding="utf-8")

            self.assertEqual(matching_files(root, "*.md"), [expected])

    def test_test_discovery_ignores_skip_names_above_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".venv" / "repo"
            tests = root / "demo" / "tests"
            tests.mkdir(parents=True)
            (tests / "test_demo.py").write_text("", encoding="utf-8")

            self.assertEqual(find_test_directories(root), [tests])

    def test_frontmatter_parser_reads_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text(
                "---\nname: demo\ndescription: demo skill\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_frontmatter(path)["name"], "demo")

    def test_frontmatter_parser_reads_folded_description(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text(
                "---\nname: demo\ndescription: >-\n  first line\n  second line\n---\n",
                encoding="utf-8",
            )
            self.assertEqual(
                parse_frontmatter(path)["description"],
                "first line second line",
            )

    def test_skill_check_rejects_empty_folded_description(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: >-\n---\n",
                encoding="utf-8",
            )
            self.assertIn(
                "demo\\SKILL.md: description must not be empty"
                if os.name == "nt"
                else "demo/SKILL.md: description must not be empty",
                check_skill_metadata(root),
            )

    def test_skill_check_ignores_similarly_named_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "NOT_SKILL.md").write_text("no frontmatter", encoding="utf-8")
            self.assertEqual(check_skill_metadata(root), [])

    def test_local_link_parser_ignores_urls_and_anchors(self) -> None:
        self.assertIsNone(local_link_target("https://example.com/doc"))
        self.assertIsNone(local_link_target("#section"))
        self.assertEqual(local_link_target("docs/guide.md#start"), "docs/guide.md")

    def test_readme_check_requires_backticked_skill_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "workline-init").mkdir()
            (root / "workline-init" / "SKILL.md").write_text("", encoding="utf-8")
            (root / "README.md").write_text("workline-init", encoding="utf-8")
            errors = check_readme_skills(root)
            self.assertIn("README.md does not list skill: workline-init", errors)

            (root / "README.md").write_text("`workline-init`", encoding="utf-8")
            self.assertEqual(check_readme_skills(root), [])

    def test_script_copies_must_be_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "workline-tasks",
                "workline-run",
                "workline-review",
                "workline-archive",
            ):
                scripts = root / name / "scripts"
                scripts.mkdir(parents=True)
                (scripts / "workline_csv.py").write_text("same\n", encoding="utf-8")
            self.assertEqual(check_script_copies(root), [])

            (
                root / "workline-run" / "scripts" / "workline_csv.py"
            ).write_text("different\n", encoding="utf-8")
            errors = check_script_copies(root)
            self.assertTrue(any("script copy diverged" in item for item in errors))
            self.assertEqual(len(errors), 4)

    def test_reference_copies_must_be_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "workline-tasks",
                "workline-run",
                "workline-review",
                "workline-archive",
            ):
                (root / name).mkdir()
                (root / name / "REFERENCE.md").write_text("same", encoding="utf-8")
            self.assertEqual(check_reference_copies(root), [])

            (root / "workline-run" / "REFERENCE.md").write_text(
                "different", encoding="utf-8"
            )
            errors = check_reference_copies(root)
            self.assertTrue(any("reference copy diverged" in item for item in errors))
            self.assertEqual(len(errors), 4)


class ReleasePackageTests(unittest.TestCase):
    def test_release_archives_exclude_tests_and_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            (skill / "tests").mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (skill / "script.py").write_text("print('ok')\n", encoding="utf-8")
            (skill / "tests" / "test_demo.py").write_text("", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")

            first = root / "first"
            second = root / "second"
            first_archives = build_archives(root, first, "1.0.0")
            second_archives = build_archives(root, second, "1.0.0")

            self.assertEqual(
                [path.read_bytes() for path in first_archives],
                [path.read_bytes() for path in second_archives],
            )
            with zipfile.ZipFile(first / "workline-demo-1.0.0.zip") as archive:
                self.assertIn("demo/SKILL.md", archive.namelist())
                self.assertNotIn("demo/tests/test_demo.py", archive.namelist())

            checksum_file = write_checksums(first, first_archives)
            self.assertIn("workline-demo-1.0.0.zip", checksum_file.read_text())

    def test_release_output_cannot_be_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                build_archives(root, root, "1.0.0")

    def test_invalid_version_does_not_delete_existing_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            output = root / "dist"
            output.mkdir()
            existing = output / "workline-demo-1.0.0.zip"
            existing.write_bytes(b"existing")

            with self.assertRaises(ValueError):
                build_archives(root, output, "*")

            self.assertEqual(existing.read_bytes(), b"existing")

    def test_rebuild_preserves_unrelated_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            output = root / "dist"
            output.mkdir()
            unrelated = output / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")
            previous_version = output / "workline-demo-0.9.0.zip"
            previous_version.write_bytes(b"previous")
            retired_skill = output / "workline-retired-1.0.0.zip"
            retired_skill.write_bytes(b"stale")

            build_archives(root, output, "1.0.0")
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")
            self.assertEqual(previous_version.read_bytes(), b"previous")
            self.assertFalse(retired_skill.exists())

    def test_custom_output_does_not_package_existing_dist_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            dist = skill / "dist"
            dist.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (dist / "previous-build.zip").write_bytes(b"previous")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            output = Path(directory) / "custom-output"

            archives = build_archives(root, output, "1.0.0")

            with zipfile.ZipFile(archives[0]) as archive:
                self.assertFalse(
                    any(name.startswith("demo/dist/") for name in archive.namelist())
                )

    def test_output_can_be_an_ancestor_of_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            root = output / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")

            archives = build_archives(root, output, "1.0.0")

            with zipfile.ZipFile(archives[0]) as archive:
                self.assertIn("demo/SKILL.md", archive.namelist())

    def test_output_directory_is_not_discovered_as_a_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            output = root / "dist"
            output.mkdir()
            (output / "SKILL.md").write_text("stale", encoding="utf-8")

            archives = build_archives(root, output, "1.0.0")

            self.assertEqual(
                [path.name for path in archives],
                ["workline-1.0.0.zip", "workline-demo-1.0.0.zip"],
            )

    def test_output_inside_skill_is_not_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            output = skill / "release-output"
            output.mkdir()
            (output / "private.txt").write_text("not packaged", encoding="utf-8")

            archives = build_archives(root, output, "1.0.0")

            with zipfile.ZipFile(archives[0]) as archive:
                self.assertFalse(
                    any(
                        name.startswith("demo/release-output/")
                        for name in archive.namelist()
                    )
                )

    def test_output_inside_skill_does_not_validate_its_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            output = skill / "release-output"
            output.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            outside = Path(directory) / "private.txt"
            outside.write_text("private", encoding="utf-8")
            try:
                os.symlink(outside, output / "private-link.txt")
            except OSError:
                self.skipTest("symbolic links are unavailable")

            archives = build_archives(root, output, "1.0.0")

            with zipfile.ZipFile(archives[0]) as archive:
                self.assertFalse(
                    any(
                        name.startswith("demo/release-output/")
                        for name in archive.namelist()
                    )
                )

    def test_release_rejects_symbolic_link_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "LICENSE").write_text("MIT", encoding="utf-8")
            outside = Path(directory) / "private.txt"
            outside.write_text("private", encoding="utf-8")
            link = skill / "private-link.txt"
            try:
                os.symlink(outside, link)
            except OSError:
                self.skipTest("symbolic links are unavailable")

            with self.assertRaises(ValueError):
                build_archives(root, root / "dist", "1.0.0")

    def test_release_works_without_license(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            skill = root / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("demo", encoding="utf-8")

            archives = build_archives(root, root / "dist", "1.0.0")
            with zipfile.ZipFile(archives[1]) as archive:
                self.assertIn("demo/SKILL.md", archive.namelist())
                self.assertNotIn("LICENSE", archive.namelist())


if __name__ == "__main__":
    unittest.main()
