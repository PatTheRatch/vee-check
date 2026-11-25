# Starting on a project that already has code

When Vee Check is switched on in a project that already has code, the user hasn't been
quizzed on any of it. Don't gate them on their own existing code. Do this instead, once,
when they ask for a scan or the first time a Vee Check would start in a project that has
code but no concept list (`vc.py concepts` says "No concept list yet").

In every command below, `vc.py` means the script path given in SKILL.md.

## 1. Scan: build the concept list

Read the imports, config files, file types and recurring patterns. List the concepts the
project uses, 6 to 15 of them, and rank each by how much of the code leans on it (1 to 10).

A concept is **something you'd explain to a coworker in one sentence when they ask why that
code is there**. "Python" is too big. "f-strings" is too small. "pandas groupby", "Flask
routes", "environment variables for secrets", "async/await" are the right size.

Put each one in a group and save it:

```bash
python3 "<vc.py>" concepts add "Flask routes" --group tools --weight 8
```

Groups: `big_picture` (how the parts fit together), `tools` (libraries and services),
`techniques` (patterns in the code). New entries start as `learning`: on the learning list,
never gating. Show the user the list with `vc.py concepts` and a one-line summary.

## 2. Project tour: the whole thing first

Before any single concept, one lesson on how the codebase fits together: what talks to
what, where data comes in and where it goes out. The goal is that the user can explain the
project to someone.

```bash
python3 "<vc.py>" start "Project tour" --no-gate
```

Write the content as usual (a `story` of what the project is for, a `steps` scene that walks
one request or one run through the files, 2 or 3 `explain` questions), then `build`.
`--no-gate` means nothing is blocked: carry on working. If the user pastes the code from the
end, run `unlock` so it lands in their Learning Log.

## 3. Placement quiz: skip what they already know

Two quick questions per concept, no lesson. Start it with no gate:

```bash
python3 "<vc.py>" start "Placement quiz" --no-gate
```

In the content, set `"placement": true`, leave `"lesson": []`, and give every question a
`"concept"` that exactly matches a name on the concept list. Up to 10 questions per quiz,
so cover the 5 heaviest concepts first and offer a second round for the rest.

When the user pastes the code, `unlock` sorts it out by itself: a concept whose questions
were both right first time becomes **known** (no lesson, never quizzed), the others stay on
the learning list. This needs the full copied code, not just the short one typed by hand.

## 4. After that: what gates and what doesn't

- A concept **already in the code** never gates by default. It sits on the learning list.
  When the user says "teach me X", run a `--no-gate` lesson on it.
- A concept that is **new to the project** gates as normal.
- The user can make any listed concept gate: `concepts add "<topic>" --status gate`. Treat
  those like new concepts the next time a task touches them.
- The user can mark one as known without a quiz: `concepts add "<topic>" --status known`.
