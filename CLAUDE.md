# Vee Check: notes for Claude Code

## What this is
Vee Check is a Claude Code plugin. When Claude is about to build something that
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
| **Lesson before quiz** | Every Vee Check is **Learn → Check**: a short interactive lesson first (click-through cards with a tiny example, maybe a "predict the output" step), *then* the quiz. Never quiz on something that wasn't taught. |
| **If the gate breaks** | Fail closed only while a quiz is pending (error → exit 2 with a "gate is broken" message). With no quiz pending, an error lets the edit through, so a bug can't lock up normal editing. |
| **After a skip** | `skip` only opens the gate this once. The concept is not marked as passed, so it gets quizzed again the next time it comes up. |
| **Concepts vs. hands-on** | A `style` setting. **`concepts` (default):** the goal is understanding what the code does well enough to explain it to someone, no typing code. **`hands_on`:** learn by doing, where the user writes a small piece of the code themselves. Never force hands-on when the style is `concepts`. |
| **Three looks** | The quiz page comes in three looks and the user picks one with the `look` setting: **`arcade`** (the overkill one: sound, mascot, drag games, combo, fireworks; Patrick's favourite, set as his own global default), **`classic`** (the original prototype, **the default for everyone else**) and **`plain`** (one scrolling page, no animation, no game pieces). Same lesson and questions in all three; only the presentation changes. |
| **Adjustable** | Difficulty, number of questions, pass bar, lesson on/off and trigger sensitivity are all settings. Asked at first run in a project, changeable anytime (see Settings below). |

## Architecture (v1, as built)
```
.claude-plugin/plugin.json      plugin manifest
.claude-plugin/marketplace.json lets people install the plugin from this repo
skills/vee-check/SKILL.md      tells Claude WHEN and HOW to run a Vee Check
  quiz-format.md                the quiz content format (lesson scenes, question types)
  arcade-scenes.md              how to write a custom scene for the arcade look
  existing-projects.md          scan, tour and placement quiz for projects that already have code
  tracks-and-review.md          the three tracks, expectation questions, possible issues
hooks/hooks.json                PreToolUse hook on Edit|Write|MultiEdit|NotebookEdit
scripts/gate.py                 the hook: blocks edits while a quiz is pending (exit 2 + message)
scripts/vc.py                   CLI: start / build / unlock / skip / status / config / topics / review / concepts / issues
templates/core.js               shared quiz rules, pass code and answer trail; stamped into every page
templates/game.html             the arcade and classic looks (one file, arcade switches the extras on)
templates/plain.html            the plain look
commands/                       slash commands: skip, status, config, topics, review, scan, tour, check, issues
examples/pandas-playground/     sample data plus a complete worked quiz (content + custom scene)
prototypes/                     the three hand-built groupby pages the looks came from
tests/test_vee_check.py        gate and CLI tests (python3 -m unittest discover -s tests)
```

**State** in the *user's* project at `.vee-check/`:
- `pending.json`: the gated quiz in progress (topic, hash of the pass code, paths). While this file exists, the gate is closed.
- `practice.json`: a no-gate lesson in progress (`start --no-gate`). The gate ignores it.
- `passed.json`: concepts already passed, so they don't get re-quizzed.
- `concepts.json`: the project's concept list from a scan (learning / known / gate).
- `config.json`: this project's settings.
- `quizzes/<topic>.json`: the quiz content Claude writes. `quizzes/<topic>.html`: the built page.

**State for the user** at `~/.vee-check/` (or `$VEE_CHECK_HOME`): `config.json` (defaults),
`history.jsonl`, `reviews/` (no-gate copies of passed quizzes), `log.html` (Learning Log).

**The flow:**
1. Claude spots a new concept and runs `vc.py start "<topic>"`, which creates `pending.json` (gate closes).
2. Claude writes the quiz **content** as JSON to `.vee-check/quizzes/<topic>.json` (plus two small files for an arcade custom scene). The gate lets writes inside `.vee-check/` through.
3. `vc.py build` checks the content, makes the pass code, stamps content + code into the template for the user's `look`, and opens the page. Claude never sees the pass code.
4. The user passes and pastes what the Copy button gave them: `<pass code>.<answer trail>`. Claude runs `vc.py unlock <that>`: if the hash matches, the concept goes into `passed.json`, the answers go into the history, and `pending.json` is removed.
5. Edits are allowed again, and Claude does the actual work.

**About the pass code:** this is a self-imposed gate, not a security system. The code
lives inside the quiz HTML in base64, hidden until the user passes. Don't over-engineer it.

**Arcade custom scenes:** the shell (header, XP, mascot, quiz, pass code) is fixed. Only one
lesson scene is agent-written, it runs with a small `vc` toolkit, it must ship a `fallback`
scene, and if it throws the page shows the fallback. A bad scene can't block the exit.

## Settings (v1)
Stored at `.vee-check/config.json` in the project, with optional global defaults at
`~/.vee-check/config.json` (project wins). Asked once, the first time Vee Check runs in a
project (AskUserQuestion), and changeable anytime with `/vee-check:config` or by just saying
"make it easier", "fewer questions", etc.
```json
{
  "style": "concepts",          // concepts = understand it well enough to explain it to someone (default)
                                //   hands_on = also learn by doing: write a small piece of the code yourself
  "look": "classic",            // classic | arcade | plain: how the quiz page looks and feels (see prototypes/)
  "tracks": ["domain", "architecture", "code"],  // which kinds of concept get lessons and gates
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

## Template library (built)
Reusable interactive pieces that Claude fills with data, so a lesson is hands-on without new
code each time. All work in all three looks (plain shows them as tables or lists).
- **Scenes:** `sort` (into piles), `match` (pairs, with unmatched extras), `flow` (follow one
  thing through the parts), `slider`, `build` (assemble a line), `compare` (before/after).
  Plus the originals: `story`, `steps`, `playground`, `card`.
- **Questions:** `fill` (the blank), `bug` (spot the line), `match` (terms). Plus `predict`,
  `order`, `explain`, `choice`, `expect`.
- The skill says: at least one library scene per lesson; a custom arcade scene only when
  nothing in the library fits.
- Worked example using every template: `examples/pandas-playground/quiz-example-templates/`.
- Ideas not built yet: two-handle slider (for `a[1:4]`), a call-stack scene (recursion), a
  node-and-arrow map for architecture, a "worked calculation" scene for domain math.

## Naming (decided: Vee Check)
The project started as "Vibe Check", but that name is used by other products
(agileforce.co.uk/vibecheck, vibecheck.software, vibe-check.cloud). On 2026-11-25 Patrick
renamed it **Vee Check**, after Vee the mascot, who is also the icon. Plugin id `vee-check`,
commands `/vee-check:...`, state folders `.vee-check/` and `~/.vee-check/`, environment
variables `VEE_CHECK_HOME` and `VEE_CHECK_NO_OPEN`.
- The tagline "Learn as you vibe" and the phrase "vibe coding" stay.
- The GitHub repo was renamed to `PatTheRatch/vee-check` the same day (GitHub redirects the
  old address) and the prototypes now say Vee Check too.
- Only the local folder is still called `vibe-check`. Renaming it has to happen outside a
  Claude Code session, because the session and its saved memory are tied to the folder path.

## Learning tracks: what kind of thing to learn
Not everyone cares about the code. Someone building a portfolio risk platform needs to know how
*the platform* works (how tracking error is computed, where benchmark weights come from, what
happens when a price is missing) without learning how Python works. Every concept gets a track:
- **Domain / logic:** what the system does in business terms (the risk math, the rules, the data flow).
- **Architecture:** how the pieces fit together.
- **Code:** the language, libraries and patterns.
A `tracks` setting (e.g. `["domain","architecture"]`) picks which ones get lessons and gates.
Lessons on the domain track explain *this project's* logic, not textbook theory.

## Review mode: Vee Check as a correctness check (big idea, Patrick's)
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

**First stab, built (tracks + review mode):**
- `tracks` setting; `start --track`, `concepts add --track`; a switched-off track never gates.
- `expect` question type (answer = what the code actually does) and an optional `source` on any question.
- "That's not what it should do" button after any wrong reveal (not on put-in-order). It
  travels back in the pasted code as a `d` mark, is not a miss, and keeps full XP.
- `unlock` prints each POSSIBLE ISSUE; `vc.py issues` and `/vee-check:issues` list them; the
  Learning Log counts them. `/vee-check:check <area>` runs a no-gate review quiz.
- Worked domain example: `examples/pandas-playground/quiz-example-domain/`.
- **Not built yet:** nothing *enforces* that answer keys come from running the code (it is a
  rule in the skill); issues have no open/resolved state; no architecture-track example.

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
- Command idea: `/vee-check:scan` runs the inventory, `/vee-check:tour` replays the tour.

## Depth: how high-level vs. in the weeds (decided)
- Three zoom levels: **What** (what it does and why it's there) → **How** (the moving parts) →
  **Weeds** (the actual lines, edge cases, gotchas). The `concepts` style defaults to What + How.
- **Default + adaptive + zoom:** start at the configured level; go deeper when the user aces
  things and simpler when they miss; every lesson has a "go deeper" button.
- **Concept size rule:** a concept is something you'd explain to a coworker in one sentence when
  they ask why that code is there. "Python" is too big; "f-strings" is too small.
- Store the zoom level reached per concept in the history, so a review picks up there.

## Tracking & review (v1)
Every Vee Check is logged so the user can see what they've covered and go back to it.
- `~/.vee-check/history.jsonl` (global, across all projects): one line per Vee Check with
  date, project, topic, the lesson content, every question with the user's answers, attempts
  and misses, pass/skip, and the quiz file path.
- `.vee-check/passed.json` (per project) stays as the "don't re-quiz" list.
- **Learning Log page**: a generated `~/.vee-check/log.html` listing topics covered (by date and
  project), with a **Review** button per topic that replays the lesson and quiz without gating.
- Commands: `/vee-check:topics` ("what have we covered?") and `/vee-check:review <topic>`.
- Gamification stats (XP, streaks and so on) are computed from the history, not stored separately.

## Build plan (do these one at a time)
- [x] **1. Gate hook:** write `scripts/gate.py`. It reads the hook's JSON on stdin; if `.vee-check/pending.json` exists and the target file isn't inside `.vee-check/`, it exits 2 with a clear message for Claude. Otherwise it exits 0. Test it by piping sample JSON into it.
- [x] **2. CLI:** write `scripts/vc.py` with the start / unlock / skip / status commands, using only the standard library.
- [x] **3. Quiz template:** `templates/quiz.html` as one file with no CDN, so it works on locked-down machines. **Lesson (click-through cards, tiny example, predict-the-output)** → MCQ → retry misses → reveal the pass code. Lengths come from the config. Mobile-friendly.
- [x] **4. Skill:** finish `skills/vee-check/SKILL.md`: when to trigger, how to write good questions (teach before you test; prediction over definitions; respect config for level and counts; first-run setup questions), the step-by-step flow.
- [x] **5. Slash commands:** `/vee-check:skip`, `/vee-check:status`, `/vee-check:config`. `vc.py` reads and writes the config.
- [ ] **6. Test it:** install the plugin locally and use it in `examples/pandas-playground` (for example, "load a CSV into a DataFrame and group by a column"). Fix whatever feels annoying.
  *Partly done: automated tests, browser click-throughs of all three looks, and a fresh agent following the skill cold all pass. Still to do by a person: install the plugin for real, confirm the hook blocks an edit in a live session, and take one whole Vee Check start to finish.*
- [x] **7. README + release:** install steps, a GIF/screenshot, tag v0.1.0.

## Open questions (bring up when you get to them, not before)
- Should the gate also catch `Bash` commands that write files (`>`, `sed -i`, `cat <<EOF`)? Probably yes in v2.
- "Claude spots a new concept" depends on Claude following the skill. Is that good enough, or does a UserPromptSubmit hook need to nudge it?
- Should `passed.json` turn into a "what I've learned" page later?

## Conventions
- Python 3, standard library only, for anything in `scripts/` (corporate machines can be restricted).
- No external JS/CSS in templates.
- Plugin paths use `${CLAUDE_PLUGIN_ROOT}`.
- Commit after each build step with a short message.
