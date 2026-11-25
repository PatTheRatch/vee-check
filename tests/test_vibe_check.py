"""Tests for the gate and the CLI. Standard library only.

Run from the repo root:  python3 -m unittest discover -s tests -v
Nothing here touches your real ~/.vibe-check: every test gets its own folders.
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
        self.env = {**os.environ, "VIBE_CHECK_HOME": str(self.home), "VIBE_CHECK_NO_OPEN": "1"}
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
        quizzes = self.project / ".vibe-check" / "quizzes"
        quizzes.mkdir(parents=True, exist_ok=True)
        for source in EXAMPLE.iterdir():
            shutil.copy(source, quizzes / source.name.replace("pandas-groupby", slug))

    def page_data(self, slug="pandas-groupby"):
        page = (self.project / ".vibe-check" / "quizzes" / f"{slug}.html").read_text(encoding="utf-8")
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
        state = self.project / ".vibe-check"
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
        self.assertEqual(self.gate(self.project / ".vibe-check" / "quizzes" / "a.json")[0], 0)
        self.assertEqual(self.gate(".vibe-check/quizzes/a.html")[0], 0)

    def test_lookalike_folder_and_climbing_out_are_blocked(self):
        self.pend()
        self.assertEqual(self.gate(self.project / ".vibe-check-notes" / "x.py")[0], 2)
        self.assertEqual(self.gate(f"{self.project}/.vibe-check/../app.py")[0], 2)

    def test_unreadable_input_blocks_only_while_pending(self):
        self.assertEqual(self.gate(None, stdin="not json")[0], 0)
        self.pend()
        self.assertEqual(self.gate(None, stdin="not json")[0], 2)
        self.assertEqual(self.gate(None, stdin=json.dumps({"tool_input": {}}))[0], 2)


class CliTests(Base):
    def test_full_pass_flow(self):
        code = self.start_and_build()
        self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertEqual(self.gate(self.project / "app.py")[0], 2)
        pending = json.loads((self.project / ".vibe-check" / "pending.json").read_text())
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
        self.assertIn("Vibe Check started", self.vc("start", "groupby")[1])

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
        quizzes = self.project / ".vibe-check" / "quizzes"
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

    def test_commands_find_the_project_from_a_subfolder(self):
        self.vc("start", "groupby")
        sub = self.project / "src" / "deep"
        sub.mkdir(parents=True)
        self.assertIn("CLOSED", self.vc("status", cwd=sub)[1])


if __name__ == "__main__":
    unittest.main()
