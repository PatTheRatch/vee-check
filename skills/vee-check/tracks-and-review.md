# Tracks and review mode

## Tracks: what kind of thing the user wants to learn

Not everyone cares about the code. Someone building a portfolio risk platform may need to
know how *the platform* works without learning how Python works. Every concept belongs to
one track:

| Track | The concept is about | Examples |
|---|---|---|
| `domain` | what the system does in business terms: the rules, the math, the data flow | how tracking error is computed here, where benchmark weights come from, what happens when a price is missing |
| `architecture` | how the pieces fit together | which service calls which, where data is stored, what runs on a schedule |
| `code` | the language, libraries and patterns | pandas groupby, async/await, decorators |

The `tracks` setting lists the tracks the user wants (`vc config set tracks domain,architecture`).
Say which track a concept is on when you start: `vc start "<topic>" --track domain`. If that
track is switched off, `start` says so and opens no gate: get on with the work. Without
`--track`, the concept's track from the concept list is used, else `code`.

When you scan a project, give each concept a track as well as a group:
`vc concepts add "tracking error" --group techniques --track domain --weight 9`.

### Writing a domain-track lesson

- **Teach this project's logic, not textbook theory.** "Tracking error is the standard
  deviation of active returns" is a textbook. "Here, `risk.py` takes daily active returns
  for the last 250 days and does *not* annualize" is a lesson.
- **Use the project's own names and numbers**: real column names, a few real rows, the real
  function name. Never mention language syntax unless the `code` track is also on.
- **No code blocks** unless they help. Describe the step in words and show the data before
  and after. A `steps` scene that follows one number through the calculation is the
  natural shape.
- **Ask what a colleague would ask**: "45% of what?", "what happens if a price is missing?".

A complete domain-track example ships in the plugin at
`examples/pandas-playground/quiz-example-domain/region-shares.json` (the folder path prefix is
in SKILL.md). It explains what `portfolio.py` computes without teaching any pandas.

## Review mode: the quiz as a check on the code

A Vee Check can find bugs. If the user's understanding and the code disagree, either the
user learns something **or the code is wrong**. Three rules make that work.

### 1. Answer keys come from the code, not from what you believe

For every question about what the code does, get the answer from the code itself:

- **Run it** on the lesson's example data whenever you can, and use the real output.
- If it can't be run, **read the exact lines** and trace them by hand.
- Put where the answer came from in the question's `"source"` field: `"risk.py:42"`. The
  page shows it next to the reveal.

Never write an answer key from memory of how a library or formula usually behaves.

### 2. Ask what the user expects before showing what the code does

The `expect` question type does this:

```json
{ "type": "expect",
  "prompt": "One holding in the file has a blank weight. What should the script do?",
  "source": "portfolio.py:7",
  "options": ["Stop with an error", "Quietly leave that holding out and carry on", "Count it as the average weight"],
  "answer": 1,
  "why": "`sum` skips blank values without saying anything, so the holding drops out and nothing looks wrong." }
```

`answer` is **what the code actually does**, which may not be what it *should* do. Write the
other options as things a sensible person might expect. Good expectation questions sit on
edges: missing data, zero, duplicates, units, rounding, "does this add up to 100%?",
"is this annualized?". Include one or two in any domain-track quiz.

### 3. "That's not what it should do" is a possible bug, not a miss

After any reveal the user disagrees with, the page offers a button: **That's not what it
should do**. Pressing it doesn't count against them. When they paste the code, `unlock`
prints each one:

```
POSSIBLE ISSUE (question 2): One holding in the file has a blank weight. What should the script do?
  The user expected: Stop with an error
  The code does:     Quietly leave that holding out and carry on   [portfolio.py:7]
```

When you see that, **before doing anything else**:

1. Take the user's expectation seriously. They often know the domain better than the code does.
2. Re-read the source lines and decide: is the code wrong, or is the expectation?
3. Tell the user in two or three lines what you found and what you'd change. If the code
   is wrong, offer the fix and ask before making it. If the code is right, explain why in
   plain words.

`vc issues` lists everything flagged in this project. The Learning Log counts them.

### Running a review on purpose

When the user asks to check or review part of the code ("check the risk calc with me"),
run a no-gate quiz made mostly of `expect` questions:

```bash
vc start "<area> review" --no-gate --track domain
```

Read the code first, run it on a small example, write 3 to 6 expectation questions on the
places where it makes a choice someone could disagree with, then `build`. Follow up on every
possible issue as above.
