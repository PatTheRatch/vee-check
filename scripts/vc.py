#!/usr/bin/env python3
"""Vibe Check CLI. Claude runs these to close and open the gate.

  vc.py start "<topic>"   begin a quiz: make a pass code and pending.json (gate closes)
  vc.py unlock <code>     check a pasted pass code; if right, mark the topic passed (gate opens)
  vc.py skip              drop the pending quiz without passing it (gate opens)
  vc.py status            show the gate and which topics have been passed

State lives in the user's project, in .vibe-check/:
  pending.json   the quiz in progress. While it exists, gate.py blocks edits.
  passed.json    topics already passed, so they are not quizzed again.
  quizzes/       the quiz pages.

Exit codes: 0 = done, 1 = could not do it (wrong code, quiz already pending, ...).
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import date
from pathlib import Path

STATE_DIR = ".vibe-check"
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, which look alike


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
        # ~/.vibe-check/ holds global settings, not a project's quiz state.
        if folder != Path.home() and (folder / STATE_DIR).is_dir():
            return folder
    return here


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
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def fail(message):
    print(message, file=sys.stderr)
    return 1


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

    code = new_pass_code()
    quiz = Path(STATE_DIR) / "quizzes" / f"{slug}.html"
    write_json(pending_file, {
        "topic": topic,
        "slug": slug,
        "code_hash": fingerprint(code),  # the fingerprint only, never the code
        "quiz": str(quiz),
        "started": date.today().isoformat(),
    })
    (state / "quizzes").mkdir(exist_ok=True)
    print(f'Vibe Check started: "{topic}"')
    print(f"Gate: CLOSED. Edits outside {STATE_DIR}/ are blocked until the quiz is passed or skipped.")
    print(f"Quiz file to write: {state.parent / quiz}")
    print(f"Pass code to hide in the quiz: {code}")
    print("Don't show the pass code to the user. They earn it by passing the quiz.")
    return 0


def unlock(state, code):
    pending_file = state / "pending.json"
    if not pending_file.exists():
        return fail("No quiz is pending, so there is nothing to unlock. Gate: OPEN.")
    quiz = read_json(pending_file)
    if not quiz.get("code_hash") or not quiz.get("slug"):
        return fail("pending.json is damaged, so the code can't be checked. Run skip to clear it, then start again.")
    if fingerprint(code) != quiz["code_hash"]:
        return fail(
            "That pass code doesn't match. Gate: still CLOSED. "
            "Ask the user to copy the code shown at the end of the quiz."
        )

    passed_file = state / "passed.json"
    passed = read_json(passed_file)
    passed[quiz["slug"]] = {"topic": quiz.get("topic", quiz["slug"]), "passed": date.today().isoformat()}
    write_json(passed_file, passed)
    pending_file.unlink()
    print(f'Passed: "{passed[quiz["slug"]]["topic"]}". Gate: OPEN. Edits are allowed again.')
    return 0


def skip(state):
    pending_file = state / "pending.json"
    if not pending_file.exists():
        print("No quiz is pending, so there is nothing to skip. Gate: OPEN.")
        return 0
    topic = read_json(pending_file).get("topic", "the pending topic")
    pending_file.unlink()
    print(f'Skipped: "{topic}". Gate: OPEN.')
    print("It is not marked as passed, so it will be quizzed again next time it comes up.")
    return 0


def status(state):
    print(f"Project: {state.parent}")
    pending_file = state / "pending.json"
    if pending_file.exists():
        quiz = read_json(pending_file)
        print(f'Gate: CLOSED. Quiz pending on "{quiz.get("topic", "?")}" (started {quiz.get("started", "?")}).')
        if quiz.get("quiz"):
            print(f"Quiz file: {state.parent / quiz['quiz']}")
    else:
        print("Gate: OPEN. No quiz pending.")
    passed = read_json(state / "passed.json")
    if passed:
        print(f"Passed ({len(passed)}):")
        for entry in passed.values():
            print(f"  - {entry.get('topic', '?')} ({entry.get('passed', '?')})")
    else:
        print("Passed: none yet.")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="vc.py", description="Vibe Check: close and open the quiz gate.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    start_args = commands.add_parser("start", help="begin a quiz on a topic (closes the gate)")
    start_args.add_argument("topic", nargs="+", help="the concept, for example: pandas DataFrames")
    unlock_args = commands.add_parser("unlock", help="check a pass code (opens the gate if it matches)")
    unlock_args.add_argument("code", nargs="+", help="the pass code shown at the end of the quiz")
    commands.add_parser("skip", help="drop the pending quiz without passing it (opens the gate)")
    commands.add_parser("status", help="show the gate and which topics have been passed")
    args = parser.parse_args()

    state = project_root() / STATE_DIR
    if args.command == "start":
        return start(state, " ".join(args.topic).strip())
    if args.command == "unlock":
        return unlock(state, " ".join(args.code))
    if args.command == "skip":
        return skip(state)
    return status(state)


if __name__ == "__main__":
    sys.exit(main())
