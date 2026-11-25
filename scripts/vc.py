#!/usr/bin/env python3
"""Vibe Check CLI. Claude runs these to close and open the gate.

  vc.py start "<topic>"        begin a Vibe Check (gate closes); says where to write the quiz content
  vc.py build                  turn the quiz content into the quiz page and open it in the browser
  vc.py unlock <code>          check a pasted pass code; if right, mark the topic passed (gate opens)
  vc.py skip                   drop the pending quiz without passing it (gate opens)
  vc.py status                 show the gate, the settings and what has been passed here
  vc.py config [set KEY VALUE] show or change settings (add --global for all projects)
  vc.py topics                 list what has been covered, across all projects
  vc.py review "<topic>"       reopen a passed topic's lesson and quiz, with no gate

State in the user's project, in .vibe-check/:
  pending.json   the quiz in progress. While it exists, gate.py blocks edits.
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
import sys
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
    "look": ("arcade", ["arcade", "classic", "plain"], "arcade = custom interactive lesson, most tokens and slowest; classic = animated cards; plain = one simple page, fewest tokens"),
    "level": ("beginner", ["beginner", "intermediate", "advanced"], "how much the lesson assumes and how hard the questions are"),
    "lesson": (True, [True, False], "show the Learn part before the Check"),
    "lesson_cards": (4, (2, 8), "how many lesson scenes"),
    "questions": (3, (1, 10), "how many questions"),
    "pass_bar": ("all", None, '"all", or how many questions must be right, for example 2'),
    "trigger": ("new_concepts", ["new_concepts", "big_concepts_only", "manual"], "when a Vibe Check starts"),
}
SCENE_TYPES = {"story", "steps", "playground", "card", "custom"}
QUESTION_TYPES = {"choice", "predict", "explain", "order"}


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
    if args.action != "set" or len(args.pair) != 2:
        return fail('Use: config    or    config set KEY VALUE [--global]')
    key, text = args.pair
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
        else:
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
        marks = "" if marks == "x" else marks
        if question.get("type") == "order":
            trails.append(["right order" if m == "y" else "wrong order" for m in marks if m in "yn"])
        else:
            options = question.get("options", [])
            trails.append([options[int(m)] for m in marks if m.isdigit() and int(m) < len(options)])
    return trails


def add_history(state, pending, result, content=None, tail=""):
    questions = []
    if content:
        for question, tries in zip(content["questions"], parse_trail(tail, content["questions"])):
            questions.append({
                "type": question["type"], "prompt": question["prompt"],
                "options": question.get("options") or question.get("items"),
                "answer": question.get("answer"), "why": question["why"],
                "answers": tries, "tries": max(1, len(tries)), "missed": len(tries) > 1,
            })
    now = datetime.now()
    entry = {
        "date": now.date().isoformat(), "time": now.strftime("%H:%M"),
        "project": str(state.parent), "topic": pending.get("topic"), "slug": pending.get("slug"),
        "result": result, "look": pending.get("look"), "level": pending.get("level"),
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
        review = ""
        if passed and entry.get("review_file") and Path(entry["review_file"]).exists():
            review = f'<a href="{e(Path(entry["review_file"]).as_uri())}">Review</a>'
        rows.append(
            f"<tr><td>{e(str(entry.get('date', '')))}</td>"
            f"<td>{e(str(entry.get('badge') or '')) if passed else ''} {e(str(entry.get('topic', '')))}</td>"
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
</div>
<div class="wide"><table>
<tr><th>Date</th><th>Topic</th><th>Result</th><th>Questions</th><th>XP</th><th>Project</th><th></th></tr>
{''.join(rows) or '<tr><td colspan="7">Nothing yet. Your first Vibe Check will show up here.</td></tr>'}
</table></div>
</body></html>
"""
    path = user_home() / "log.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


# ---------- commands ----------

def start(state, topic):
    pending_file = state / "pending.json"
    slug = slugify(topic)
    if not slug:
        return fail("The topic needs at least one letter or number.")
    if pending_file.exists():
        current = read_json(pending_file).get("topic", "another topic")
        return fail(
            f'A quiz on "{current}" is already pending. '
            "It has to be passed (unlock <code>) or skipped (skip) first."
        )
    if slug in read_json(state / "passed.json"):
        print(f'Already passed: "{topic}". No quiz needed. Gate: OPEN.')
        return 0

    config = load_config(state)
    quizzes = Path(STATE_DIR) / "quizzes"
    write_json(pending_file, {
        "topic": topic, "slug": slug,
        "content": str(quizzes / f"{slug}.json"), "quiz": str(quizzes / f"{slug}.html"),
        "started": date.today().isoformat(),
    })
    (state / "quizzes").mkdir(exist_ok=True)
    print(f'Vibe Check started: "{topic}"')
    print(f"Gate: CLOSED. Edits outside {STATE_DIR}/ are blocked until the quiz is passed or skipped.")
    print(f"Settings: {json.dumps(config)}")
    if not is_set_up(state):
        print("First run here: ask the user the setup questions and save them with config set, before writing the quiz.")
    print(f"Write the quiz content (JSON) to: {state.parent / quizzes / (slug + '.json')}")
    print("Then run: build")
    return 0


def build(state, open_page=True):
    pending_file = state / "pending.json"
    if not pending_file.exists():
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
    problems = check_content(content)
    if problems:
        return fail("The quiz content needs fixing, then run build again:\n- " + "\n- ".join(problems))

    config = load_config(state)
    look = config["look"]
    lesson = scenes_for(look, content.get("lesson", [])) if config["lesson"] else []
    code = new_pass_code()
    page_data = {
        "topic": pending["topic"], "look": look, "level": config["level"], "style": config["style"],
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

    pending.update({"code_hash": fingerprint(code), "look": look, "level": config["level"], "review_file": str(review_file)})
    write_json(pending_file, pending)
    opened = open_in_browser(quiz_file, open_page)
    print(f'Quiz page built ({look} look): {quiz_file}')
    print("Opened in the browser." if opened else "It did not open by itself: give the user that path to open.")
    print('Tell the user in one line: "Vibe Check: pass the quiz and paste the code here." Then stop and wait.')
    return 0


def unlock(state, pasted):
    pending_file = state / "pending.json"
    if not pending_file.exists():
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
            "That pass code doesn't match. Gate: still CLOSED. "
            "Ask the user to copy the code shown at the end of the quiz."
        )

    content = read_json(state.parent / quiz.get("content", ""))
    passed_file = state / "passed.json"
    passed = read_json(passed_file)
    passed[quiz["slug"]] = {"topic": quiz.get("topic", quiz["slug"]), "passed": date.today().isoformat()}
    write_json(passed_file, passed)
    pending_file.unlink()
    try:
        entry = add_history(state, quiz, "pass", content if content.get("questions") else None, re.sub(r"[^0-9a-z-]", "", tail.lower()))
        totals = stats(read_history())
        print(f'Passed: "{passed[quiz["slug"]]["topic"]}". Gate: OPEN. Edits are allowed again.')
        print(f"+{entry_xp(entry)} XP. Level {totals['level']}, {totals['xp']} XP, {totals['streak']}-day streak.")
    except OSError as problem:  # the gate must open even if the log can't be written
        print(f'Passed: "{passed[quiz["slug"]]["topic"]}". Gate: OPEN. Edits are allowed again.')
        print(f"(The Learning Log could not be updated: {problem})")
    return 0


def skip(state):
    pending_file = state / "pending.json"
    if not pending_file.exists():
        print("No quiz is pending, so there is nothing to skip. Gate: OPEN.")
        return 0
    quiz = read_json(pending_file)
    topic = quiz.get("topic", "the pending topic")
    pending_file.unlink()
    try:
        add_history(state, quiz, "skip")
    except OSError:
        pass
    print(f'Skipped: "{topic}". Gate: OPEN.')
    print("It is not marked as passed, so it will be quizzed again next time it comes up.")
    return 0


def status(state):
    print(f"Project: {state.parent}")
    pending_file = state / "pending.json"
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
    review_args = commands.add_parser("review", help="reopen a passed topic with no gate")
    review_args.add_argument("topic", nargs="+")
    review_args.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    state = project_root() / STATE_DIR
    if args.command == "start":
        return start(state, " ".join(args.topic).strip())
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
    if args.command == "review":
        return review(state, " ".join(args.topic), not args.no_open)
    return status(state)


if __name__ == "__main__":
    sys.exit(main())
