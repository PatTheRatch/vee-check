---
name: vee-review
description: Replay a passed topic's lesson and quiz, with no gate. Run only when the user asks for it.
argument-hint: <topic>
disable-model-invocation: true
---

The user wants to review a topic they already passed (the text they typed after the command, if any).

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" review "<topic>"
```

If it opens, tell the user in one line that the review is open in their browser and that there is nothing to paste. If nothing matches, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" topics` and show what they can review. If they named no topic, do that too and ask which one.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
