# Vee Check with GitHub Copilot in VS Code

Vee Check was built for Claude Code. This page is how to run it with GitHub Copilot's agent
mode in VS Code, for example on a work machine where the code lives on Bitbucket.

**Status: built from the documentation, not yet run in Copilot.** The pieces below are
tested here as far as they can be without Copilot itself. Expect to need one round of
fixes after the first real try; the last section says what to send back.

## What you need

- VS Code with GitHub Copilot, using **agent mode** in the chat.
- `python3` in the terminal (on Windows, `python`). Version 3.9 or later.
- A copy of this repository on the machine, or a git address VS Code can reach.

## Is a marketplace needed?

No. A marketplace is only a list of plugins. VS Code can install a plugin straight from a
git address or from a folder on disk, and this repository is laid out as a plugin (it also
contains a one-plugin marketplace file, for the places that want one).

## Route A: install it as a plugin (try this first)

This is the same thing you did before with a Bitbucket URL.

1. Put the repository somewhere your work VS Code can reach. Either:
   - push a copy to a Bitbucket repository of your own, or
   - clone it onto the work machine from GitHub, if github.com is reachable there.
2. In VS Code, open the Command Palette and run **Chat: Install Plugin from Source**.
3. Paste the git address (ending in `.git`), or the path of the folder if you cloned it.
4. Reload the window (**Developer: Reload Window**).
5. Open Copilot chat in agent mode and type `/vee-status`.

If `/vee-status` runs and prints the gate and settings, the skills are loaded. Go to
"First real test" below.

## Route B: no plugin system (older VS Code, or plugins switched off by policy)

Clone the repository onto the machine, then from inside it:

```bash
python3 scripts/install_copilot.py
```

That copies the skills into `~/.copilot/skills/` and registers the edit-blocking hook in
`~/.copilot/hooks/vee-check.json`, for you, in every project. Nothing is added to your
employer's repositories. Keep the cloned folder where it is: the copies point back at it.

To set it up for one repository only (this *does* add files under that repo's `.github/`):

```bash
python3 scripts/install_copilot.py --workspace /path/to/repo
```

To remove it:

```bash
python3 scripts/install_copilot.py --uninstall
```

Reload the window afterwards and try `/vee-status`.

## First real test

In a scratch folder with a small data file, in Copilot agent mode, ask for something that
needs a concept you'd want explained, for example:

> Load holdings.csv into a pandas DataFrame and print the total weight per region. I'm new to pandas.

What should happen:

1. Copilot says it is starting a Vee Check and runs a `vc.py start ...` command.
2. It writes a quiz file under `.vee-check/quizzes/` and runs `vc.py build`.
3. A page opens in your browser. Copilot says to pass the quiz and paste the code, and stops.
4. **The gate test:** before pasting the code, tell Copilot "go ahead and write the file
   anyway". The edit should be refused with a message starting "Vee Check: edit blocked".
5. Pass the quiz, press Copy, paste the code into the chat. Copilot runs `vc.py unlock ...`
   and then writes the code.

## What differs from Claude Code

| | Claude Code | Copilot in VS Code |
|---|---|---|
| Slash commands | `/vee-check:vee-skip`, `/vee-check:vee-status`, ... | `/vee-skip`, `/vee-status`, ... |
| Blocking edits | Hook, stable | Hook, marked **preview** by VS Code |
| If the hook is slow or times out | Edit is blocked | **Edit goes through** (Copilot fails open on a timeout) |
| Setup questions | Asked as multiple choice | Asked as multiple choice if `ask_user` is available, otherwise in plain chat |

The lesson pages, the pass code, the Learning Log and all settings are identical. Your
history lives in `~/.vee-check/` on each machine and does not sync between them.

## Things that can stop it at work

- **Hooks or plugins disabled by policy.** Companies can allow only their own hooks
  (`ChatAllowManagedHooksOnly`) or only approved plugins. If the skills load but edits are
  never blocked, this is the likely cause. Vee Check then still teaches and quizzes; it
  just can't *enforce* waiting. Ask whoever manages VS Code settings.
- **The older chat engine.** VS Code is moving from its "Local" agent engine to the "Copilot"
  one. In the older engine, hooks need the `chat.useHooks` setting turned on.
- **`python3` not on the PATH** that VS Code uses. Run `python3 --version` in VS Code's own
  terminal to check.
- **Browser doesn't open.** `build` prints the page's path; open it by hand.

## If something doesn't work: what to send back

The one thing that couldn't be confirmed from the docs is exactly what Copilot sends the
hook when it edits a file. To capture it, in the project you're testing in:

1. Create an empty file named `debug` inside the `.vee-check` folder.
2. Ask Copilot to edit any file.
3. Send back the last few lines of `.vee-check/hook-log.jsonl`.

That file shows the real tool names and fields, which is all that's needed to adjust the
gate. Delete the `debug` file afterwards to stop the logging. Also useful: your VS Code
version (Help → About), and whether Route A or Route B was used.
