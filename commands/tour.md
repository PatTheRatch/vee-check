---
description: Take a guided tour of how this project fits together
---

The user wants the project tour: one lesson on how the whole codebase fits together, with no gate.

Use the vibe-check skill and follow its existing-projects guide, step 2 (Project tour). If a tour was already passed here, replay it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" review "Project tour"`. Otherwise read enough of the code to explain what talks to what, then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" start "Project tour" --no-gate`, write the lesson, and `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" build`.

The goal is that the user can explain the project to someone else afterwards.
