---
name: vee-issues
description: List the possible bugs you flagged during Vee Checks in this project. Run only when the user asks for it.
disable-model-invocation: true
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" issues
```

Show the user each possible issue: the question, what they expected and what the code does. For any that haven't been looked into in this conversation, offer to check the code against their expectation now.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
