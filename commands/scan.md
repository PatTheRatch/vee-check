---
description: Scan this project and list the concepts it uses
---

The user wants Vee Check to take stock of a project that already has code.

Use the vee-check skill and follow its existing-projects guide, step 1 (Scan): read the imports, config, file types and recurring patterns, pick the 6 to 15 concepts the code leans on most, and save each with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" concepts add "<topic>" --group <big_picture|tools|techniques> --weight <1-10>`.

Then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" concepts`, show the user the list grouped as Big picture, Tools and Techniques, and offer the next two steps with AskUserQuestion: a project tour (`/vee-check:tour`) and a placement quiz to skip what they already know. Nothing in this command blocks edits.
