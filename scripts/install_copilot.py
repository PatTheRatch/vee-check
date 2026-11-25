#!/usr/bin/env python3
"""Set Vee Check up for GitHub Copilot without the plugin system.

Use this when your editor can't install agent plugins (an older VS Code, or a
company policy that switches plugins off). It copies the skills and registers
the edit-blocking hook where Copilot looks for them. Keep this folder where it
is afterwards: the copies point back at its scripts and templates.

  python3 scripts/install_copilot.py                  for you, in every project (~/.copilot)
  python3 scripts/install_copilot.py --workspace DIR  for one repository (DIR/.github)
  python3 scripts/install_copilot.py --uninstall      remove what this script added
                                                      (add --workspace DIR to match)

Standard library only.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
HOOK_FILE = "vee-check.json"
EDIT_TOOLS = "edit|create|str_replace_editor|apply_patch"


def skill_names():
    return sorted(p.name for p in (PLUGIN / "skills").iterdir() if (p / "SKILL.md").exists())


def install(target):
    for name in skill_names():
        destination = target / "skills" / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(PLUGIN / "skills" / name, destination)
        for page in destination.glob("*.md"):
            # Outside the plugin system nothing fills this placeholder in, so write the real folder.
            text = page.read_text(encoding="utf-8")
            page.write_text(text.replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN.as_posix()), encoding="utf-8")
    gate = PLUGIN / "scripts" / "gate.py"
    hook = {"version": 1, "hooks": {"preToolUse": [{
        "type": "command", "matcher": EDIT_TOOLS,
        "bash": f'python3 "{gate.as_posix()}"',
        "powershell": f'python "{gate}"',
        "timeoutSec": 15,
    }]}}
    (target / "hooks").mkdir(parents=True, exist_ok=True)
    (target / "hooks" / HOOK_FILE).write_text(json.dumps(hook, indent=2) + "\n", encoding="utf-8")
    print(f"Installed {len(skill_names())} skills and the edit-blocking hook into {target}")
    print(f"They point at this folder, so keep it here: {PLUGIN}")
    print("Now reload VS Code (Developer: Reload Window), open Copilot chat in agent mode and type /vee-status.")
    print("If /vee-status isn't offered, your VS Code may not read this location: see docs/copilot.md.")


def uninstall(target):
    removed = 0
    for name in skill_names():
        destination = target / "skills" / name
        if destination.exists():
            shutil.rmtree(destination)
            removed += 1
    hook = target / "hooks" / HOOK_FILE
    if hook.exists():
        hook.unlink()
        removed += 1
    print(f"Removed {removed} Vee Check items from {target}. Your Learning Log in ~/.vee-check is untouched.")


def main():
    parser = argparse.ArgumentParser(description="Set Vee Check up for GitHub Copilot without the plugin system.")
    parser.add_argument("--workspace", metavar="DIR", help="install into DIR/.github for one repository")
    parser.add_argument("--uninstall", action="store_true", help="remove what this script added")
    args = parser.parse_args()
    if args.workspace:
        target = Path(args.workspace).expanduser().resolve() / ".github"
    else:
        target = Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot")
    (uninstall if args.uninstall else install)(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
