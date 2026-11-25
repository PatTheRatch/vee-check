# pandas playground

A scratch project for trying Vee Check.

- `holdings.csv`: six rows of sample data.
- `quiz-example/`: a complete, hand-checked Vee Check on pandas groupby. It is the worked
  example the skill points Claude at: the quiz content (`pandas-groupby.json`) and the
  custom scene used by the arcade look (`pandas-groupby.scene.html`, `pandas-groupby.scene.js`).

## Try it

Open Claude Code in this folder with the plugin loaded and ask:

> Load holdings.csv into a DataFrame and print the total weight per region.

## Build the example page yourself, without Claude

```bash
python3 ../../scripts/vc.py start "pandas groupby"
```

```bash
cp quiz-example/* .vee-check/quizzes/
```

```bash
python3 ../../scripts/vc.py build
```

Change the look first with `python3 ../../scripts/vc.py config set look classic` (or `plain`, `arcade`).
When you're done, `python3 ../../scripts/vc.py skip` opens the gate again.
