---
name: vee-topics
description: List what you have covered with Vee Check. Run only when the user asks for it.
disable-model-invocation: true
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" topics
```

Show the user what they have covered, newest first, with their level, XP and streak, and give them the Learning Log page path from the last line so they can open it. Mention that `/vee-review <topic>` replays any passed topic.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
