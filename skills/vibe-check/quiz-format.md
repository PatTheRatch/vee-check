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

## The interactive template library

Six more scene types where the learner *does* something. They work in every look (the
plain look shows the same content as a table or list), cost only data, and are tested, so
reach for these before writing a custom scene.

| Type | The learner | Fits concepts about |
|---|---|---|
| `sort` | drags items into the pile each belongs to | grouping, classifying, filtering, categories |
| `match` | drags each item onto its partner | joins, keys and values, terms and meanings |
| `flow` | steps one thing through the parts of a system | requests, pipelines, how a number gets computed, architecture |
| `slider` | moves one setting and watches the effect | slicing, limits, thresholds, "what changes as n grows" |
| `build` | assembles a line of code from pieces | syntax order, method chains, SQL clause order |
| `compare` | flips between before and after | what one operation does to the data |

A complete quiz using all of them is in the plugin's
`examples/pandas-playground/quiz-example-templates/template-tour.json`.

### `sort`: put each item in its pile

```json
{ "type": "sort", "title": "Whose fault is this status code?",
  "body": "The first digit tells you who has to fix it.",
  "items": [
    { "label": "200", "detail": "OK", "group": "It worked" },
    { "label": "404", "detail": "Not found", "group": "The request was wrong" },
    { "label": "500", "detail": "Server error", "group": "The server broke" }
  ],
  "groups": ["It worked", "The request was wrong", "The server broke"],
  "result": { "button": "Show the pattern",
              "per_group": { "It worked": "2xx", "The request was wrong": "4xx", "The server broke": "5xx" },
              "say": "**2xx** worked, **4xx** means fix the request, **5xx** means fix the server." } }
```

`items` need `label` and `group`; `detail` is optional. `groups` sets the pile order (leave
it out to use the order groups first appear). `result` is optional: a button that replaces
each pile with its `per_group` value, for "split, then compute" ideas such as groupby. It
can also carry `code` to show the finished line. 4 to 8 items and 2 to 4 groups work best.

### `match`: pair things up

```json
{ "type": "match", "title": "Which customer does each order belong to?",
  "left_title": "orders", "right_title": "customers",
  "pairs": [
    { "left": "Order 1, customer 7", "right": "7: Ada" },
    { "left": "Order 2, customer 9", "right": "9: Grace" },
    { "left": "Order 3, customer 7", "right": "7: Ada" }
  ],
  "extras": { "left": ["Order 4, customer 42"], "right": ["11: Linus"] },
  "say": "An inner join keeps only the pairs. Order 4 and Linus drop out." }
```

Several lefts may share one right (written identically): it appears once. `extras` are
items with no partner on either side, which is exactly how to show what a join drops.

### `flow`: follow one thing through the system

```json
{ "type": "flow", "title": "What happens when Claude tries to edit a file",
  "nodes": [ { "label": "Claude", "detail": "wants to edit" }, { "label": "The hook", "detail": "gate.py" },
             { "label": "pending.json", "detail": "the lock file" } ],
  "steps": [
    { "at": 0, "text": "Claude decides to edit `app.py`.", "value": "Edit app.py" },
    { "at": 1, "text": "Claude Code hands the request to the hook first.", "value": "{ \"tool_name\": \"Edit\" }" },
    { "at": 2, "text": "The hook checks whether the lock file exists.", "value": "pending.json exists" },
    { "at": 1, "text": "It does, so the hook exits with code **2**: block.", "value": "exit 2" }
  ] }
```

`nodes` are the parts, in a sensible reading order (3 to 5). Each step sits `at` one node
(counting from 0) and may revisit a node. `value` is optional: what the thing being followed
looks like at that moment. This is the natural scene for **domain** and **architecture**
lessons: follow one number, one request or one record.

### `slider`: move a setting, watch the effect

```json
{ "type": "slider", "title": "How far does a slice reach?", "label": "n", "start": 2,
  "cells": ["a", "b", "c", "d", "e"],
  "positions": [
    { "label": "0", "code": "letters[:[[0]]]", "highlight": [],     "say": "Nothing: it stops before position 0." },
    { "label": "1", "code": "letters[:[[1]]]", "highlight": [0],    "say": "Just `a`." },
    { "label": "2", "code": "letters[:[[2]]]", "highlight": [0, 1], "say": "`a` and `b`. Position 2 is not included." }
  ] }
```

One entry in `positions` per slider stop, each with a `label` and a `say`. `cells` is an
optional row of boxes; `highlight` lists which boxes (counting from 0) light up at that
stop. `code` is optional. Without `cells` it works as a plain "setting → result" explorer.

### `build`: assemble the line

```json
{ "type": "build", "title": "Assemble the line that totals weight by region",
  "pieces": ["df", ".groupby('region')", "['weight']", ".sum()"],
  "extras": [".sort()", "['region']"],
  "say": "Table, then split by region, then the weight column, then add each pile up." }
```

`pieces` are in the **correct** order; the page shuffles them together with `extras`
(wrong pieces that are tempting). 3 to 6 pieces. Each piece should be one idea.

### `compare`: before and after

```json
{ "type": "compare", "title": "What sorting does to the table",
  "code": "df.sort_values('weight', ascending=False)",
  "before": { "columns": ["ticker", "weight"], "rows": [["AAA", "5"], ["BBB", "3"], ["CCC", "4"]] },
  "after":  { "columns": ["ticker", "weight"], "rows": [["AAA", "5"], ["CCC", "4"], ["BBB", "3"]] },
  "say": "Same rows, new order. Nothing was added or removed." }
```

Two tables in the same shape as a `steps` table. Rows with the same first cell slide to
their new place; rows that exist on only one side appear or disappear.

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

{ "type": "expect", "prompt": "One holding has a blank weight. What should the script do?",
  "source": "portfolio.py:7",
  "options": ["Stop with an error", "Quietly leave it out and carry on"],
  "answer": 1, "why": "`sum` skips blank values without saying anything." }
```

- `answer` is the position of the right option, **counting from 0**. Vary it: don't always
  put the right answer in the same slot.
- `expect`: asks what the user expects before revealing what the code does. `answer` is what
  the code **actually** does. See tracks-and-review.md.
- `source`: optional on any question, the file and line the answer came from (`"risk.py:42"`).
  Use it whenever the question is about the project's own code.
- `predict`: options are possible outputs, shown in monospace. Use `\n` for line breaks.
- `order`: write `items` in the **correct** order. The page scrambles them.
- `explain`: a coworker asks, the user picks the best plain-English reply. `from` and
  `thanks` (the coworker's reply to the right answer) are optional. This is the core
  question type for the `concepts` style: include at least one.
- 2 to 9 options or items. `code` is optional on every type.
- For a placement quiz, add `"placement": true` at the top level and a `"concept": "<name>"`
  on every question (see the skill's section on existing projects).

### Three more question types

```json
{ "type": "fill", "prompt": "Fill the blank so this gives the average weight per region.",
  "code": "df.groupby('region')['weight'].___()",
  "options": ["sum", "mean", "count", "avg"], "answer": 1,
  "why": "`mean` is pandas' word for average. There is no `avg` in pandas." }

{ "type": "bug", "prompt": "This should print the total weight per region. Which line has the bug?",
  "lines": ["import pandas as pd", "df = pd.read_csv('holdings.csv')",
            "totals = df.groupby('weight')['region'].sum()", "print(totals)"],
  "answer": 2, "why": "The two column names are swapped." }

{ "type": "match", "prompt": "Match each status code to what it means.",
  "pairs": [ { "left": "404", "right": "The request asked for something that isn't there" },
             { "left": "500", "right": "The server broke while handling it" },
             { "left": "200", "right": "It worked" } ],
  "why": "2xx worked, 4xx is the request's problem, 5xx is the server's." }
```

- `fill`: `code` must contain `___` (three underscores) where the blank goes. `options` are
  what could go there. Good for the one piece of a line that carries the meaning.
- `bug`: `lines` are the lines of a short snippet (2 to 9); `answer` is the position of the
  broken line, counting from 0. Exactly one line should be wrong, and wrong in a way the
  lesson taught. Good for reading code critically.
- `match`: 2 to 9 `pairs`, each right side different. The page scrambles the right side.
  Good for vocabulary. (This is the question; the `match` *scene* above is the lesson version.)

Which to use: `predict` and `expect` for behaviour, `fill` and `build` for syntax, `bug`
for reading code, `order` for sequence, `match` for vocabulary, `explain` for the big idea.

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
