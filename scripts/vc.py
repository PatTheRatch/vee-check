#!/usr/bin/env python3
"""Vibe Check CLI. Claude runs these to close and open the gate.

  vc.py start "<topic>"        begin a Vibe Check (gate closes); says where to write the quiz content
                               add --no-gate for a lesson that doesn't block edits ("teach me X", tours)
  vc.py build                  turn the quiz content into the quiz page and open it in the browser
  vc.py unlock <code>          check a pasted pass code; if right, mark the topic passed (gate opens)
  vc.py skip                   drop the pending quiz without passing it (gate opens)
  vc.py status                 show the gate, the settings and what has been passed here
  vc.py config [set KEY VALUE] show or change settings (add --global for all projects)
  vc.py topics                 list what has been covered, across all projects
  vc.py concepts [add ...]     this project's concept list (from a scan): known, learning or gate
  vc.py review "<topic>"       reopen a passed topic's lesson and quiz, with no gate

State in the user's project, in .vibe-check/:
  pending.json   the quiz in progress. While it exists, gate.py blocks edits.
  practice.json  a no-gate lesson in progress. The gate ignores it.
  concepts.json  the concepts found in this project and where each stands.
  passed.json    topics already passed, so they are not quizzed again.
  config.json    this project's settings.
  quizzes/       quiz content (<topic>.json) and the built pages (<topic>.html).

State for the user, in ~/.vibe-check/ (or $VIBE_CHECK_HOME):
  config.json    default settings for every project.
  history.jsonl  one line per Vibe Check: what was taught, asked and answered.
  reviews/       no-gate copies of passed quizzes.
  log.html       the Learning Log page.

Exit codes: 0 = done, 1 = could not do it (wrong code, quiz already pending, ...).
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

STATE_DIR = ".vibe-check"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, which look alike
XP_PASS, XP_FIRST_TRY, XP_RETRY, XP_PER_LEVEL = 50, 20, 10, 250

# setting: (default, allowed values or a (low, high) range, what it does)
SETTINGS = {
    "style": ("concepts", ["concepts", "hands_on"], "concepts = understand it well enough to explain it; hands_on = also write a small piece yourself"),
    "look": ("classic", ["arcade", "classic", "plain"], "classic = animated cards; arcade = custom interactive lesson, most tokens and slowest; plain = one simple page, fewest tokens"),
    "tracks": (["domain", "architecture", "code"], "tracks", "which kinds of concept get lessons and gates: domain (what the system does in business terms), architecture (how the pieces fit), code (language, libraries, patterns)"),
    "level": ("beginner", ["beginner", "intermediate", "advanced"], "how much the lesson assumes and how hard the questions are"),
    "zoom": ("how", ["what", "how", "weeds"], "starting depth: what = what it does and why; how = the moving parts; weeds = the actual lines and edge cases"),
    "lesson": (True, [True, False], "show the Learn part before the Check"),
    "lesson_cards": (4, (2, 8), "how many lesson scenes"),
    "questions": (3, (1, 10), "how many questions"),
    "pass_bar": ("all", None, '"all", or how many questions must be right, for example 2'),
    "trigger": ("new_concepts", ["new_concepts", "big_concepts_only", "manual"], "when a Vibe Check starts"),
}
SCENE_TYPES = {"story", "steps", "playground", "card", "custom", "sort", "match", "flow", "slider", "build", "compare"}
QUESTION_TYPES = {"choice", "predict", "explain", "order", "expect", "fill", "bug", "match"}
TRACKS = ["domain", "architecture", "code"]
CONCEPT_GROUPS = ["big_picture", "tools", "techniques"]
CONCEPT_STATUSES = ["learning", "known", "gate"]


# ---------- where things live ----------

def project_root():
    """The user's project folder. This has to be the same folder gate.py watches.

    Claude Code tells hooks the project folder (CLAUDE_PROJECT_DIR) but doesn't
    always tell shell commands, so fall back to the nearest folder that already
    has a .vibe-check/, then to the current folder.
    """
    named = os.environ.get("CLAUDE_PROJECT_DIR")
    if named:
        return Path(named)
    here = Path.cwd()
    for folder in (here, *here.parents):
        # ~/.vibe-check/ holds the user's history and defaults, not a project's quiz state.
        if folder != Path.home() and (folder / STATE_DIR).is_dir():
            return folder
    return here


def user_home():
    """The user's own Vibe Check folder (history, default settings, Learning Log)."""
    return Path(os.environ.get("VIBE_CHECK_HOME") or Path.home() / STATE_DIR)


# ---------- small helpers ----------

def slugify(topic):
    """'pandas DataFrames' -> 'pandas-dataframes': safe as a file name and a lookup key."""
    return re.sub(r"[\W_]+", "-", topic.lower()).strip("-")


def new_pass_code():
    """A random code such as K7QM-2XPA."""
    chars = "".join(secrets.choice(CODE_LETTERS) for _ in range(8))
    return f"{chars[:4]}-{chars[4:]}"


def fingerprint(code):
    """One-way fingerprint (SHA-256 hash) of a pass code.

    Case, spaces and dashes are ignored, so 'k7qm 2xpa' matches 'K7QM-2XPA'.
    """
    tidy = re.sub(r"[\s-]+", "", code).upper()
    return hashlib.sha256(tidy.encode()).hexdigest()


def read_json(path):
    """The dict stored in a JSON file, or {} if it is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fail(message):
    print(message, file=sys.stderr)
    return 1


def open_in_browser(path, wanted):
    if wanted and not os.environ.get("VIBE_CHECK_NO_OPEN"):
        try:
            return webbrowser.open(path.resolve().as_uri())
        except Exception:
            return False
    return False


# ---------- settings ----------

def load_config(state):
    """Defaults, then the user's defaults, then this project's settings (project wins)."""
    config = {key: spec[0] for key, spec in SETTINGS.items()}
    for source in (user_home() / "config.json", state / "config.json"):
        for key, value in read_json(source).items():
            if key in SETTINGS:
                config[key] = value
    return config


def is_set_up(state):
    return (state / "config.json").exists() or (user_home() / "config.json").exists()


def parse_setting(key, text):
    """Turn what was typed into a valid value for a setting, or raise ValueError."""
    if key not in SETTINGS:
        raise ValueError(f'There is no setting called "{key}". Settings: {", ".join(SETTINGS)}.')
    _, allowed, _ = SETTINGS[key]
    word = text.strip().lower()
    if key == "tracks":
        chosen = [t for t in re.split(r"[\s,]+", word) if t]
        if not chosen or any(t not in TRACKS for t in chosen):
            raise ValueError(f'tracks is one or more of: {", ".join(TRACKS)} (for example: domain,architecture).')
        return [t for t in TRACKS if t in chosen]
    if key == "pass_bar":
        if word == "all":
            return "all"
        if word.isdigit() and int(word) >= 1:
            return int(word)
        raise ValueError('pass_bar is "all" or a whole number of 1 or more.')
    if isinstance(allowed, tuple):
        low, high = allowed
        if word.isdigit() and low <= int(word) <= high:
            return int(word)
        raise ValueError(f"{key} is a whole number from {low} to {high}.")
    if True in allowed:
        if word in ("true", "on", "yes"):
            return True
        if word in ("false", "off", "no"):
            return False
        raise ValueError(f"{key} is on or off.")
    if word in allowed:
        return word
    raise ValueError(f'{key} is one of: {", ".join(allowed)}.')


def config_command(state, args):
    if not args.action:
        config = load_config(state)
        print("Settings (this project, after defaults):")
        for key, (_, _, about) in SETTINGS.items():
            print(f"  {key} = {json.dumps(config[key])}    {about}")
        if not is_set_up(state):
            print("Not set up yet: these are the built-in defaults. Ask the user the first-run questions.")
        return 0
    if args.action != "set" or len(args.pair) < 2:
        return fail('Use: config    or    config set KEY VALUE [--global]')
    key, text = args.pair[0], " ".join(args.pair[1:])
    try:
        value = parse_setting(key, text)
    except ValueError as problem:
        return fail(str(problem))
    target = (user_home() if args.everywhere else state) / "config.json"
    saved = read_json(target)
    saved[key] = value
    write_json(target, saved)
    where = "for every project" if args.everywhere else "for this project"
    print(f"Saved {where}: {key} = {json.dumps(value)}")
    return 0


# ---------- quiz content ----------

def check_scene(scene, where, problems, allow_custom=True):
    if not isinstance(scene, dict) or scene.get("type") not in SCENE_TYPES:
        problems.append(f'{where}: "type" must be one of {", ".join(sorted(SCENE_TYPES))}.')
        return
    kind = scene["type"]
    if not isinstance(scene.get("title"), str) or not scene["title"].strip():
        problems.append(f'{where}: needs a "title".')
    if kind == "story" and not (isinstance(scene.get("messages"), list) and scene["messages"]):
        problems.append(f'{where}: a story needs "messages", a list of short lines.')
    if kind == "steps":
        steps = scene.get("steps")
        if not (isinstance(steps, list) and steps and all(isinstance(s, dict) and s.get("text") for s in steps)):
            problems.append(f'{where}: "steps" must be a list, each with "text".')
    if kind == "card" and not scene.get("body"):
        problems.append(f'{where}: a card needs a "body".')
    if kind == "playground":
        controls, results = scene.get("controls"), scene.get("results")
        if not (isinstance(controls, list) and controls and isinstance(results, dict)):
            problems.append(f'{where}: a playground needs "controls" and "results".')
        else:
            keys = [""]
            for control in controls:
                options = control.get("options") if isinstance(control, dict) else None
                if not (isinstance(options, list) and len(options) >= 2):
                    problems.append(f'{where}: each control needs "name" and 2 or more "options".')
                    return
                keys = [f"{k}|{o}".strip("|") for k in keys for o in options]
            missing = [k for k in keys if k not in results]
            if missing:
                problems.append(f'{where}: "results" is missing these combinations: {", ".join(missing[:6])}.')
    listed = lambda value, least=1: isinstance(value, list) and len(value) >= least
    if kind == "sort":
        items = scene.get("items")
        if not (listed(items, 2) and all(isinstance(x, dict) and x.get("label") and x.get("group") for x in items)):
            problems.append(f'{where}: a sort scene needs "items", each with a "label" and the "group" it belongs to.')
        elif len({x["group"] for x in items}) < 2:
            problems.append(f"{where}: a sort scene needs at least 2 different groups.")
        elif scene.get("groups") and {x["group"] for x in items} - set(scene["groups"]):
            problems.append(f'{where}: every item\'s "group" must appear in "groups".')
    if kind == "match":
        pairs = scene.get("pairs")
        if not (listed(pairs, 2) and all(isinstance(p, dict) and p.get("left") and p.get("right") for p in pairs)):
            problems.append(f'{where}: a match scene needs 2 or more "pairs", each with "left" and "right".')
    if kind == "flow":
        nodes, steps = scene.get("nodes"), scene.get("steps")
        if not (listed(nodes, 2) and all(isinstance(n, dict) and n.get("label") for n in nodes)):
            problems.append(f'{where}: a flow scene needs 2 or more "nodes", each with a "label".')
        elif not (listed(steps) and all(isinstance(s, dict) and s.get("text") and isinstance(s.get("at"), int)
                                        and 0 <= s["at"] < len(nodes) for s in steps)):
            problems.append(f'{where}: each flow step needs "text" and "at", the position of its node counting from 0.')
    if kind == "slider":
        positions = scene.get("positions")
        if not (listed(positions, 2) and all(isinstance(p, dict) and "label" in p and p.get("say") for p in positions)):
            problems.append(f'{where}: a slider scene needs 2 or more "positions", each with a "label" and a "say".')
    if kind == "build":
        if not (listed(scene.get("pieces"), 2) and all(isinstance(t, str) and t for t in scene["pieces"])):
            problems.append(f'{where}: a build scene needs "pieces", the parts of the line in the correct order.')
    if kind == "compare":
        for side in ("before", "after"):
            table = scene.get(side)
            if not (isinstance(table, dict) and listed(table.get("rows"))):
                problems.append(f'{where}: a compare scene needs "{side}" with "rows".')
    if kind == "custom":
        if not allow_custom:
            problems.append(f"{where}: a fallback can't itself be a custom scene.")
            return
        if not isinstance(scene.get("html"), str):
            problems.append(f'{where}: a custom scene needs "html".')
        if "fallback" not in scene:
            problems.append(f'{where}: a custom scene needs a "fallback" scene for the other looks.')
        else:
            check_scene(scene["fallback"], where + " fallback", problems, allow_custom=False)


def check_content(content):
    """A list of problems with the quiz content. Empty means it is good to build."""
    problems = []
    lesson = content.get("lesson", [])
    if not isinstance(lesson, list):
        problems.append('"lesson" must be a list of scenes.')
        lesson = []
    for number, scene in enumerate(lesson, 1):
        check_scene(scene, f"lesson scene {number}", problems)
    questions = content.get("questions")
    if not (isinstance(questions, list) and questions):
        problems.append('"questions" must be a list with at least one question.')
        questions = []
    if len(questions) > 10:
        problems.append("There can be at most 10 questions.")
    for number, question in enumerate(questions, 1):
        where = f"question {number}"
        if not isinstance(question, dict) or question.get("type") not in QUESTION_TYPES:
            problems.append(f'{where}: "type" must be one of {", ".join(sorted(QUESTION_TYPES))}.')
            continue
        if not question.get("prompt") or not question.get("why"):
            problems.append(f'{where}: needs a "prompt" and a "why" (the explanation shown after answering).')
        if question["type"] == "order":
            items = question.get("items")
            if not (isinstance(items, list) and 2 <= len(items) <= 9):
                problems.append(f'{where}: "items" must list 2 to 9 steps, in the correct order.')
        elif question["type"] == "match":
            pairs = question.get("pairs")
            if not (isinstance(pairs, list) and 2 <= len(pairs) <= 9 and all(isinstance(p, dict) and p.get("left") and p.get("right") for p in pairs)):
                problems.append(f'{where}: "pairs" must list 2 to 9 pairs, each with "left" and "right".')
        elif question["type"] == "bug":
            lines, answer = question.get("lines"), question.get("answer")
            if not (isinstance(lines, list) and 2 <= len(lines) <= 9):
                problems.append(f'{where}: "lines" must list 2 to 9 lines of code.')
            elif not (isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(lines)):
                problems.append(f'{where}: "answer" must be the position of the line with the bug, counting from 0.')
        else:
            if question["type"] == "fill" and "___" not in str(question.get("code", "")):
                problems.append(f'{where}: a fill question needs "code" with ___ (three underscores) where the blank goes.')
            options, answer = question.get("options"), question.get("answer")
            if not (isinstance(options, list) and 2 <= len(options) <= 9):
                problems.append(f'{where}: "options" must list 2 to 9 choices.')
            elif not (isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(options)):
                problems.append(f'{where}: "answer" must be the position of the right option, counting from 0.')
    return problems


def load_scene_files(content, folder):
    """A custom scene may keep its code in files next to the content: "html_file", "js_file".

    Files are easier to write than code squeezed into a JSON string.
    """
    for scene in content.get("lesson") or []:
        if not isinstance(scene, dict) or scene.get("type") != "custom":
            continue
        for key in ("html", "js"):
            name = scene.pop(key + "_file", None)
            if name:
                path = (folder / str(name)).resolve()
                if not path.is_relative_to(folder.resolve()):
                    raise ValueError(f"{name} must be inside {folder}")
                scene[key] = path.read_text(encoding="utf-8")


def check_scene_scripts(content):
    """Catch a custom scene whose JavaScript won't even parse. Needs node; skipped without it."""
    node = shutil.which("node")
    problems = []
    for number, scene in enumerate(content.get("lesson") or [], 1):
        if not (node and isinstance(scene, dict) and scene.get("type") == "custom" and isinstance(scene.get("js"), str)):
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as scratch:
            scratch.write("(function(vc){\n" + scene["js"] + "\n})")
        try:
            done = subprocess.run([node, "--check", scratch.name], capture_output=True, text=True, timeout=20)
            if done.returncode != 0:
                detail = " ".join(done.stderr.strip().splitlines()[1:5]).strip()
                problems.append(f"lesson scene {number}: the custom scene's JavaScript has a syntax error: {detail}")
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            os.unlink(scratch.name)
    return problems


def scenes_for(look, lesson):
    """Custom scenes only run in the arcade look; the other looks get their fallback."""
    if look == "arcade":
        return lesson
    return [scene["fallback"] if scene.get("type") == "custom" else scene for scene in lesson]


def stamp(look, page_data):
    """Fill a template: the shared core script and the quiz data go into the page."""
    template = (TEMPLATES / ("plain.html" if look == "plain" else "game.html")).read_text(encoding="utf-8")
    core = (TEMPLATES / "core.js").read_text(encoding="utf-8")
    # "<" is written as < so nothing in the data can end the script block early.
    data = json.dumps(page_data, ensure_ascii=False).replace("<", "\\u003c")
    before, _, after = template.partition("__VC_DATA__")
    return before.replace("/*__VC_CORE__*/", core) + data + after.replace("/*__VC_CORE__*/", core)


# ---------- history, XP and the Learning Log ----------

def read_history():
    entries = []
    try:
        lines = (user_home() / "history.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def entry_xp(entry):
    if entry.get("result") != "pass":
        return 0
    questions = entry.get("questions") or []
    return XP_PASS + sum(XP_FIRST_TRY if q.get("tries", 1) <= 1 else XP_RETRY for q in questions)


def stats(entries):
    """XP, level and streak. Always worked out from the history, never stored."""
    xp = sum(entry_xp(e) for e in entries)
    days = {e.get("date") for e in entries if e.get("result") == "pass"}
    day, streak = date.today(), 0
    if day.isoformat() not in days:
        day -= timedelta(days=1)  # a streak survives until the end of the next day
    while day.isoformat() in days:
        streak += 1
        day -= timedelta(days=1)
    return {
        "xp": xp, "level": xp // XP_PER_LEVEL + 1, "streak": streak,
        "passed": len({e.get("slug") for e in entries if e.get("result") == "pass"}),
        "passed_today": date.today().isoformat() in days,
    }


def parse_trail(tail, questions):
    """'10-y-1' -> what was answered on each try, per question."""
    parts = tail.split("-") if tail else []
    trails = []
    for number, question in enumerate(questions):
        marks = parts[number] if number < len(parts) else ""
        marks = "" if marks == "x" else marks.replace("d", "")
        if question.get("type") in ("order", "match"):
            trails.append(["right" if m == "y" else "wrong" for m in marks if m in "yn"])
        else:
            options = question.get("lines") if question.get("type") == "bug" else question.get("options", [])
            trails.append([options[int(m)] for m in marks if m.isdigit() and int(m) < len(options)])
    return trails


def find_disputes(content, tail):
    """Questions where the user said "that's not what it should do": possible bugs, not misses."""
    questions = (content or {}).get("questions") or []
    parts = tail.split("-") if tail else []
    found = []
    for number, (question, answers) in enumerate(zip(questions, parse_trail(tail, questions))):
        if number < len(parts) and "d" in parts[number] and question.get("type") not in ("order", "match"):
            options = question.get("lines") if question.get("type") == "bug" else question.get("options", [])
            answer = question.get("answer")
            found.append({
                "question": number + 1, "prompt": question.get("prompt"),
                "expected": answers[-1] if answers else None,
                "code_does": options[answer] if isinstance(answer, int) and answer < len(options) else None,
                "source": question.get("source"),
            })
    return found


def add_history(state, pending, result, content=None, tail=""):
    questions = []
    disputes = find_disputes(content, tail)
    disputed = {d["question"] for d in disputes}
    if content:
        for number, (question, tries) in enumerate(zip(content["questions"], parse_trail(tail, content["questions"])), 1):
            argued = number in disputed
            questions.append({
                "type": question["type"], "prompt": question["prompt"],
                "options": question.get("options") or question.get("items") or question.get("lines") or question.get("pairs"),
                "answer": question.get("answer"), "why": question["why"], "source": question.get("source"),
                "answers": tries, "tries": 1 if argued else max(1, len(tries)),
                "missed": len(tries) > 1 and not argued, "disputed": argued,
            })
    now = datetime.now()
    entry = {
        "date": now.date().isoformat(), "time": now.strftime("%H:%M"),
        "project": str(state.parent), "topic": pending.get("topic"), "slug": pending.get("slug"),
        "result": result, "kind": pending.get("kind", "lesson"), "gated": pending.get("gated", True),
        "look": pending.get("look"), "level": pending.get("level"), "zoom": pending.get("zoom"),
        "track": pending.get("track", "code"), "possible_issues": disputes,
        "badge": (content or {}).get("badge"),
        "lesson": scenes_for("plain", content.get("lesson", [])) if content else [],
        "questions": questions, "answers_recorded": bool(tail),
        "quiz_file": str(state.parent / pending["quiz"]) if pending.get("quiz") else None,
        "review_file": pending.get("review_file"),
    }
    home = user_home()
    home.mkdir(parents=True, exist_ok=True)
    with (home / "history.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    write_log_page()
    return entry


def write_log_page():
    """~/.vibe-check/log.html: everything covered, newest first, with links to review."""
    entries = read_history()
    totals = stats(entries)
    e = html.escape
    rows = []
    for entry in reversed(entries):
        passed = entry.get("result") == "pass"
        questions = entry.get("questions") or []
        missed = sum(1 for q in questions if q.get("missed"))
        detail = f"{len(questions) - missed} of {len(questions)} first try" if passed and questions else ""
        issues = len(entry.get("possible_issues") or [])
        if issues:
            detail += f", {issues} possible {'issue' if issues == 1 else 'issues'} found"
        review = ""
        if passed and entry.get("review_file") and Path(entry["review_file"]).exists():
            review = f'<a href="{e(Path(entry["review_file"]).as_uri())}">Review</a>'
        rows.append(
            f"<tr><td>{e(str(entry.get('date', '')))}</td>"
            f"<td>{e(str(entry.get('badge') or '')) if passed else ''} {e(str(entry.get('topic', '')))}</td>"
            f"<td>{e(str(entry.get('track') or 'code'))}</td>"
            f"<td>{'Passed' if passed else 'Skipped'}</td><td>{e(detail)}</td>"
            f"<td>{entry_xp(entry) or ''}</td><td>{e(Path(str(entry.get('project', ''))).name)}</td><td>{review}</td></tr>"
        )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vibe Check: Learning Log</title>
<style>
:root{{color-scheme:light dark}}
body{{max-width:56rem;margin:0 auto;padding:1.5rem 1rem 4rem;font:1rem/1.55 system-ui,sans-serif}}
h1{{font-size:1.6rem;margin:0 0 .25rem}}
.totals{{display:flex;gap:2rem;flex-wrap:wrap;margin:1rem 0 1.5rem}}
.totals b{{display:block;font-size:1.6rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:.4rem 1rem .4rem 0;border-bottom:1px solid color-mix(in srgb,currentColor 25%,transparent);vertical-align:top}}
.wide{{overflow-x:auto}}
</style></head><body>
<h1>Learning Log</h1>
<p>Everything you have covered with Vibe Check, newest first.</p>
<div class="totals">
  <div><b>{totals['passed']}</b>topics passed</div>
  <div><b>Level {totals['level']}</b>{totals['xp']} XP</div>
  <div><b>{totals['streak']}</b>day streak</div>
  <div><b>{sum(len(x.get('possible_issues') or []) for x in entries)}</b>possible issues found</div>
</div>
<div class="wide"><table>
<tr><th>Date</th><th>Topic</th><th>Track</th><th>Result</th><th>Questions</th><th>XP</th><th>Project</th><th></th></tr>
{''.join(rows) or '<tr><td colspan="8">Nothing yet. Your first Vibe Check will show up here.</td></tr>'}
</table></div>
</body></html>
"""
    path = user_home() / "log.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


# ---------- commands ----------

def in_progress(state):
    """(file, True) for a gated quiz, (file, False) for a no-gate lesson, or (None, None)."""
    if (state / "pending.json").exists():
        return state / "pending.json", True
    if (state / "practice.json").exists():
        return state / "practice.json", False
    return None, None


def start(state, topic, gated=True, track=None):
    pending_file = state / "pending.json"
    slug = slugify(topic)
    if not slug:
        return fail("The topic needs at least one letter or number.")
    config = load_config(state)
    track = track or read_json(state / "concepts.json").get(slug, {}).get("track") or "code"
    if gated and track not in config["tracks"]:
        print(f'"{topic}" is a {track}-track concept, and that track is switched off in the settings.')
        print("No Vibe Check needed. Gate: OPEN.")
        return 0
    if pending_file.exists():
        current = read_json(pending_file).get("topic", "another topic")
        return fail(
            f'A quiz on "{current}" is already pending. '
            "It has to be passed (unlock <code>) or skipped (skip) first."
        )
    if gated and slug in read_json(state / "passed.json"):
        print(f'Already passed: "{topic}". No quiz needed. Gate: OPEN.')
        return 0

    quizzes = Path(STATE_DIR) / "quizzes"
    write_json(pending_file if gated else state / "practice.json", {
        "topic": topic, "slug": slug, "track": track,
        "content": str(quizzes / f"{slug}.json"), "quiz": str(quizzes / f"{slug}.html"),
        "started": date.today().isoformat(),
    })
    (state / "quizzes").mkdir(exist_ok=True)
    if gated:
        print(f'Vibe Check started: "{topic}" ({track} track)')
        print(f"Gate: CLOSED. Edits outside {STATE_DIR}/ are blocked until the quiz is passed or skipped.")
        if read_json(state / "concepts.json").get(slug, {}).get("status") == "learning":
            print("Note: this concept is on the learning list (already in the code), which doesn't gate by default.")
    else:
        print(f'Lesson started with no gate: "{topic}"')
        print("Gate: OPEN. Nothing is blocked; the code at the end only records it in the Learning Log.")
    print(f"Settings: {json.dumps(config)}")
    if not is_set_up(state):
        print("First run here: ask the user the setup questions and save them with config set, before writing the quiz.")
    print(f"Write the quiz content (JSON) to: {state.parent / quizzes / (slug + '.json')}")
    if config["look"] == "arcade":
        print(f"Custom scene files go next to it: {slug}.scene.html and {slug}.scene.js")
    print("Then run this same script with: build")
    return 0


def build(state, open_page=True):
    pending_file, gated = in_progress(state)
    if not pending_file:
        return fail("No quiz is pending. Run start \"<topic>\" first.")
    pending = read_json(pending_file)
    if not pending.get("content") or not pending.get("slug"):
        return fail("pending.json is damaged. Run skip to clear it, then start again.")
    content_file = state.parent / pending["content"]
    if not content_file.exists():
        return fail(f"The quiz content isn't written yet. Write it to: {content_file}")
    try:
        content = json.loads(content_file.read_text(encoding="utf-8"))
    except ValueError as problem:
        return fail(f"The quiz content isn't valid JSON ({problem}). Fix {content_file} and run build again.")
    if not isinstance(content, dict):
        return fail("The quiz content must be a JSON object with \"lesson\" and \"questions\".")
    try:
        load_scene_files(content, content_file.parent)
    except (OSError, ValueError) as problem:
        return fail(f"A custom scene file could not be read: {problem}")
    problems = check_content(content) + check_scene_scripts(content)
    if problems:
        return fail("The quiz content needs fixing, then run build again:\n- " + "\n- ".join(problems))

    config = load_config(state)
    look = config["look"]
    lesson = scenes_for(look, content.get("lesson", [])) if config["lesson"] else []
    code = new_pass_code()
    zoom = content.get("zoom") if content.get("zoom") in SETTINGS["zoom"][1] else config["zoom"]
    page_data = {
        "topic": pending["topic"], "look": look, "level": config["level"], "style": config["style"],
        "gate": gated, "zoom": zoom, "track": pending.get("track", "code"),
        "pass_bar": config["pass_bar"], "badge": content.get("badge"),
        "lesson": lesson, "questions": content["questions"], "stats": stats(read_history()),
    }
    quiz_file = state.parent / pending["quiz"]
    quiz_file.parent.mkdir(parents=True, exist_ok=True)
    # The quiz page hides the pass code in base64: a disguise, not a lock.
    quiz_file.write_text(stamp(look, {**page_data, "code": base64.b64encode(code.encode()).decode()}), encoding="utf-8")
    # A second copy with no pass code, for reviewing later with no gate.
    project_tag = hashlib.sha256(str(state.parent).encode()).hexdigest()[:8]
    review_file = user_home() / "reviews" / f"{pending['slug']}-{project_tag}.html"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(stamp(look, {**page_data, "review": True}), encoding="utf-8")

    pending.update({"code_hash": fingerprint(code), "look": look, "level": config["level"], "zoom": zoom,
                    "review_file": str(review_file)})
    write_json(pending_file, pending)
    opened = open_in_browser(quiz_file, open_page)
    print(f'Quiz page built ({look} look): {quiz_file}')
    print("Opened in the browser." if opened else "It did not open by itself: give the user that path to open.")
    if gated:
        print('Tell the user in one line: "Vibe Check: pass the quiz and paste the code here." Then stop and wait.')
    else:
        print("No gate: carry on working. If the user pastes the code from the end, run unlock to log it.")
    return 0


def unlock(state, pasted):
    pending_file, gated = in_progress(state)
    if not pending_file:
        return fail("No quiz is pending, so there is nothing to unlock. Gate: OPEN.")
    quiz = read_json(pending_file)
    if not quiz.get("slug"):
        return fail("pending.json is damaged, so the code can't be checked. Run skip to clear it, then start again.")
    if not quiz.get("code_hash"):
        return fail("The quiz page hasn't been built yet, so there is no code to check. Write the content and run build.")
    # The page's Copy button gives "<pass code>.<answer trail>". The trail is optional.
    code, _, tail = pasted.strip().partition(".")
    if fingerprint(code) != quiz["code_hash"]:
        return fail(
            f"That pass code doesn't match. Gate: {'still CLOSED' if gated else 'OPEN (this lesson has no gate)'}. "
            "Ask the user to copy the code shown at the end of the quiz."
        )

    content = read_json(state.parent / quiz.get("content", ""))
    tail = re.sub(r"[^0-9a-z-]", "", tail.lower())
    topic = quiz.get("topic", quiz["slug"])
    passed_file = state / "passed.json"
    passed = read_json(passed_file)
    today = date.today().isoformat()
    placement = bool(content.get("placement"))
    if placement:
        lines = sort_placement(state, content, tail, passed, today)
    else:
        passed[quiz["slug"]] = {"topic": topic, "passed": today}
    write_json(passed_file, passed)
    pending_file.unlink()
    print(f'Passed: "{topic}". Gate: OPEN.' + (" Edits are allowed again." if gated else ""))
    if placement:
        print("\n".join(lines))
    try:
        entry = add_history(state, {**quiz, "gated": gated, "kind": "placement" if placement else "lesson"},
                            "pass", content if content.get("questions") else None, tail)
        totals = stats(read_history())
        print(f"+{entry_xp(entry)} XP. Level {totals['level']}, {totals['xp']} XP, {totals['streak']}-day streak.")
        if not tail:
            print("(Only the short code was pasted, so the answers were not recorded.)")
        for issue in entry.get("possible_issues") or []:
            print(f"POSSIBLE ISSUE (question {issue['question']}): {issue['prompt']}")
            print(f"  The user expected: {issue['expected']}")
            print(f"  The code does:     {issue['code_does']}" + (f"   [{issue['source']}]" if issue.get("source") else ""))
        if entry.get("possible_issues"):
            print("Check the code against what the user expected and report back before building on it. They may be right.")
    except OSError as problem:  # the gate must open even if the log can't be written
        print(f"(The Learning Log could not be updated: {problem})")
    return 0


def sort_placement(state, content, tail, passed, today):
    """After a placement quiz: concepts answered right first time are known, the rest go on the learning list."""
    questions = content.get("questions") or []
    tries = parse_trail(tail, questions)
    by_concept = {}
    for question, answers in zip(questions, tries):
        name = question.get("concept")
        if name:
            by_concept.setdefault(name, []).append(len(answers) == 1)
    if not tail:
        return ["Only the short code was pasted, so nothing could be marked as known. Ask for the full copied code next time."]
    concepts = read_json(state / "concepts.json")
    known, learning = [], []
    for name, firsts in by_concept.items():
        slug = slugify(name)
        entry = concepts.setdefault(slug, {"topic": name})
        if all(firsts):
            entry["status"] = "known"
            passed[slug] = {"topic": name, "passed": today, "via": "placement"}
            known.append(name)
        else:
            entry["status"] = entry.get("status") if entry.get("status") == "gate" else "learning"
            learning.append(name)
    write_json(state / "concepts.json", concepts)
    return [f"Already known (no lesson needed): {', '.join(known) or 'none'}",
            f"On the learning list: {', '.join(learning) or 'none'}"]


def skip(state):
    pending_file, gated = in_progress(state)
    if not pending_file:
        print("No quiz is pending, so there is nothing to skip. Gate: OPEN.")
        return 0
    quiz = read_json(pending_file)
    topic = quiz.get("topic", "the pending topic")
    pending_file.unlink()
    if not gated:
        print(f'Dropped the no-gate lesson on "{topic}". Gate: OPEN.')
        return 0
    try:
        add_history(state, quiz, "skip")
    except OSError:
        pass
    print(f'Skipped: "{topic}". Gate: OPEN.')
    print("It is not marked as passed, so it will be quizzed again next time it comes up.")
    return 0


def concepts_command(state, args):
    """The project's concept list, filled in by a scan. Statuses: learning, known, gate."""
    path = state / "concepts.json"
    concepts = read_json(path)
    if args.action == "add":
        topic = " ".join(args.topic).strip()
        slug = slugify(topic)
        if not slug:
            return fail('Use: concepts add "<topic>" [--group big_picture|tools|techniques] [--status learning|known|gate] [--weight N]')
        entry = concepts.setdefault(slug, {"topic": topic, "status": "learning"})
        entry["topic"] = topic
        if args.group:
            entry["group"] = args.group
        if args.track:
            entry["track"] = args.track
        if args.status:
            entry["status"] = args.status
        if args.weight is not None:
            entry["weight"] = args.weight
        write_json(path, concepts)
        if entry["status"] == "known":
            passed = read_json(state / "passed.json")
            passed.setdefault(slug, {"topic": topic, "passed": date.today().isoformat(), "via": "marked known"})
            write_json(state / "passed.json", passed)
        print(f'Concept saved: "{topic}" ({entry.get("group", "no group")}, {entry.get("track", "code")} track, {entry["status"]})')
        return 0
    if args.action:
        return fail('Use: concepts    or    concepts add "<topic>" [--group ...] [--status ...] [--weight N]')
    if not concepts:
        print("No concept list yet. A scan of the project creates one.")
        return 0
    about = {"learning": "on the learning list, never gates", "known": "known, no lesson needed", "gate": "gates when it comes up"}
    for group in CONCEPT_GROUPS + [None]:
        members = [c for c in concepts.values() if c.get("group") == group or (group is None and c.get("group") not in CONCEPT_GROUPS)]
        if not members:
            continue
        print({"big_picture": "Big picture", "tools": "Tools", "techniques": "Techniques", None: "Other"}[group] + ":")
        for concept in sorted(members, key=lambda c: -(c.get("weight") or 0)):
            print(f"  - {concept.get('topic')} [{concept.get('track', 'code')}]: {about.get(concept.get('status'), concept.get('status'))}")
    return 0


def issues_command(state):
    """Possible bugs the user flagged in this project: places where they expected the code to do something else."""
    found = [(entry, issue) for entry in read_history() if entry.get("project") == str(state.parent)
             for issue in entry.get("possible_issues") or []]
    if not found:
        print("No possible issues flagged in this project.")
        return 0
    print(f"Possible issues flagged in this project ({len(found)}):")
    for entry, issue in found:
        print(f"- {entry.get('date')}, {entry.get('topic')}: {issue['prompt']}")
        print(f"    expected: {issue['expected']}")
        print(f"    code does: {issue['code_does']}" + (f"   [{issue['source']}]" if issue.get("source") else ""))
    return 0


def status(state):
    print(f"Project: {state.parent}")
    pending_file = state / "pending.json"
    if (state / "practice.json").exists() and not pending_file.exists():
        print(f'No-gate lesson in progress: "{read_json(state / "practice.json").get("topic", "?")}".')
    if pending_file.exists():
        quiz = read_json(pending_file)
        built = "page built" if quiz.get("code_hash") else "content not built yet"
        print(f'Gate: CLOSED. Quiz pending on "{quiz.get("topic", "?")}" (started {quiz.get("started", "?")}, {built}).')
        if quiz.get("quiz"):
            print(f"Quiz file: {state.parent / quiz['quiz']}")
    else:
        print("Gate: OPEN. No quiz pending.")
    passed = read_json(state / "passed.json")
    if passed:
        print(f"Passed here ({len(passed)}):")
        for entry in passed.values():
            print(f"  - {entry.get('topic', '?')} ({entry.get('passed', '?')})")
    else:
        print("Passed here: none yet.")
    concepts = read_json(state / "concepts.json")
    print(f"Concept list: {len(concepts)} concepts (run concepts to see them)." if concepts else "Concept list: none yet.")
    totals = stats(read_history())
    print(f"Overall: level {totals['level']}, {totals['xp']} XP, {totals['streak']}-day streak, {totals['passed']} topics passed.")
    print(f"Settings: {json.dumps(load_config(state))}" + ("" if is_set_up(state) else " (defaults, not set up yet)"))
    return 0


def topics(state):
    entries = read_history()
    if not entries:
        print("Nothing covered yet.")
        return 0
    totals = stats(entries)
    print(f"Level {totals['level']}, {totals['xp']} XP, {totals['streak']}-day streak, {totals['passed']} topics passed.")
    for entry in reversed(entries):
        passed = entry.get("result") == "pass"
        questions = entry.get("questions") or []
        missed = sum(1 for q in questions if q.get("missed"))
        detail = f", {len(questions) - missed} of {len(questions)} first try" if passed and questions else ""
        here = "" if entry.get("project") == str(state.parent) else f" [{Path(str(entry.get('project', ''))).name}]"
        print(f"  {entry.get('date')}  {'passed ' if passed else 'skipped'}  {entry.get('topic')}{detail}{here}")
    print(f"Learning Log page: {write_log_page()}")
    return 0


def review(state, topic, open_page=True):
    slug = slugify(topic)
    matches = [e for e in read_history() if e.get("result") == "pass" and e.get("review_file")
               and (e.get("slug") == slug or slug in str(e.get("slug", "")))]
    matches = [e for e in matches if Path(e["review_file"]).exists()]
    if not matches:
        return fail(f'No passed topic matching "{topic}" has a review page. Run topics to see what has been covered.')
    here = [e for e in matches if e.get("project") == str(state.parent)]
    entry = (here or matches)[-1]
    opened = open_in_browser(Path(entry["review_file"]), open_page)
    print(f'Review of "{entry.get("topic")}" (no gate, nothing to paste): {entry["review_file"]}')
    print("Opened in the browser." if opened else "It did not open by itself: give the user that path to open.")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="vc.py", description="Vibe Check: close and open the quiz gate.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    start_args = commands.add_parser("start", help="begin a Vibe Check on a topic (closes the gate)")
    start_args.add_argument("topic", nargs="+", help="the concept, for example: pandas groupby")
    start_args.add_argument("--no-gate", action="store_true", help="a lesson that doesn't block edits")
    start_args.add_argument("--track", choices=TRACKS, help="what kind of concept this is (default: code)")
    build_args = commands.add_parser("build", help="build the quiz page from the content and open it")
    build_args.add_argument("--no-open", action="store_true", help="don't open the browser")
    unlock_args = commands.add_parser("unlock", help="check a pass code (opens the gate if it matches)")
    unlock_args.add_argument("code", nargs="+", help="the code copied at the end of the quiz")
    commands.add_parser("skip", help="drop the pending quiz without passing it (opens the gate)")
    commands.add_parser("status", help="show the gate, settings and passed topics")
    config_args = commands.add_parser("config", help="show settings, or: config set KEY VALUE")
    config_args.add_argument("action", nargs="?", help="set")
    config_args.add_argument("pair", nargs="*", help="KEY VALUE")
    config_args.add_argument("--global", dest="everywhere", action="store_true", help="save as the default for every project")
    commands.add_parser("topics", help="list what has been covered")
    commands.add_parser("issues", help="possible bugs the user flagged during quizzes in this project")
    concept_args = commands.add_parser("concepts", help="this project's concept list, or: concepts add \"<topic>\"")
    concept_args.add_argument("action", nargs="?", help="add")
    concept_args.add_argument("topic", nargs="*")
    concept_args.add_argument("--group", choices=CONCEPT_GROUPS)
    concept_args.add_argument("--track", choices=TRACKS)
    concept_args.add_argument("--status", choices=CONCEPT_STATUSES)
    concept_args.add_argument("--weight", type=int, help="how much of the code leans on it, 1 to 10")
    review_args = commands.add_parser("review", help="reopen a passed topic with no gate")
    review_args.add_argument("topic", nargs="+")
    review_args.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    state = project_root() / STATE_DIR
    if args.command == "start":
        return start(state, " ".join(args.topic).strip(), gated=not args.no_gate, track=args.track)
    if args.command == "build":
        return build(state, not args.no_open)
    if args.command == "unlock":
        return unlock(state, " ".join(args.code))
    if args.command == "skip":
        return skip(state)
    if args.command == "config":
        return config_command(state, args)
    if args.command == "topics":
        return topics(state)
    if args.command == "concepts":
        return concepts_command(state, args)
    if args.command == "issues":
        return issues_command(state)
    if args.command == "review":
        return review(state, " ".join(args.topic), not args.no_open)
    return status(state)


if __name__ == "__main__":
    sys.exit(main())
