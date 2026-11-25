---
description: Review part of the code together, as a quiz on what you expect it to do
argument-hint: <area or file>
---

The user wants to check part of the code with them: $ARGUMENTS

Use the vee-check skill and follow its tracks-and-review guide, "Running a review on purpose". Read the code, run it on a small example if you can, then start a no-gate lesson with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" start "<area> review" --no-gate --track domain`, write 3 to 6 `expect` questions on the places where the code makes a choice someone could disagree with (each with a `source`), and `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" build`.

When the user pastes the code from the end, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" unlock` with it and follow up on every POSSIBLE ISSUE it prints. If they named no area, ask which part of the project they want to check.
