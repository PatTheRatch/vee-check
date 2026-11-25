---
description: List the possible bugs you flagged during Vibe Checks in this project
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" issues
```

Show the user each possible issue: the question, what they expected and what the code does. For any that haven't been looked into in this conversation, offer to check the code against their expectation now.
