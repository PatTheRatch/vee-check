"""Tests for the gate and the CLI. Standard library only.

Run from the repo root:  python3 -m unittest discover -s tests -v
Nothing here touches your real ~/.vee-check: every test gets its own folders.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "scripts" / "gate.py"
VC = REPO / "scripts" / "vc.py"
EXAMPLE = REPO / "examples" / "pandas-playground" / "quiz-example"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.project = self.tmp / "project"
        self.home = self.tmp / "home"
        self.project.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = {**os.environ, "VEE_CHECK_HOME": str(self.home), "VEE_CHECK_NO_OPEN": "1"}
        self.env.pop("CLAUDE_PROJECT_DIR", None)

    def vc(self, *args, cwd=None):
        done = subprocess.run([sys.executable, "-B", str(VC), *args], cwd=cwd or self.project,
                              env=self.env, text=True, capture_output=True)
        return done.returncode, done.stdout + done.stderr

    def gate(self, path, key="file_path", stdin=None, root=None):
        text = stdin if stdin is not None else json.dumps(
            {"tool_name": "Edit", "cwd": str(self.project), "tool_input": {key: str(path)}})
        done = subprocess.run([sys.executable, "-B", str(GATE)], input=text, text=True, capture_output=True,
                              env={**self.env, "CLAUDE_PROJECT_DIR": str(root or self.project)})
        return done.returncode, done.stderr

    def write_example(self, slug="pandas-groupby"):
        quizzes = self.project / ".vee-check" / "quizzes"
        quizzes.mkdir(parents=True, exist_ok=True)
        for source in EXAMPLE.iterdir():
            shutil.copy(source, quizzes / source.name.replace("pandas-groupby", slug))

    def page_data(self, slug="pandas-groupby"):
        page = (self.project / ".vee-check" / "quizzes" / f"{slug}.html").read_text(encoding="utf-8")
        block = re.search(r'<script id="vc-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        return json.loads(block), page

    def start_and_build(self, topic="pandas groupby"):
        self.assertEqual(self.vc("start", topic)[0], 0)
        self.write_example()
        code, out = self.vc("build")
        self.assertEqual(code, 0, out)
        data, _ = self.page_data()
        return base64.b64decode(data["code"]).decode()


class GateTests(Base):
    def pend(self):
        state = self.project / ".vee-check"
        state.mkdir(exist_ok=True)
        (state / "pending.json").write_text(json.dumps({"topic": "pandas groupby"}))

    def test_open_when_nothing_is_pending(self):
        self.assertEqual(self.gate(self.project / "app.py")[0], 0)

    def test_blocks_project_files_while_pending(self):
        self.pend()
        code, message = self.gate(self.project / "app.py")
        self.assertEqual(code, 2)
        self.assertIn("pandas groupby", message)
        self.assertEqual(self.gate(self.project / "nb.ipynb", key="notebook_path")[0], 2)
        self.assertEqual(self.gate("app.py")[0], 2)

    def test_allows_files_inside_the_state_folder(self):
        self.pend()
        self.assertEqual(self.gate(self.project / ".vee-check" / "quizzes" / "a.json")[0], 0)
        self.assertEqual(self.gate(".vee-check/quizzes/a.html")[0], 0)

    def test_lookalike_folder_and_climbing_out_are_blocked(self):
        self.pend()
        self.assertEqual(self.gate(self.project / ".vee-check-notes" / "x.py")[0], 2)
        self.assertEqual(self.gate(f"{self.project}/.vee-check/../app.py")[0], 2)

    def test_unreadable_input_blocks_only_while_pending(self):
        self.assertEqual(self.gate(None, stdin="not json")[0], 0)
        self.pend()
        self.assertEqual(self.gate(None, stdin="not json")[0], 2)
        self.assertEqual(self.gate(None, stdin=json.dumps({"tool_input": {}}))[0], 2)


class CopilotTests(Base):
    """GitHub Copilot sends different field names and tool names from Claude Code."""

    def pend(self):
        state = self.project / ".vee-check"
        state.mkdir(exist_ok=True)
        (state / "pending.json").write_text(json.dumps({"topic": "pandas groupby"}))

    def copilot(self, tool, args):
        payload = {"sessionId": "s", "timestamp": 1, "cwd": str(self.project), "toolName": tool, "toolArgs": args}
        done = subprocess.run([sys.executable, "-B", str(GATE)], input=json.dumps(payload), text=True, capture_output=True,
                              env={k: v for k, v in self.env.items() if k != "CLAUDE_PROJECT_DIR"})
        return done.returncode, done.stdout, done.stderr

    def test_copilot_edits_are_blocked_with_a_deny_decision(self):
        self.pend()
        for tool, args in (("edit", {"path": "app.py"}), ("create", {"path": str(self.project / "new.py")}),
                           ("edit", json.dumps({"filePath": "src/app.py"}))):          # args as JSON text
            with self.subTest(tool=tool, args=args):
                code, out, err = self.copilot(tool, args)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out)["permissionDecision"], "deny")
                self.assertIn("pandas groupby", json.loads(out)["permissionDecisionReason"])

    def test_copilot_can_still_read_run_commands_and_write_the_quiz(self):
        self.pend()
        for tool, args in (("view", {"path": "app.py"}), ("bash", {"command": "python3 vc.py status"}),
                           ("grep", {"pattern": "x"}), ("ask_user", {"question": "?"}),
                           ("create", {"path": ".vee-check/quizzes/pandas-groupby.json"})):
            with self.subTest(tool=tool):
                self.assertEqual(self.copilot(tool, args)[0], 0)

    def test_patches_are_checked_file_by_file(self):
        self.pend()
        outside = "*** Begin Patch\n*** Update File: app.py\n@@\n-a\n+b\n*** End Patch"
        inside = "*** Begin Patch\n*** Add File: .vee-check/quizzes/x.scene.js\n+1\n*** End Patch"
        mixed = inside.replace("*** End Patch", "*** Update File: app.py\n@@\n-a\n+b\n*** End Patch")
        self.assertEqual(self.copilot("apply_patch", outside)[0], 2)
        self.assertEqual(self.copilot("apply_patch", {"input": inside})[0], 0)
        self.assertEqual(self.copilot("apply_patch", mixed)[0], 2)

    def test_nothing_is_blocked_without_a_pending_quiz(self):
        self.assertEqual(self.copilot("edit", {"path": "app.py"})[0], 0)

    def test_debug_file_records_what_the_editor_sent(self):
        self.pend()
        (self.project / ".vee-check" / "debug").write_text("")
        self.copilot("edit", {"path": "app.py"})
        logged = json.loads((self.project / ".vee-check" / "hook-log.jsonl").read_text().splitlines()[-1])
        self.assertEqual(logged["toolName"], "edit")

    def test_installer_sets_up_skills_and_hook_and_removes_them(self):
        home = self.tmp / "copilot"
        run = lambda *extra: subprocess.run([sys.executable, "-B", str(REPO / "scripts" / "install_copilot.py"), *extra],
                                            env={**self.env, "COPILOT_HOME": str(home)}, text=True, capture_output=True)
        self.assertEqual(run().returncode, 0)
        skill = (home / "skills" / "vee-check" / "SKILL.md").read_text()
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill)
        self.assertIn(str(REPO.as_posix()) + "/scripts/vc.py", skill)
        self.assertTrue((home / "skills" / "vee-skip" / "SKILL.md").exists())
        hook = json.loads((home / "hooks" / "vee-check.json").read_text())["hooks"]["preToolUse"][0]
        self.assertIn("gate.py", hook["bash"])
        self.assertEqual(run("--uninstall").returncode, 0)
        self.assertFalse((home / "skills" / "vee-check").exists())
        self.assertFalse((home / "hooks" / "vee-check.json").exists())


class SkillTests(unittest.TestCase):
    def test_every_skill_is_named_after_its_folder(self):
        for page in sorted((REPO / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=page.parent.name):
                front = page.read_text(encoding="utf-8").split("---")[1]
                self.assertIn(f"name: {page.parent.name}\n", front)
                self.assertRegex(page.parent.name, r"^[a-z0-9-]{1,64}$")
                description = re.search(r"description: (.*)", front).group(1)
                self.assertLessEqual(len(description), 1024)


class CliTests(Base):
    def test_full_pass_flow(self):
        code = self.start_and_build()
        self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertEqual(self.gate(self.project / "app.py")[0], 2)
        pending = json.loads((self.project / ".vee-check" / "pending.json").read_text())
        self.assertNotIn(code, json.dumps(pending))            # only the fingerprint is stored
        self.assertEqual(self.vc("unlock", "AAAA-BBBB")[0], 1)
        self.assertEqual(self.gate(self.project / "app.py")[0], 2)
        status, out = self.vc("unlock", code.lower().replace("-", " ") + ".01-ny-1")
        self.assertEqual(status, 0, out)
        self.assertIn("+90 XP", out)                            # 50 for passing + 10 + 10 (retried) + 20 (first try)
        self.assertEqual(self.gate(self.project / "app.py")[0], 0)
        entry = json.loads((self.home / "history.jsonl").read_text().splitlines()[-1])
        self.assertEqual(entry["result"], "pass")
        self.assertEqual([q["tries"] for q in entry["questions"]], [2, 2, 1])
        self.assertEqual(entry["questions"][0]["answers"][1], entry["questions"][0]["options"][1])
        self.assertTrue((self.home / "log.html").exists())
        self.assertIn("Already passed", self.vc("start", "Pandas GroupBy!")[1])

    def test_short_code_without_answers_still_unlocks(self):
        code = self.start_and_build()
        status, out = self.vc("unlock", code)
        self.assertEqual(status, 0, out)
        entry = json.loads((self.home / "history.jsonl").read_text().splitlines()[-1])
        self.assertFalse(entry["answers_recorded"])

    def test_skip_opens_the_gate_but_does_not_pass(self):
        self.vc("start", "groupby")
        self.assertEqual(self.vc("skip")[0], 0)
        self.assertEqual(self.gate(self.project / "app.py")[0], 0)
        self.assertIn("Vee Check started", self.vc("start", "groupby")[1])

    def test_one_quiz_at_a_time_and_unlock_needs_a_built_page(self):
        self.vc("start", "groupby")
        self.assertEqual(self.vc("start", "joins")[0], 1)
        code, out = self.vc("unlock", "AAAA-BBBB")
        self.assertEqual(code, 1)
        self.assertIn("hasn't been built", out)
        self.assertEqual(self.vc("build")[0], 1)                # no content written yet

    def test_build_reports_bad_content(self):
        self.vc("start", "pandas groupby")
        bad = {"lesson": [{"type": "card", "title": "x"}], "questions": [{"type": "choice", "prompt": "p", "why": "w", "options": ["a", "b"], "answer": 5}]}
        quizzes = self.project / ".vee-check" / "quizzes"
        (quizzes / "pandas-groupby.json").write_text(json.dumps(bad))
        code, out = self.vc("build")
        self.assertEqual(code, 1)
        self.assertIn("body", out)
        self.assertIn("answer", out)

    def test_each_look_builds_and_only_arcade_gets_custom_code(self):
        for look in ("arcade", "classic", "plain"):
            with self.subTest(look=look):
                self.vc("config", "set", "look", look)
                self.start_and_build()
                data, page = self.page_data()
                self.assertEqual(data["look"], look)
                self.assertNotIn("__VC_", page)
                kinds = [scene["type"] for scene in data["lesson"]]
                self.assertEqual("custom" in kinds, look == "arcade")
                self.assertEqual(self.vc("skip")[0], 0)

    @unittest.skipUnless(shutil.which("node"), "node is not installed, so the page scripts can't be syntax-checked")
    def test_built_pages_have_valid_javascript(self):
        for look in ("arcade", "plain"):
            with self.subTest(look=look):
                self.vc("config", "set", "look", look)
                self.start_and_build()
                _, page = self.page_data()
                scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
                self.assertTrue(scripts)
                for number, script in enumerate(scripts):
                    path = self.tmp / f"{look}-{number}.js"
                    path.write_text(script, encoding="utf-8")
                    done = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
                    self.assertEqual(done.returncode, 0, done.stderr)
                self.vc("skip")

    def test_settings(self):
        self.assertEqual(self.vc("config", "set", "look", "sparkly")[0], 1)
        self.assertEqual(self.vc("config", "set", "questions", "11")[0], 1)
        self.assertEqual(self.vc("config", "set", "pass_bar", "2")[0], 0)
        self.assertEqual(self.vc("config", "set", "look", "plain", "--global")[0], 0)
        self.assertEqual(self.vc("config", "set", "lesson", "off")[0], 0)
        self.start_and_build()
        data, _ = self.page_data()
        self.assertEqual((data["pass_bar"], data["look"], data["lesson"]), (2, "plain", []))

    def test_review_reopens_a_passed_topic_without_a_code(self):
        code = self.start_and_build()
        self.vc("unlock", code)
        status, out = self.vc("review", "groupby")
        self.assertEqual(status, 0, out)
        review_page = Path(re.search(r": (/.*\.html)", out).group(1)).read_text(encoding="utf-8")
        block = re.search(r'<script id="vc-data" type="application/json">(.*?)</script>', review_page, re.S).group(1)
        review_data = json.loads(block)
        self.assertTrue(review_data["review"])
        self.assertNotIn("code", review_data)
        self.assertEqual(self.vc("review", "nothing like this")[0], 1)
        self.assertIn("pandas groupby", self.vc("topics")[1])

    def test_no_gate_lesson_never_blocks_and_still_logs(self):
        self.assertEqual(self.vc("start", "pandas groupby", "--no-gate")[0], 0)
        self.assertEqual(self.gate(self.project / "app.py")[0], 0)
        self.write_example()
        self.assertEqual(self.vc("build")[0], 0)
        data, _ = self.page_data()
        self.assertIs(data["gate"], False)
        self.assertEqual(data["zoom"], "how")
        self.assertTrue(any(scene.get("deeper") for scene in data["lesson"]))
        code = base64.b64decode(data["code"]).decode()
        status, out = self.vc("unlock", code + ".1-y-1")
        self.assertEqual(status, 0, out)
        entry = json.loads((self.home / "history.jsonl").read_text().splitlines()[-1])
        self.assertEqual((entry["gated"], entry["zoom"], entry["result"]), (False, "how", "pass"))

    def test_placement_quiz_sorts_concepts_into_known_and_learning(self):
        self.vc("concepts", "add", "Flask routes", "--group", "tools", "--weight", "8")
        self.vc("concepts", "add", "pandas groupby", "--group", "tools", "--weight", "5")
        self.vc("start", "Placement quiz", "--no-gate")
        question = lambda concept: {"type": "choice", "concept": concept, "prompt": "p", "why": "w", "options": ["a", "b"], "answer": 0}
        content = {"placement": True, "lesson": [], "questions": [question("Flask routes"), question("Flask routes"),
                                                                   question("pandas groupby"), question("pandas groupby")]}
        quizzes = self.project / ".vee-check" / "quizzes"
        (quizzes / "placement-quiz.json").write_text(json.dumps(content))
        self.assertEqual(self.vc("build")[0], 0)
        data, _ = self.page_data("placement-quiz")
        code = base64.b64decode(data["code"]).decode()
        status, out = self.vc("unlock", code + ".0-0-10-0")       # groupby: one question needed a second try
        self.assertEqual(status, 0, out)
        self.assertIn("Already known (no lesson needed): Flask routes", out)
        self.assertIn("On the learning list: pandas groupby", out)
        self.assertIn("Already passed", self.vc("start", "Flask routes")[1])
        listing = self.vc("concepts")[1]
        self.assertIn("Flask routes [code]: known", listing)
        self.assertIn("pandas groupby [code]: on the learning list", listing)

    def test_template_library_example_builds_in_every_look(self):
        tour = REPO / "examples" / "pandas-playground" / "quiz-example-templates" / "template-tour.json"
        self.vc("config", "set", "lesson_cards", "6")
        for look in ("arcade", "classic", "plain"):
            with self.subTest(look=look):
                self.vc("config", "set", "look", look)
                self.vc("start", "template tour")
                shutil.copy(tour, self.project / ".vee-check" / "quizzes" / "template-tour.json")
                code, out = self.vc("build")
                self.assertEqual(code, 0, out)
                data, _ = self.page_data("template-tour")
                self.assertEqual([s["type"] for s in data["lesson"]], ["sort", "match", "flow", "slider", "build", "compare"])
                self.assertEqual([q["type"] for q in data["questions"]], ["fill", "bug", "match"])
                self.vc("skip")

    def test_template_content_is_checked(self):
        self.vc("start", "bad templates")
        bad = {"lesson": [
            {"type": "sort", "title": "t", "items": [{"label": "a", "group": "x"}, {"label": "b", "group": "x"}]},
            {"type": "flow", "title": "t", "nodes": [{"label": "A"}, {"label": "B"}], "steps": [{"at": 5, "text": "x"}]},
            {"type": "build", "title": "t", "pieces": ["only one"]}],
            "questions": [{"type": "fill", "prompt": "p", "why": "w", "code": "no blank here", "options": ["a", "b"], "answer": 0},
                          {"type": "bug", "prompt": "p", "why": "w", "lines": ["a", "b"], "answer": 7}]}
        (self.project / ".vee-check" / "quizzes" / "bad-templates.json").write_text(json.dumps(bad))
        code, out = self.vc("build")
        self.assertEqual(code, 1)
        for expected in ("2 different groups", '"at"', '"pieces"', "___", "line with the bug"):
            self.assertIn(expected, out)

    def test_bug_and_match_answers_reach_the_history(self):
        tour = REPO / "examples" / "pandas-playground" / "quiz-example-templates" / "template-tour.json"
        self.vc("config", "set", "lesson_cards", "6")
        self.vc("start", "template tour")
        shutil.copy(tour, self.project / ".vee-check" / "quizzes" / "template-tour.json")
        self.vc("build")
        data, _ = self.page_data("template-tour")
        code = base64.b64decode(data["code"]).decode()
        status, out = self.vc("unlock", code + ".1-02-ny")
        self.assertEqual(status, 0, out)
        questions = json.loads((self.home / "history.jsonl").read_text().splitlines()[-1])["questions"]
        self.assertEqual(questions[1]["answers"], ["import pandas as pd", "totals = df.groupby('weight')['region'].sum()"])
        self.assertEqual(questions[2]["answers"], ["wrong", "right"])
        self.assertEqual([q["tries"] for q in questions], [1, 2, 2])

    def test_classic_is_the_default_look(self):
        self.start_and_build()
        self.assertEqual(self.page_data()[0]["look"], "classic")

    def test_tracks_switch_lessons_on_and_off(self):
        self.assertEqual(self.vc("config", "set", "tracks", "domain, architecture")[0], 0)
        self.assertEqual(self.vc("config", "set", "tracks", "vibes")[0], 1)
        code, out = self.vc("start", "list comprehensions")              # code track by default: switched off
        self.assertEqual(code, 0)
        self.assertIn("switched off", out)
        self.assertEqual(self.gate(self.project / "app.py")[0], 0)
        self.vc("concepts", "add", "tracking error", "--track", "domain")
        self.assertIn("(domain track)", self.vc("start", "tracking error")[1])   # picked up from the concept list
        self.assertEqual(self.gate(self.project / "app.py")[0], 2)

    def test_a_disputed_answer_is_logged_as_a_possible_issue_not_a_miss(self):
        self.vc("start", "tracking error", "--track", "domain")
        content = {"lesson": [], "questions": [
            {"type": "expect", "prompt": "Is tracking error annualized here?", "source": "risk.py:42",
             "options": ["Yes, times sqrt(252)", "No, it is daily"], "answer": 1, "why": "risk.py returns the daily figure."},
            {"type": "choice", "prompt": "p", "options": ["a", "b"], "answer": 0, "why": "w"}]}
        (self.project / ".vee-check" / "quizzes" / "tracking-error.json").write_text(json.dumps(content))
        self.assertEqual(self.vc("build")[0], 0)
        data, _ = self.page_data("tracking-error")
        self.assertEqual(data["track"], "domain")
        code = base64.b64decode(data["code"]).decode()
        status, out = self.vc("unlock", code + ".0d-0")                   # picked "Yes", then disputed the reveal
        self.assertEqual(status, 0, out)
        self.assertIn("POSSIBLE ISSUE (question 1)", out)
        self.assertIn("The user expected: Yes, times sqrt(252)", out)
        self.assertIn("risk.py:42", out)
        self.assertIn("+90 XP", out)                                      # 50 + 20 + 20: the dispute is not a miss
        entry = json.loads((self.home / "history.jsonl").read_text().splitlines()[-1])
        self.assertEqual((entry["track"], entry["questions"][0]["disputed"], entry["questions"][0]["missed"]), ("domain", True, False))
        self.assertIn("Is tracking error annualized here?", self.vc("issues")[1])
        self.assertIn("1 possible issue found", (self.home / "log.html").read_text())

    def test_commands_find_the_project_from_a_subfolder(self):
        self.vc("start", "groupby")
        sub = self.project / "src" / "deep"
        sub.mkdir(parents=True)
        self.assertIn("CLOSED", self.vc("status", cwd=sub)[1])


if __name__ == "__main__":
    unittest.main()
