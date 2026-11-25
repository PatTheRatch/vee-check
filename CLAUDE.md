# Vibe Check: notes for Claude Code

## What this is
Vibe Check is a Claude Code plugin. When Claude is about to build something that
uses a concept new to the user, it stops, makes a quick HTML quiz
(flashcards, then multiple choice), and **will not edit files until the user passes**.
Tagline: *Learn as you vibe.*

It's Patrick's own tool first. It should also work as a general plugin anyone can
install from this repo, so keep anything specific to Patrick out of the plugin files.

## How to work with Patrick
- Python and SQL background. Calls himself a vibe coder. Wants to understand what gets built.
- **One task at a time.** Do the next step in the build plan, show it, stop.
  Don't run ahead into later steps.
- Keep explanations short. He won't read walls of text. Use a few bullets, or ask him
  multiple-choice questions (AskUserQuestion) when there's a decision to make.
- **Dogfood the idea before the gate exists. Teach first, then quiz.** At the start of each
  build step, give Patrick a **mini lesson** on the concept that step uses: 3–5 short bullets
  in plain language, one tiny concrete example, and why it matters for this step. Assume he
  has never seen it. Only then ask 2–3 multiple-choice questions (AskUserQuestion) that check
  that lesson, not trivia he couldn't know. If he misses one, explain it and re-ask. If he says
  "skip", skip. **Patrick's goal is concepts** (being able to explain what the code does),
  not becoming a software engineer, so don't make him write code by default. While building
  *this* repo he's open to trying hands-on now and then to test the `hands_on` style, but
  offer it as a choice, don't require it. (Learned in step 1: quizzing on exit codes with no lesson first just meant guessing.)

## Locked v1 decisions (settled, don't re-ask)
| Decision | Choice |
|---|---|
| Where the quiz shows | HTML page opened in the browser: flashcards first, then multiple choice |
| Gate strength | **Hard**: a PreToolUse hook blocks file edits while a quiz is pending, plus a deliberate `skip` escape hatch |
| How passing unlocks | Acing the quiz reveals a **pass code**; the user pastes it into Claude Code; it's checked and the gate opens |
| What triggers a quiz | Claude spots a new concept, and skips concepts the user has already passed |
| Pass bar | **All correct.** A miss shows the explanation, then the user retries just that question |
| First test topic | pandas DataFrames (something Patrick already knows, so we test the tool, not him) |
| **Lesson before quiz** | Every Vibe Check is **Learn → Check**: a short interactive lesson first (click-through cards with a tiny example, maybe a "predict the output" step), *then* the quiz. Never quiz on something that wasn't taught. |
| **If the gate breaks** | Fail closed only while a quiz is pending (error → exit 2 with a "gate is broken" message). With no quiz pending, an error lets the edit through, so a bug can't lock up normal editing. |
| **After a skip** | `skip` only opens the gate this once. The concept is not marked as passed, so it gets quizzed again the next time it comes up. |
| **Concepts vs. hands-on** | A `style` setting. **`concepts` (default):** the goal is understanding what the code does well enough to explain it to someone, no typing code. **`hands_on`:** learn by doing, where the user writes a small piece of the code themselves. Never force hands-on when the style is `concepts`. |
| **Adjustable** | Difficulty, number of questions, pass bar, lesson on/off and trigger sensitivity are all settings. Asked at first run in a project, changeable anytime (see Settings below). |

## Architecture (v1)
```
.claude-plugin/plugin.json      plugin manifest
.claude-plugin/marketplace.json lets people install the plugin from this repo
skills/vibe-check/SKILL.md      tells Claude WHEN and HOW to run a vibe check
hooks/hooks.json                PreToolUse hook on Edit|Write|MultiEdit|NotebookEdit
scripts/gate.py                 the hook: blocks edits while a quiz is pending (exit 2 + message)
scripts/vc.py                   CLI: start <topic> / unlock <code> / skip / status
templates/quiz.html             single-file quiz template; Claude fills in a JSON block of cards + questions
commands/                       slash commands (/vibe-check:skip, /vibe-check:status)
examples/pandas-playground/     a scratch project for testing the plugin on pandas
```

**State** lives in the *user's* project at `.vibe-check/`:
- `pending.json`: the current quiz (topic, hash of the pass code, path to the quiz file). While this file exists, the gate is closed.
- `passed.json`: concepts already passed, so they don't get re-quizzed.
- `quizzes/<topic>.html`: the generated quiz pages.

**The flow:**
1. Claude spots a new concept and runs `vc.py start "<topic>"`, which creates the pass code and `pending.json`.
2. Claude writes `.vibe-check/quizzes/<topic>.html` from the template and opens it in the browser. The gate lets writes inside `.vibe-check/` through.
3. The user passes and pastes the code into Claude Code. Claude runs `vc.py unlock <code>`: if the hash matches, the concept is added to `passed.json` and `pending.json` is removed.
4. Edits are allowed again, and Claude does the actual work.

**About the pass code:** this is a self-imposed gate, not a security system. The code
lives inside the quiz HTML, hidden until the user passes (base64 or similar is enough).
Don't over-engineer it.

## Settings (v1)
Stored at `.vibe-check/config.json` in the project, with optional global defaults at
`~/.vibe-check/config.json` (project wins). Asked once, the first time Vibe Check runs in a
project (AskUserQuestion), and changeable anytime with `/vibe-check:config` or by just saying
"make it easier", "fewer questions", etc.
```json
{
  "style": "concepts",          // concepts = understand it well enough to explain it to someone (default)
                                //   hands_on = also learn by doing: write a small piece of the code yourself
  "level": "beginner",          // beginner | intermediate | advanced: changes how much the lesson assumes and how hard questions are
  "lesson": true,               // show the Learn part before the Check
  "lesson_cards": 4,            // 2–8
  "questions": 3,               // 1–10
  "pass_bar": "all",            // "all" or a number, e.g. 2 (of 3)
  "trigger": "new_concepts"     // new_concepts | big_concepts_only | manual
}
```

## Build plan (do these one at a time)
- [x] **1. Gate hook:** write `scripts/gate.py`. It reads the hook's JSON on stdin; if `.vibe-check/pending.json` exists and the target file isn't inside `.vibe-check/`, it exits 2 with a clear message for Claude. Otherwise it exits 0. Test it by piping sample JSON into it.
- [x] **2. CLI:** write `scripts/vc.py` with the start / unlock / skip / status commands, using only the standard library.
- [ ] **3. Quiz template:** `templates/quiz.html` as one file with no CDN, so it works on locked-down machines. **Lesson (click-through cards, tiny example, predict-the-output)** → MCQ → retry misses → reveal the pass code. Lengths come from the config. Mobile-friendly.
- [ ] **4. Skill:** finish `skills/vibe-check/SKILL.md`: when to trigger, how to write good questions (teach before you test; prediction over definitions; respect config for level and counts; first-run setup questions), the step-by-step flow.
- [ ] **5. Slash commands:** `/vibe-check:skip`, `/vibe-check:status`, `/vibe-check:config`. `vc.py` reads and writes the config.
- [ ] **6. Test it:** install the plugin locally and use it in `examples/pandas-playground` (for example, "load a CSV into a DataFrame and group by a column"). Fix whatever feels annoying.
- [ ] **7. README + release:** install steps, a GIF/screenshot, tag v0.1.0.

## Open questions (bring up when you get to them, not before)
- Should the gate also catch `Bash` commands that write files (`>`, `sed -i`, `cat <<EOF`)? Probably yes in v2.
- "Claude spots a new concept" depends on Claude following the skill. Is that good enough, or does a UserPromptSubmit hook need to nudge it?
- Should `passed.json` turn into a "what I've learned" page later?

## Conventions
- Python 3, standard library only, for anything in `scripts/` (corporate machines can be restricted).
- No external JS/CSS in templates.
- Plugin paths use `${CLAUDE_PLUGIN_ROOT}`.
- Commit after each build step with a short message.
