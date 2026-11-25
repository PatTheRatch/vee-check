# Quiz content format

You write one JSON file per Vibe Check. `start` prints the exact path
(`.vibe-check/quizzes/<topic>.json`). `build` checks it, tells you what to fix, and turns it
into the page. A complete worked example ships with the plugin; SKILL.md gives its path.

```json
{
  "badge": "🧩",
  "zoom": "how",
  "lesson": [ ...scenes... ],
  "questions": [ ...questions... ]
}
```

- `badge`: optional, one emoji for the topic. Shown when the user passes and on the Learning Log.
- `zoom`: the depth you actually wrote this at (`what`, `how` or `weeds`). Leave it out to use the setting.
- `lesson`: as many scenes in total as the `lesson_cards` setting says (a custom scene counts as one). Empty if the `lesson` setting is off.
- `questions`: as many as the `questions` setting says.

## Text rules

Every text field is plain text with two extras: `` `backticks` `` for code and `**bold**`.
No HTML (it is shown as typed). In any `code` field, in scenes and questions alike, wrap
the part to look at in `[[double brackets]]` to highlight it:
`"df.[[groupby('region')]]['weight'].sum()"`. Use `\n` for line breaks in code and output.

Any scene can carry `"deeper"`: an optional short paragraph one depth level below the
lesson, shown behind a "Go deeper" button.

## Lesson scenes

Mix the types: no more than two scenes of the same type in one lesson. A good order is a
story first, then the scene where the concept happens (a step-through, or the custom scene
in the arcade look), then a playground. Fill any remaining slots with `card` scenes: a
prerequisite the user needs first, or one gotcha worth knowing.

### `story`: a real situation the concept solves

```json
{ "type": "story", "title": "\"What's our total weight in each region?\"",
  "from": "PM",
  "messages": ["Quick one before the 2pm: what's our total weight in each region?", "Holdings attached 👇"],
  "table": { "columns": ["ticker", "region", "weight"], "rows": [["AAA", "Europe", "5%"], ["BBB", "Asia", "3%"]] },
  "body": "Adding by hand works for 6 rows, not for 600. pandas does it in one line with `groupby`." }
```

`from` is who is asking (2 to 4 letters works best: PM, Sam, You). `messages` arrive as chat
bubbles. `table` and `body` are optional.

### `steps`: watch the data change as the code runs

```json
{ "type": "steps", "title": "Split, apply, combine",
  "steps": [
    { "text": "Here's `df`: six holdings.", "code": "df",
      "table": { "columns": ["ticker", "region", "weight"], "rows": [["AAA", "Europe", "5"], ["BBB", "Asia", "3"]] } },
    { "text": "**Split.** pandas tags each row with its group.", "code": "df.[[groupby('region')]]",
      "table": { "columns": ["ticker", "region", "weight"], "rows": [["AAA", "Europe", "5"], ["BBB", "Asia", "3"]],
                 "groups": ["Europe", "Asia"] } }
  ] }
```

Each step needs `text`; `code` and `table` are optional. Two things make the animation work:

- The **first cell of each row is its identity**. Keep it the same across steps and the row
  slides to its new position instead of popping in.
- `groups` has one label per row. Rows with the same label get the same colour.

### `playground`: change a setting, see the result change

```json
{ "type": "playground", "title": "Change it up and watch the result",
  "controls": [
    { "name": "group by", "label": "group by ", "options": ["region", "sector"] },
    { "name": "function", "options": ["sum", "mean"] }
  ],
  "results": {
    "region|sum":  { "code": "df.groupby('[[region]]')['weight'].[[sum]]()",  "rows": [["Europe", 9], ["Asia", 8]], "say": "It adds up the weights in each region." },
    "region|mean": { "code": "df.groupby('[[region]]')['weight'].[[mean]]()", "rows": [["Europe", 4.5], ["Asia", 4.0]], "say": "It averages the weights in each region." },
    "sector|sum":  { "code": "...", "rows": [["Tech", 7], ["Banks", 4]], "say": "..." },
    "sector|mean": { "code": "...", "rows": [["Tech", 3.5], ["Banks", 2.0]], "say": "..." }
  } }
```

You work out every result ahead of time. `results` needs **one entry for every combination**
of options, keyed by the chosen options joined with `|` in control order. If the second value
in every row is a number, the page draws bars; otherwise it shows the rows as a table. Add
`"unit": "%"` to a result to put a unit after the numbers. Keep it to 12 combinations or fewer.

### `card`: a short idea, optionally with "predict then run"

```json
{ "type": "card", "title": "A DataFrame is a table", "body": "Rows and named columns, like a SQL table.",
  "code": "df.shape", "output": "(6, 4)" }
```

With `output`, the user is asked to decide what the code prints before pressing "Run it".

### `custom`: a scene you build for this topic (arcade look only)

See [arcade-scenes.md](arcade-scenes.md). It must include a `fallback` scene of one of the
types above, which the classic and plain looks use, and which the arcade look falls back to
if your code fails.

## Questions

Every question needs `type`, `prompt` and `why`. `why` is the explanation shown after
answering, right or wrong, so it must teach: say why the right answer is right **and** why
the tempting wrong one is wrong.

```json
{ "type": "predict", "prompt": "What does this give you?",
  "code": "df.groupby('region')['weight'].mean()",
  "options": ["Europe    9\nAsia      8", "Europe    4.5\nAsia      4.0", "3.33"],
  "answer": 1, "why": "`mean` averages each group. 9 / 8 is what `sum` would give." }

{ "type": "order", "prompt": "Put the steps of this line in order.",
  "code": "df.groupby('region')['weight'].sum()",
  "items": ["Split the rows into piles by region", "Add up the weight in each pile", "Combine the totals into one table"],
  "why": "Split, apply, combine." }

{ "type": "explain", "from": "Sam",
  "prompt": "hey, what does `df.groupby('sector')['weight'].sum()` actually do?",
  "options": ["It sorts the table by sector.", "It adds up the weight for each sector, one total per sector.", "It removes duplicate sectors."],
  "answer": 1, "thanks": "Ohh, one total per sector. Thanks!",
  "why": "groupby plus sum gives one total **per group**. Sorting does no math." }

{ "type": "choice", "prompt": "Which of these would need groupby?", "options": ["...", "..."], "answer": 0, "why": "..." }
```

- `answer` is the position of the right option, **counting from 0**. Vary it: don't always
  put the right answer in the same slot.
- `predict`: options are possible outputs, shown in monospace. Use `\n` for line breaks.
- `order`: write `items` in the **correct** order. The page scrambles them.
- `explain`: a coworker asks, the user picks the best plain-English reply. `from` and
  `thanks` (the coworker's reply to the right answer) are optional. This is the core
  question type for the `concepts` style: include at least one.
- 2 to 9 options or items. `code` is optional on every type.
- For a placement quiz, add `"placement": true` at the top level and a `"concept": "<name>"`
  on every question (see the skill's section on existing projects).

## What good content looks like

- **Teach before you test.** Every question must be answerable from the lesson alone.
- **Prediction over definitions.** "What does this return?" beats "What is groupby?".
- **One concrete, tiny dataset** carried through the whole lesson and quiz (6 rows, not 60).
  Use the user's real domain and column names when you know them.
- **Wrong options are real mistakes** a learner would make, not jokes.
- **Check your own answers.** Work out every `results` entry and every `predict` option by
  hand or by running the code. A wrong answer key is worse than no quiz.
- **Show what the code really prints**: the same values, units and row order as the real
  output. (pandas `groupby` lists groups in sorted order, for example.) If the user's data
  has bare numbers, don't add a `%`.
