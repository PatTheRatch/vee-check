---
name: vee-scan
description: Scan this project and list the concepts it uses. Run only when the user asks for it.
disable-model-invocation: true
---

The user wants Vee Check to take stock of a project that already has code.

Use the vee-check skill and follow its existing-projects guide, step 1 (Scan): read the imports, config, file types and recurring patterns, pick the 6 to 15 concepts the code leans on most, and save each with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" concepts add "<topic>" --group <big_picture|tools|techniques> --weight <1-10>`.

Then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" concepts`, show the user the list grouped as Big picture, Tools and Techniques, and offer the next two steps with a multiple-choice question (AskUserQuestion in Claude Code, ask_user in Copilot; plain chat if you have neither): a project tour (`/vee-tour`) and a placement quiz to skip what they already know. Nothing in this command blocks edits.

If a command above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder, the plugin folder is the one two levels above this file's folder (it contains `scripts/vc.py`).
