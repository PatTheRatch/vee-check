---
description: Show or change Vee Check settings
argument-hint: [setting value] [--global]
---

The user wants to see or change their Vee Check settings. What they typed: $ARGUMENTS

- If they typed nothing, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" config` and show the settings as a short list, each with its current value and what it does.
- If they named a setting and a value (in any wording, such as "plain look", "fewer questions", "make it easier"), work out the matching setting and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" config set <key> <value>`. Add `--global` only if they asked for it to apply to every project.
- If it isn't clear which setting they mean, ask with AskUserQuestion.

Settings: `look` (arcade, classic, plain), `style` (concepts, hands_on), `level` (beginner, intermediate, advanced), `zoom` (what, how, weeds), `lesson` (on, off), `lesson_cards` (2 to 8), `questions` (1 to 10), `pass_bar` (all, or a number), `trigger` (new_concepts, big_concepts_only, manual).

When changing `look`, mention the cost: arcade uses the most tokens and takes longest, plain the least. Confirm the change in one line.
