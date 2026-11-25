---
name: vibe-check
description: Before writing code that uses a concept the user hasn't learned yet, run a Vibe Check, a quick browser quiz the user must pass before any file edits. Use whenever a task introduces a new library, pattern, data structure or tool.
---

# Vibe Check

DRAFT: finished in build plan step 4 (see the repo's CLAUDE.md).

Outline:
1. Before coding, name the new concept(s) the task needs. Skip anything in `.vibe-check/passed.json`.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" start "<topic>"`.
3. Fill `templates/quiz.html` with 3–5 flashcards + 3–5 multiple-choice questions, save it to `.vibe-check/quizzes/<topic>.html`, and open it.
4. Tell the user in one line: "Vibe Check: pass the quiz and paste the code." Then stop.
5. When they paste a code, run `vc.py unlock <code>`. Do the work only once it succeeds.
6. If the user says skip, run `vc.py skip` and continue.

Good questions test **prediction and understanding** ("what does this return?"), not trivia.
