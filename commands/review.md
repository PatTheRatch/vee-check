---
description: Replay a passed topic's lesson and quiz, with no gate
argument-hint: <topic>
---

The user wants to review a topic they already passed: $ARGUMENTS

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" review "$ARGUMENTS"
```

If it opens, tell the user in one line that the review is open in their browser and that there is nothing to paste. If nothing matches, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" topics` and show what they can review. If they named no topic, do that too and ask which one.
