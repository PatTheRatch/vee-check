---
name: vee-check
description: Before writing code that uses a concept the user hasn't learned yet, run a Vee Check, a short browser lesson and quiz the user must pass before any file edits. Use at the start of any coding task that introduces a new library, pattern, data structure, language feature, tool, business rule or calculation to this project, and when the user says "teach me X", "vee check", "what have we covered", "review X", "check this code with me", "scan this project", "make it easier", "fewer questions" or asks to skip a quiz.
---

# Vee Check

Vibe coding is fast, but the code shows up and the user never learns what it does. A Vibe
Check fixes that: before you write code that uses a concept new to the user, they take a
short lesson and quiz in their browser. A hook blocks your file edits until they pass and
paste the pass code back. **Learn → Check → build.**

Every command below runs the plugin's CLI. Run them from the project folder:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vc.py" <command>
```

In the rest of this file, `vc <command>` is short for that full line.

If the line above still shows the text `${CLAUDE_PLUGIN_ROOT}` instead of a real folder,
nothing filled it in for you: the plugin folder is the one two levels above this file's
folder (it contains `scripts/vc.py`). On Windows, use `python` if `python3` isn't found.

This skill works the same in Claude Code and in GitHub Copilot's agent mode. Where it says
"you", it means whichever coding agent is reading it.

## When to run one

Before you edit any file for a task, name the concepts the task needs. A concept is
**something you'd explain to a coworker in one sentence when they ask why that code is
there**. "Python" is too big. "f-strings" is too small. "pandas groupby", "Flask routes",
"async/await", "environment variables for secrets" are the right size.

Run `vc status` first. It shows the settings, what has been passed here, and whether the
project has a concept list. Then follow the `trigger` setting:

| `trigger` | Run a Vee Check when |
|---|---|
| `new_concepts` (default) | the task uses a concept that is new to this project and not yet passed |
| `big_concepts_only` | only for concepts the whole task hinges on, not small helpers |
| `manual` | only when the user asks |

Don't run one for a concept that is already passed, for a pure bug fix or rename that
introduces nothing new, or for code the project already contains (see "Projects that
already have code").

**One Vee Check per task.** If a task needs more than one new concept, quiz the one the
task hinges on (the one the user would most need to explain afterwards), and fold a small
prerequisite into its lesson as one `card` scene. For "load a CSV and total it by region",
that means a Vee Check on `groupby` with one card on what a DataFrame is. Only run a
second Vee Check in the same task when the second concept is as big as the first.

## The flow

1. **Start.** `vc start "<topic>" --track <domain|architecture|code>`. Use a short, specific
   topic ("pandas groupby"). The track says what kind of concept it is (see "Tracks"); if the
   user has switched that track off, `start` says so and there is nothing more to do. This
   closes the gate and prints the settings and the path for the quiz content. If it says
   "Already passed", skip the rest and get on with the work. Also run `vc topics` once: it
   shows how the user did on recent quizzes, which sets the depth (see "Depth" below).
2. **First run only.** If the output says "First run here", ask the setup questions below
   before writing anything.
3. **Write the content.** One JSON file at the path `start` printed. The format, with
   examples, is in [quiz-format.md](quiz-format.md). Follow the settings: `lesson_cards`
   scenes in total (a custom scene counts as one), `questions` questions, pitched at `level`
   and `zoom`. Writing inside `.vee-check/` is always allowed, with any tool.
4. **Build.** `vc build`. It checks the content, makes the page in the user's `look` and
   opens it. If it lists problems, fix the JSON and build again.
5. **Hand over and stop.** Say one line: "Vee Check: pass the quiz and paste the code
   here." If `build` said the page did not open by itself, add the file path on a second
   line so the user can open it. Then end your turn. Do not start the work, plan it out
   loud, or give hints.
6. **Unlock.** When the user pastes a code (it looks like `K7QM-2XPA.10-y-1`; the part after
   the dot is their answers), run `vc unlock <exactly what they pasted>`. If it says the
   code doesn't match, tell them and wait again. If it prints a **POSSIBLE ISSUE**, the user
   disagreed with what the code does: deal with that first (see "Review mode").
7. **Build the thing.** The gate is open. Do the task. In one line, connect the first piece
   of code you write to what they just learned.

If the user says to skip: `vc skip`, then carry on. A skipped concept is quizzed again next
time it comes up. Never suggest skipping yourself.

## First-run setup questions

Ask these once per project with a multiple-choice question (AskUserQuestion in Claude Code, ask_user in Copilot; plain chat if you have neither), then save each answer with
`vc config set <key> <value>` (add `--global` if they want it everywhere):

1. **Look** (`look`). Say what each costs:
   - `classic` (the default): animated lesson cards and a quiz. Middle of the road.
   - `arcade`: a custom interactive lesson built for the topic, with sound, a mascot and
     game pieces. Uses the most tokens and takes the longest to appear.
   - `plain`: one simple page. Fastest and cheapest.
2. **Tracks** (`tracks`, pick any): `domain` (what the system does in business terms),
   `architecture` (how the pieces fit together), `code` (the language, libraries and
   patterns). Someone who doesn't care about the code can leave `code` off.
3. **Style** (`style`): `concepts` (understand it well enough to explain it, no typing
   code) or `hands_on` (also write a small piece yourself).
4. **Level** (`level`): `beginner`, `intermediate` or `advanced`.

Leave the other settings at their defaults unless the user asks. Later, when the user says
things like "make it easier", "fewer questions", "go plainer" or "only quiz me on big
things", change the matching setting with `vc config set` and confirm in one line.
`vc config` lists every setting and what it does.

## Writing a lesson worth taking

Read [quiz-format.md](quiz-format.md) before your first one. The short version:

- **Teach before you test.** Every question must be answerable from the lesson alone.
- **Prediction over definitions**, and at least one `explain` question (pick the best
  plain-English explanation for a coworker). A good mix for three questions: one about
  behaviour (`predict` or `expect`), one about the code itself (`fill`, `bug`, `order` or
  `match`), and one `explain`. Vary the types from one Vee Check to the next.
- **One tiny, concrete dataset** from the user's own domain, carried through lesson and quiz.
- **Check your answer key.** Work out every output yourself or run the code.
- **Make the learner do something.** In every look, at least one scene should come from
  the interactive template library in quiz-format.md: `sort`, `match`, `flow`, `slider`,
  `build` or `compare`. Pick the one whose action *is* the concept (grouping → `sort`,
  joining → `match`, a request or a calculation moving through parts → `flow`).
- When `look` is `arcade` and no library template fits the concept, write one custom scene
  for it. Read [arcade-scenes.md](arcade-scenes.md) first. If a library template fits, use
  it instead: it costs a few lines of data and can't break. Never write a custom scene in
  the other looks.
- `level` is how much the user already knows (which words you can use without explaining
  them). `zoom` is how far into the mechanics this lesson goes. They move independently.

### Depth (`zoom`) and adapting

Three depths: **what** (what it does and why it's there), **how** (the moving parts),
**weeds** (the actual lines, edge cases, gotchas). Start at the `zoom` setting. Then adapt
using `vc topics`, which shows how the user did recently:

- Last two Vee Checks all right first try → go one level deeper this time.
- Missed half or more last time → go one level simpler.

Put `"zoom"` in the content to record the depth you wrote at. Where there is something
worth saying one level down, give a scene a `"deeper"` paragraph for its "Go deeper"
button (aim for at least one per lesson; on a custom scene it goes on the scene itself).

## Tracks and review mode

Read [tracks-and-review.md](tracks-and-review.md) before your first domain or architecture
lesson, and whenever `unlock` prints a POSSIBLE ISSUE. The essentials:

- **Tracks.** Every concept is `domain`, `architecture` or `code`. Only tracks in the
  `tracks` setting get lessons and gates. A domain lesson teaches *this project's* logic in
  the project's own names and numbers, without language syntax.
- **Answer keys come from the code.** Run the code on the example data, or trace the exact
  lines, and record where the answer came from in the question's `"source"`.
- **Expectation questions** (`"type": "expect"`) ask what the user expects before showing
  what the code does. Put one or two in every domain-track quiz.
- **A disputed answer is a possible bug.** The user can press "That's not what it should
  do" on any reveal. When `unlock` reports one, check the code against their expectation
  and tell them what you found before building anything on top of it.

## The `hands_on` style

When `style` is `hands_on`, after the quiz is passed and before you finish the task, leave
one small, meaningful piece (2 to 10 lines) for the user to write: mark it with a
`TODO(human)` comment, say what it should do and what to watch for, and wait. Then check
it and give one sentence of feedback. When `style` is `concepts`, never ask the user to
write code.

## Lessons with no gate

For "teach me X", a project tour, or a placement quiz: `vc start "<topic>" --no-gate`, then
write and `build` as usual. Nothing is blocked, so keep working. If the user pastes the code
from the end, run `vc unlock` to record it.

- `vc topics`: what the user has covered, with a link to their Learning Log page.
- `vc review "<topic>"`: reopens a passed topic's lesson and quiz with no gate.

## Projects that already have code

If the project already has source files (more than data and config) but `vc status` says
"Concept list: none yet", don't gate the user on code that was already there. Follow [existing-projects.md](existing-projects.md):
scan, tour, placement quiz. After that, only concepts **new to the project** gate.

## Rules

- **Never show, hint at or look for the pass code.** Don't open the built quiz page.
- **Never work around the gate**: no creating or changing files outside `.vee-check/`
  with Bash while a quiz is pending, no deleting `pending.json`, no editing `passed.json`. If the gate reports that it is broken, tell the
  user and offer `vc skip`.
- **Don't answer the quiz for the user.** If they ask for help on a question, re-explain
  the idea in different words, not the answer.
- **Keep the hand-over to one line.** The lesson is in the browser, not in the chat.
- Costs: a Vee Check adds a lesson's worth of tokens to the task, most with `arcade`,
  least with `plain`. If the user worries about usage, suggest `plain` or
  `big_concepts_only`.

## The worked example

`${CLAUDE_PLUGIN_ROOT}/examples/pandas-playground/quiz-example/` holds one complete Vibe
Check on pandas groupby: `pandas-groupby.json` (content), `pandas-groupby.scene.html` and
`pandas-groupby.scene.js` (the arcade custom scene). Read all three once, before your first
Vee Check, to see the shape. It is a reference, not a template: write each lesson fresh
for the user's topic and data, and design a new interaction for each custom scene. Only
reuse the example's idea when the topic really is groupby.
