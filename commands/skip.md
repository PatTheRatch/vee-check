---
description: Skip the pending Vibe Check quiz and open the gate
---

The user wants to skip the pending Vibe Check on purpose.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" skip
```

Tell the user in one line what was skipped and that the concept will be quizzed again the next time it comes up. Then carry on with the task that was waiting, if there was one.
