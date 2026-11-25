#!/usr/bin/env python3
"""Vee Check gate: a "before tool use" hook for Claude Code and GitHub Copilot.

The agent's host runs this before a tool call and pipes the call in as JSON on
stdin. While a quiz is pending (.vee-check/pending.json exists), file edits
outside .vee-check/ are blocked. Reading, searching and shell commands are never
blocked, so the agent can still run vc.py.

To block, it does three things at once, so either host understands:
  exit code 2          Claude Code and Copilot both treat this as "deny"
  a message on stderr  Claude Code passes this to the agent
  JSON on stdout       Copilot reads {"permissionDecision": "deny", ...}

If the gate itself breaks:
  no quiz pending  the crash exits 1 and Claude Code lets the edit through
                   (Copilot denies on any error, so the gate never crashes on purpose)
  quiz pending     the error is caught and the edit is blocked (fail closed)

To see exactly what your editor sends, create an empty file .vee-check/debug:
every call is then appended to .vee-check/hook-log.jsonl.
"""
import json
import os
import re
import sys
from pathlib import Path

STATE_DIR = ".vee-check"
ALLOW = 0
BLOCK = 2

# Tool names differ between hosts, so the gate recognises both families.
EDIT_TOOLS = {
    "edit", "write", "multiedit", "notebookedit",                      # Claude Code
    "create", "str_replace_editor", "apply_patch",                     # Copilot
    "replace_string_in_file", "multi_replace_string_in_file", "insert_edit_into_file",
    "create_file", "edit_file", "editfiles", "edit_notebook_file", "str_replace_based_edit_tool",
}
SAFE_TOOLS = {
    "read", "view", "glob", "grep", "ls", "bash", "powershell", "task", "agent", "skill",
    "web_fetch", "webfetch", "websearch", "ask_user", "askuserquestion", "todowrite",
}
EDIT_WORDS = ("edit", "write", "patch", "replace", "insert")
PATH_KEYS = ("file_path", "notebook_path", "path", "filePath", "file", "filename", "target_file", "uri")
PATCH_KEYS = ("input", "patch", "patchText", "diff")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.MULTILINE)


def read_hook_input():
    """The tool call the host piped in, as a dict ({} if it isn't usable)."""
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return {}
    return hook if isinstance(hook, dict) else {}


def project_root(hook):
    """The user's project folder, which is where .vee-check/ lives."""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or hook.get("cwd") or os.getcwd())


def tool_name(hook):
    """Claude Code says tool_name, Copilot says toolName."""
    name = hook.get("tool_name") or hook.get("toolName") or ""
    return name if isinstance(name, str) else ""


def is_edit_tool(name):
    """True for a tool that changes files. An unknown tool counts only if its name says so."""
    low = name.lower()
    if low in EDIT_TOOLS:
        return True
    return low not in SAFE_TOOLS and any(word in low for word in EDIT_WORDS)


def tool_args(hook):
    """The tool's inputs: tool_input (Claude Code) or toolArgs (Copilot, sometimes JSON as text)."""
    args = hook.get("tool_input", hook.get("toolArgs"))
    if isinstance(args, str):
        try:
            return json.loads(args)
        except ValueError:
            return args  # for example the raw text of a patch
    return args


def target_files(hook, root):
    """Absolute paths of every file the call would change (empty if we can't tell)."""
    args, found = tool_args(hook), []

    def from_patch(text):
        found.extend(PATCH_FILE.findall(text))

    def from_dict(item):
        for key in PATH_KEYS:
            if isinstance(item.get(key), str) and item[key]:
                found.append(item[key])
        for key in PATCH_KEYS:
            if isinstance(item.get(key), str):
                from_patch(item[key])
        for value in item.values():  # for example {"edits": [{"filePath": ...}, ...]}
            if isinstance(value, list):
                for part in value:
                    if isinstance(part, dict):
                        from_dict(part)

    if isinstance(args, dict):
        from_dict(args)
    elif isinstance(args, str):
        from_patch(args)

    base = Path(hook.get("cwd") or root)
    paths = []
    for name in found:
        name = name.strip()
        if name.startswith("file://"):
            name = name[len("file://"):]
        # Joining onto an absolute path just returns that path, so this only
        # changes anything when the tool was given a relative path.
        paths.append(base / name)
    return paths


def is_inside(target, folder):
    """True if the file `target` is somewhere inside the directory `folder`.

    Both are absolute pathlib.Path objects. `target` often doesn't exist yet,
    because Write creates new files.
    """
    return Path(target).resolve().is_relative_to(folder.resolve())


def block_message(pending):
    """What the agent reads when an edit is blocked."""
    try:
        topic = json.loads(pending.read_text()).get("topic")
    except (OSError, ValueError, AttributeError):
        topic = None
    quiz = f'the "{topic}" quiz' if topic else "the pending quiz"
    vc = Path(__file__).with_name("vc.py")
    return (
        f"Vee Check: edit blocked. The user hasn't passed {quiz} yet.\n"
        "Don't edit project files or work around this another way (for example with shell commands).\n"
        "Ask the user to finish the quiz in their browser and paste the pass code, then run:\n"
        f'  python3 "{vc}" unlock <code>\n'
        "If the user says to skip the quiz, run the same script with: skip\n"
        f"Files inside {STATE_DIR}/ can still be written."
    )


def crash_message(error):
    """What the agent reads when the gate itself breaks while a quiz is pending."""
    vc = Path(__file__).with_name("vc.py")
    return (
        f"Vee Check: the gate hit an error ({error!r}) while a quiz is pending, "
        "so the edit is blocked to be safe.\n"
        "Tell the user the gate is broken and show them this error. "
        "If they say to skip the quiz, run:\n"
        f'  python3 "{vc}" skip'
    )


def log_call(state_dir, hook):
    """Opt-in record of what the host sent, for working out a new editor's format."""
    try:
        if (state_dir / "debug").exists() or os.environ.get("VEE_CHECK_DEBUG"):
            with (state_dir / "hook-log.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(hook) + "\n")
    except OSError:
        pass


def decide(hook, root, state_dir):
    """ALLOW or BLOCK for one tool call while a quiz is pending."""
    name = tool_name(hook)
    if name and not is_edit_tool(name):
        return ALLOW  # reading, searching, shell: never gated
    targets = target_files(hook, root)
    if targets and all(is_inside(target, state_dir) for target in targets):
        return ALLOW  # writing the quiz itself is fine
    if not targets and name and name.lower() not in EDIT_TOOLS:
        return ALLOW  # a tool we only guessed was an edit, with no file in sight
    return BLOCK


def main():
    hook = read_hook_input()
    root = project_root(hook)
    state_dir = root / STATE_DIR
    pending = state_dir / "pending.json"
    log_call(state_dir, hook)

    # Fail open: an error up to here is not caught (see the note at the top).
    if not pending.exists():
        return ALLOW  # no quiz pending: the gate is open

    # Fail closed: a quiz is pending, so from here any error blocks the edit.
    try:
        if decide(hook, root, state_dir) == ALLOW:
            return ALLOW
        message = block_message(pending)
    except Exception as error:
        message = crash_message(error)

    print(message, file=sys.stderr)
    print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": message}))
    return BLOCK


if __name__ == "__main__":
    sys.exit(main())
