#!/usr/bin/env python3
"""Vibe Check gate (PreToolUse hook).

Claude Code runs this before every Edit / Write / MultiEdit / NotebookEdit and
pipes the tool call in as JSON on stdin. While a quiz is pending
(.vibe-check/pending.json exists), only files inside .vibe-check/ may be written.

Exit codes:
  0  allow the edit
  2  block the edit; whatever we print to stderr is passed back to Claude

If the gate itself breaks:
  no quiz pending  the crash exits 1, which Claude Code treats as "hook had a
                   problem", and the edit goes through (fail open)
  quiz pending     the error is caught and the edit is blocked (fail closed)
"""
import json
import os
import sys
from pathlib import Path

STATE_DIR = ".vibe-check"
ALLOW = 0
BLOCK = 2


def read_hook_input():
    """The tool call Claude Code piped in, as a dict ({} if it isn't usable)."""
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return {}
    return hook if isinstance(hook, dict) else {}


def project_root(hook):
    """The user's project folder, which is where .vibe-check/ lives."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or hook.get("cwd") or os.getcwd())


def target_file(hook, root):
    """Absolute path of the file about to be changed, or None if we can't tell."""
    tool_input = hook.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(path, str) or not path:
        return None
    # Joining onto an absolute `path` just returns `path`, so this only
    # changes anything when the tool was given a relative path.
    return Path(hook.get("cwd") or root) / path


def is_inside(target, folder):
    """True if the file `target` is somewhere inside the directory `folder`.

    Both are absolute pathlib.Path objects. `target` often doesn't exist yet,
    because Write creates new files.
    """
    return Path(target).resolve().is_relative_to(folder.resolve())


def block_message(pending):
    """What Claude reads when an edit is blocked."""
    try:
        topic = json.loads(pending.read_text()).get("topic")
    except (OSError, ValueError, AttributeError):
        topic = None
    quiz = f'the "{topic}" quiz' if topic else "the pending quiz"
    vc = Path(__file__).with_name("vc.py")
    return (
        f"Vibe Check: edit blocked. The user hasn't passed {quiz} yet.\n"
        "Don't edit project files or work around this another way (for example with Bash).\n"
        "Ask the user to finish the quiz in their browser and paste the pass code, then run:\n"
        f'  python3 "{vc}" unlock <code>\n'
        "If the user says to skip the quiz, run the same script with: skip\n"
        f"Files inside {STATE_DIR}/ can still be written."
    )


def crash_message(error):
    """What Claude reads when the gate itself breaks while a quiz is pending."""
    vc = Path(__file__).with_name("vc.py")
    return (
        f"Vibe Check: the gate hit an error ({error!r}) while a quiz is pending, "
        "so the edit is blocked to be safe.\n"
        "Tell the user the gate is broken and show them this error. "
        "If they say to skip the quiz, run:\n"
        f'  python3 "{vc}" skip'
    )


def main():
    hook = read_hook_input()
    root = project_root(hook)
    state_dir = root / STATE_DIR
    pending = state_dir / "pending.json"

    # Fail open: an error up to here exits 1 and the edit goes through.
    if not pending.exists():
        return ALLOW  # no quiz pending: the gate is open

    # Fail closed: a quiz is pending, so from here any error blocks the edit.
    try:
        target = target_file(hook, root)
        if target and is_inside(target, state_dir):
            return ALLOW  # writing the quiz itself is fine
        message = block_message(pending)
    except Exception as error:
        message = crash_message(error)

    print(message, file=sys.stderr)
    return BLOCK


if __name__ == "__main__":
    sys.exit(main())
