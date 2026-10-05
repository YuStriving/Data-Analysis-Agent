"""Exercise documentation checks against disposable, real Git repositories."""

from __future__ import annotations

import hashlib
import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


checker = importlib.import_module("check-docs")


class DocumentationChecksTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="documentation-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True, capture_output=True)
        for name in (
            "AGENTS.md", "README.md", "docs/README.md", "docs/architecture/README.md",
            "docs/DESIGN.md", "docs/design-docs/index.md", "docs/design-docs/core-beliefs.md",
            "docs/WORKFLOW.md", "docs/spec/README.md", "docs/spec/template.md",
            "docs/exec-plans/README.md",
        ):
            self.write(name, "# Entry\n")
        self.write("skills/README.md", "| 分类 | 放置内容 | 当前 Skills |\n| --- | --- | --- |\n"
                   "| [design](design/README.md) | 设计 | 暂无 |\n")
        self.write("skills/design/README.md", "# Design Skills\n\n当前暂无归档 Skill。\n")

    def write(self, name: str, text: str):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def errors(self):
        return checker.check(self.root)[2]

    def add_skill(self, *, category: bool = True, summary: bool = True):
        self.write("skills/design/frontend-design/SKILL.md", "# Frontend Design\n")
        if category:
            self.write("skills/design/README.md", "# Design Skills\n\n"
                       "- [frontend-design](frontend-design/SKILL.md)\n")
        if summary:
            self.write("skills/README.md", "| 分类 | 放置内容 | 当前 Skills |\n| --- | --- | --- |\n"
                       "| [design](design/README.md) | 设计 | "
                       "[frontend-design](design/frontend-design/SKILL.md) |\n")

    def assert_issue(self, rule: str, target: str, index: str):
        issues = self.errors()
        self.assertTrue(any(rule in issue and target in issue and index in issue for issue in issues), issues)

    def test_consistent_empty_category_passes(self):
        self.assertEqual([], self.errors())

    def test_registered_skill_passes(self):
        self.add_skill()
        self.assertEqual([], self.errors())

    def test_visible_code_labels_remain_valid_navigation(self):
        self.add_skill()
        self.write("skills/design/README.md", "# Design\n- [`frontend-design`](frontend-design/SKILL.md)\n")
        self.assertEqual([], self.errors())

    def test_visible_code_label_with_missing_target_fails(self):
        self.write("docs/README.md", "# Docs\n[`missing`](missing.md)\n")
        self.assertTrue(any("Missing link target" in issue for issue in self.errors()), self.errors())

    def test_html_comments_and_indented_examples_do_not_create_navigation(self):
        self.write("docs/README.md", "# Docs\n\n<!-- [hidden](missing.md) -->\n"
                   "<!--\n[hidden](also-missing.md)\n-->\n\n"
                   "    [indented](missing-example.md)\n\n\t[tab example](another-missing.md)\n")
        self.assertEqual([], self.errors())

    def test_comment_markers_in_code_examples_do_not_hide_later_navigation(self):
        for example in ("```html\n<!--\n```", "`<!--`", "    <!--"):
            with self.subTest(example=example):
                self.write("docs/README.md", f"# Docs\n\n{example}\n\n[workflow](WORKFLOW.md)\n")
                self.assertEqual([], self.errors())

    def test_hidden_empty_declarations_do_not_contradict_registered_category(self):
        self.add_skill()
        self.write("skills/design/README.md", "# Design\n<!-- 当前暂无归档 Skill。 -->\n\n"
                   "    当前暂无归档 Skill。\n\n[frontend-design](frontend-design/SKILL.md)\n")
        self.assertEqual([], self.errors())

    def test_skill_directly_in_category_directory_is_rejected(self):
        for name in ("skills/design/SKILL.md", "skills/SKILL.md", "skills/design/example/nested/SKILL.md"):
            with self.subTest(name=name):
                self.write(name, "# Misplaced Skill\n")
                self.assert_issue("skills-layout", name, "skills/<category>/<skill>/SKILL.md")

    def test_escaped_link_literal_does_not_create_navigation(self):
        self.write("docs/README.md", "# Docs\n\\[example](missing.md)\n")
        self.assertEqual([], self.errors())

    def test_image_target_existence_is_still_checked(self):
        self.write("docs/README.md", "# Docs\n![image](missing.png)\n")
        self.assertTrue(any("Missing link target" in issue for issue in self.errors()), self.errors())

    def test_escaped_pipe_in_summary_description_does_not_shift_skill_column(self):
        self.add_skill()
        self.write("skills/README.md", "| 分类 | 放置内容 | 当前 Skills |\n| --- | --- | --- |\n"
                   "| [design](design/README.md) | UI \\| UX | "
                   "[frontend-design](design/frontend-design/SKILL.md) |\n")
        self.assertEqual([], self.errors())

    def test_missing_category_registration_fails(self):
        self.add_skill(category=False)
        self.assert_issue("skills-category", "skills/design/frontend-design/SKILL.md", "skills/design/README.md")

    def test_missing_summary_registration_fails(self):
        self.add_skill(summary=False)
        self.assert_issue("skills-summary", "skills/design/frontend-design/SKILL.md", "skills/README.md")

    def test_summary_link_under_wrong_category_does_not_register_skill(self):
        self.add_skill(summary=False)
        self.write("skills/workflow/README.md", "# Workflow Skills\n当前暂无归档 Skill。\n")
        self.write("skills/README.md", "| 分类 | 放置内容 | 当前 Skills |\n| --- | --- | --- |\n"
                   "| [design](design/README.md) | 设计 | 暂无 |\n"
                   "| [workflow](workflow/README.md) | 流程 | "
                   "[frontend-design](design/frontend-design/SKILL.md) |\n")
        self.assert_issue("skills-summary", "skills/design/frontend-design/SKILL.md", "skills/README.md")

    def test_nonempty_category_cannot_claim_empty_even_with_registration(self):
        self.add_skill()
        self.write("skills/design/README.md", "# Design Skills\n当前暂无归档 Skill；\n"
                   "- [frontend-design](frontend-design/SKILL.md)\n")
        self.assert_issue("skills-category", "empty declaration", "skills/design/README.md")

    def test_nonempty_summary_cannot_claim_empty_even_with_registration(self):
        self.add_skill()
        self.write("skills/README.md", "| 分类 | 放置内容 | 当前 Skills |\n| --- | --- | --- |\n"
                   "| [design](design/README.md) | 设计 | 暂无；"
                   "[frontend-design](design/frontend-design/SKILL.md) |\n")
        self.assert_issue("skills-summary", "empty declaration", "skills/README.md")

    def test_new_category_requires_summary_row(self):
        self.write("skills/quality/README.md", "# Quality Skills\n当前暂无归档 Skill。\n")
        self.assert_issue("skills-summary", "skills/quality/README.md", "skills/README.md")

    def test_missing_category_index_fails(self):
        self.add_skill()
        (self.root / "skills/design/README.md").unlink()
        self.assert_issue("skills-category", "Missing index", "skills/design/README.md")

    def test_missing_summary_index_fails(self):
        (self.root / "skills/README.md").unlink()
        self.assert_issue("skills-summary", "Missing index", "skills/README.md")

    def test_resources_and_example_paths_are_not_required_entries(self):
        self.add_skill()
        self.write("skills/design/frontend-design/LICENSE.txt", "License\n")
        self.write("skills/design/frontend-design/references/guide.md", "# Guidance\n")
        self.write("docs/README.md", "# Docs\n```markdown\n[example](missing.md)\n```\n"
                   "`[inline example](also-missing.md)`\n")
        self.assertEqual([], self.errors())

    def test_ignored_resources_and_skills_are_not_scanned(self):
        self.write(".gitignore", ".agents/\nskills/design/private/\nnode_modules/\n")
        self.write(".agents/private.md", "[bad](missing.md)\n")
        self.write("node_modules/package/README.md", "[bad](missing.md)\n")
        self.write("skills/design/private/SKILL.md", "[bad](missing.md)\n")
        self.assertEqual([], self.errors())

    def test_unregistered_source_file_does_not_require_directory_inventory(self):
        self.write("backend-agent/src/example.py", "print('fixture')\n")
        self.write("backend-agent/docs/topic.md", "# Selected topic\n")
        self.assertEqual([], self.errors())

    def test_deleted_and_moved_targets_fail_existing_link_check(self):
        for action in ("delete", "move"):
            with self.subTest(action=action):
                self.add_skill()
                target = self.root / "skills/design/frontend-design/SKILL.md"
                if action == "delete":
                    target.unlink()
                else:
                    target.rename(target.with_name("renamed.md"))
                self.assertTrue(any("Missing link target" in issue and "frontend-design/SKILL.md" in issue
                                    for issue in self.errors()), self.errors())

    def test_missing_required_entrypoint_fails(self):
        (self.root / "AGENTS.md").unlink()
        self.assertIn("Missing entrypoint: AGENTS.md", self.errors())

    def test_nested_agent_map_is_rejected(self):
        self.write("backend-java/AGENTS.md", "# Local map\n")
        self.assertTrue(any("Nested Agent map is not allowed: backend-java/AGENTS.md" in issue
                            for issue in self.errors()), self.errors())

    def test_local_heading_anchors_are_still_checked(self):
        self.write("docs/README.md", "# Docs\n[valid](WORKFLOW.md#entry)\n[bad](WORKFLOW.md#absent)\n")
        errors = self.errors()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Missing heading anchor", errors[0])

    def test_encoded_link_paths_and_heading_anchors_pass(self):
        self.write("docs/中文 case.md", "# Case\n")
        self.write("docs/README.md", "# Docs\n[case](%E4%B8%AD%E6%96%87%20case.md#case)\n")
        self.assertEqual([], self.errors())

    def test_link_leaving_repository_fails(self):
        self.write("README.md", "# Entry\n[outside](../outside.md)\n")
        self.assertTrue(any("Link leaves repository" in issue for issue in self.errors()))

    def test_retired_root_directory_fails(self):
        (self.root / "spec").mkdir()
        self.assertIn("Retired root directory exists: spec/", self.errors())

    def test_retired_documentation_directory_fails(self):
        (self.root / "docs/tests").mkdir()
        self.assertIn("Retired documentation directory exists: docs/tests/", self.errors())

    def test_plan_lifecycle_accepts_active_and_completed_statuses(self):
        self.write("docs/exec-plans/active/governance/active.md", "# Active\n- 状态：in_progress\n")
        self.write("docs/exec-plans/completed/governance/completed.md", "# Completed\n- Status: done\n")
        self.assertEqual([], self.errors())

    def test_completed_plan_must_be_done(self):
        self.write("docs/exec-plans/completed/governance/unfinished.md", "# Unfinished\n- 状态：in_progress\n")
        self.assertTrue(any("Completed Plan must be done" in issue for issue in self.errors()), self.errors())

    def test_active_plan_cannot_be_done(self):
        self.write("docs/exec-plans/active/governance/finished.md", "# Finished\n- 状态：done\n")
        self.assertTrue(any("Active Plan cannot be done" in issue for issue in self.errors()), self.errors())

    def test_plan_requires_a_known_status(self):
        for filename, metadata, expected in (
            ("missing.md", "", "Missing status"),
            ("invalid.md", "- 状态：complete\n", "Invalid status"),
        ):
            with self.subTest(filename=filename):
                self.write(f"docs/exec-plans/active/governance/{filename}", f"# Plan\n{metadata}")
                self.assertTrue(any(expected in issue and filename in issue for issue in self.errors()), self.errors())

    def test_cli_exit_codes_and_read_only_operation(self):
        script = self.root / "scripts/ci/check-docs.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(Path(checker.__file__), script)
        for failing in (False, True):
            with self.subTest(failing=failing):
                if failing:
                    self.write("docs/README.md", "# Docs\n[missing](missing.md)\n")
                before = {path.relative_to(self.root): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in self.root.rglob("*") if path.is_file()}
                result = subprocess.run([sys.executable, "-B", str(script)], cwd=self.root,
                                        capture_output=True, text=True, encoding="utf-8")
                after = {path.relative_to(self.root): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in self.root.rglob("*") if path.is_file()}
                self.assertEqual(1 if failing else 0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(before, after)
                if failing:
                    self.assertIn("Missing link target", result.stdout)


if __name__ == "__main__":
    unittest.main()
