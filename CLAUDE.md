# Vibe Check: notes for Claude Code

## What this is
Vibe Check is a Claude Code plugin. When Claude is about to build something that
uses a concept new to the user, it stops, makes a quick HTML quiz
(flashcards, then multiple choice), and **will not edit files until the user passes**.
Tagline: *Learn as you vibe.* It's also a **review aid**: checking that your understanding matches what the code actually does is how bugs get caught.

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
| **Three looks** | The quiz page comes in three looks and the user picks one with the `look` setting: **`arcade`** (the overkill one: sound, mascot, drag games, combo, fireworks; Patrick's favourite and the default), **`classic`** (the original prototype) and **`plain`** (one scrolling page, no animation, no game pieces). Same lesson and questions in all three; only the presentation changes. |
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
  "look": "arcade",             // arcade | classic | plain: how the quiz page looks and feels (see prototypes/)
  "level": "beginner",          // beginner | intermediate | advanced: changes how much the lesson assumes and how hard questions are
  "zoom": "how",                // what | how | weeds: starting depth (adaptive from there)
  "lesson": true,               // show the Learn part before the Check
  "lesson_cards": 4,            // 2–8
  "questions": 3,               // 1–10
  "pass_bar": "all",            // "all" or a number, e.g. 2 (of 3)
  "trigger": "new_concepts",    // new_concepts | big_concepts_only | manual
  "tracks": ["domain","architecture","code"],  // which kinds of concepts get lessons and gates
  "review": true                // ask expectation questions and flag mismatches as possible bugs
}
```

## Look & feel (picked by Patrick)
Fun, animated, gamified. Not plain flashcards.
- **Lesson formats:** *Story scenario* (a real-world problem the concept solves), *Animated
  step-through* (watch the data move as the code runs), *Playground* (change a setting, see the
  result change live).
- **Quiz formats:** *Predict the output* (animated reveal), *Drag and drop* (put steps in order,
  match terms), *Explain it back* (pick the best plain-English explanation for a coworker; this
  is the core of the `concepts` style).
- **Game pieces:** *XP + levels*, *Streaks*, *Topic badges* (shown on the Learning Log).
- Reference prototypes, one per look (all teach the same groupby lesson):
  `prototypes/pandas-groupby-overkill.html` (`arcade`), `prototypes/pandas-groupby.html` (`classic`),
  `prototypes/pandas-groupby-nofrills.html` (`plain`). Step 3's templates generalize them.

## Learning tracks: what kind of thing to learn
Not everyone cares about the code. Someone building a portfolio risk platform needs to know how
*the platform* works (how tracking error is computed, where benchmark weights come from, what
happens when a price is missing) without learning how Python works. Every concept gets a track:
- **Domain / logic:** what the system does in business terms (the risk math, the rules, the data flow).
- **Architecture:** how the pieces fit together.
- **Code:** the language, libraries and patterns.
A `tracks` setting (e.g. `["domain","architecture"]`) picks which ones get lessons and gates.
Lessons on the domain track explain *this project's* logic, not textbook theory.

## Review mode: Vibe Check as a correctness check (big idea, Patrick's)
The quiz doubles as a review: if the user's understanding and the code disagree, either the
user learns something **or the code is wrong**. Design rules:
- **Answer keys come from the code, not from Claude's beliefs.** For predict-the-output
  questions, actually run the code on the example data to get the answer.
- **Expectation questions:** ask what the user *expects* before revealing what the code does
  ("weights should sum to 100%?", "is tracking error annualized?").
- **"That's not what it should do" button** on every reveal. A mismatch the user disputes is
  logged as a **possible bug**, not a missed question, and doesn't count against them. Claude
  then checks the code against the user's expectation and reports back.
- Review findings go in the history and show on the Learning Log ("2 possible issues found").
- Suggested scope: v2, after the core gate/quiz/tracking loop works. The `domain` track and
  expectation questions are the natural place to start.

## Starting late on an existing project (decided)
1. **Scan → concept inventory.** Read imports, libraries, file types and patterns, then list the
   concepts the project uses, ranked by how much of the code depends on each. Group them as
   *Big picture* (architecture), *Tools* (libraries), *Techniques* (patterns).
2. **Project tour first.** One animated lesson on how the whole codebase fits together (what talks
   to what), before any single concept. The goal: the user can explain the project to someone.
3. **Placement quiz.** 2 quick questions per concept. Pass = marked known, no lesson needed.
4. **Concepts already in the code never gate** by default. They go on a learning list the user can
   visit anytime ("teach me X"). The user can choose to make a specific concept gate.
   Only concepts that are *new* to the project gate automatically.
- Command idea: `/vibe-check:scan` runs the inventory, `/vibe-check:tour` replays the tour.

## Depth: how high-level vs. in the weeds (decided)
- Three zoom levels: **What** (what it does and why it's there) → **How** (the moving parts) →
  **Weeds** (the actual lines, edge cases, gotchas). The `concepts` style defaults to What + How.
- **Default + adaptive + zoom:** start at the configured level; go deeper when the user aces
  things and simpler when they miss; every lesson has a "go deeper" button.
- **Concept size rule:** a concept is something you'd explain to a coworker in one sentence when
  they ask why that code is there. "Python" is too big; "f-strings" is too small.
- Store the zoom level reached per concept in the history, so a review picks up there.

## Tracking & review (v1)
Every Vibe Check is logged so the user can see what they've covered and go back to it.
- `~/.vibe-check/history.jsonl` (global, across all projects): one line per Vibe Check with
  date, project, topic, the lesson content, every question with the user's answers, attempts
  and misses, pass/skip, and the quiz file path.
- `.vibe-check/passed.json` (per project) stays as the "don't re-quiz" list.
- **Learning Log page**: a generated `~/.vibe-check/log.html` listing topics covered (by date and
  project), with a **Review** button per topic that replays the lesson and quiz without gating.
- Commands: `/vibe-check:topics` ("what have we covered?") and `/vibe-check:review <topic>`.
- Gamification stats (XP, streaks and so on) are computed from the history, not stored separately.

## Build plan (do these one at a time)
- [x] **1. Gate hook:** write `scripts/gate.py`. It reads the hook's JSON on stdin; if `.vibe-check/pending.json` exists and the target file isn't inside `.vibe-check/`, it exits 2 with a clear message for Claude. Otherwise it exits 0. Test it by piping sample JSON into it.
- [x] **2. CLI:** write `scripts/vc.py` with the start / unlock / skip / status commands, using only the standard library.
- [x] **3. Quiz template:** `templates/quiz.html` as one file with no CDN, so it works on locked-down machines. **Lesson (click-through cards, tiny example, predict-the-output)** → MCQ → retry misses → reveal the pass code. Lengths come from the config. Mobile-friendly.
- [x] **4. Skill:** finish `skills/vibe-check/SKILL.md`: when to trigger, how to write good questions (teach before you test; prediction over definitions; respect config for level and counts; first-run setup questions), the step-by-step flow.
- [x] **5. Slash commands:** `/vibe-check:skip`, `/vibe-check:status`, `/vibe-check:config`. `vc.py` reads and writes the config.
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
