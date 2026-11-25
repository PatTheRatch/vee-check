---
name: vee-skip
description: Skip the pending Vee Check quiz and open the gate. Run only when the user asks for it.
disable-model-invocation: true
---

The user wants to skip the pending Vee Check on purpose.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" skip
```

Tell the user in one line what was skipped and that the concept will be quizzed again the next time it comes up. Then carry on with the task that was waiting, if there was one.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
