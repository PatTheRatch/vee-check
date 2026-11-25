---
name: vee-status
description: Show the Vee Check gate, settings and what has been passed. Run only when the user asks for it.
disable-model-invocation: true
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" status
```

Summarize the result for the user in a few short lines: whether a quiz is pending (and on what), their level, XP and streak, the topics passed in this project, and the current settings.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
