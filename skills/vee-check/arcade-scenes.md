# Custom scenes for the arcade look

In the `arcade` look, one lesson scene (two at most) can be something you build for this
exact topic: the learner does the concept with their hands instead of reading about it.
The shell around it (header, XP, mascot, quiz, pass code) is fixed, so a custom scene can
be ambitious without risking the gate.

Only write one when the `look` setting is `arcade`, **and only when nothing in the
interactive template library fits** (`sort`, `match`, `flow`, `slider`, `build`, `compare`:
see quiz-format.md). Sorting things into piles, pairing things up, following something
through a system, moving a slider, assembling a line and before/after are all covered
already, need no code, and can't break. A custom scene costs extra tokens every time, so
save it for an interaction the library can't express.

## The idea to aim for

Find the verb in the concept and make the learner perform it.

| Concept | The learner does |
|---|---|
| `groupby` | drags rows into piles by region, then presses a button that sums each pile |
| SQL `JOIN` | drags a row from one table onto its match in the other; unmatched rows stay behind |
| list slicing `a[1:4]` | drags two handles along a row of boxes; the selected boxes light up |
| recursion | presses "call" to stack frames and "return" to pop them, watching the value come back |
| HTTP status codes | sorts responses into 2xx / 4xx / 5xx bins |
| a hook's exit code | flips a switch between 0, 1 and 2 and watches the edit go through or bounce |

Then give it a payoff: a button, a total, a reveal that shows what the code line produces.

## How to write it

A custom scene is a lesson scene with `"type": "custom"`. It counts as one of the lesson's
scenes. Keep the code in two files in the same folder as the quiz JSON, named
`<topic>.scene.html` and `<topic>.scene.js` (`start` prints the names). The file names in
the JSON are relative to that folder. This is much easier than escaping code inside JSON:

```json
{ "type": "custom",
  "title": "You are the groupby: sort each holding into its region pile",
  "html_file": "pandas-groupby.scene.html",
  "js_file": "pandas-groupby.scene.js",
  "fallback": { "type": "steps", "title": "Split, apply, combine", "steps": [ ... ] } }
```

- `html_file`: plain markup, placed inside the scene card under the title. You may include
  a `<style>` block. No `<script>` tags and nothing loaded from the internet.
- `js_file`: runs once, after the markup is on the page, with one variable in scope: `vc`.
- `fallback`: **required.** A normal scene (`steps`, `playground`, `card` or `story`) that
  teaches the same thing. The classic and plain looks use it, and the arcade look switches
  to it if your code throws.
- Inline `"html"` and `"js"` strings also work, for something very small.

The Next button is always there and always works. You never have to unlock it.

`build` checks that the script parses (when `node` is installed) and tells you if it
doesn't. It can't tell whether the scene makes sense, so read your script through once as
the learner: can every button that starts disabled actually become enabled?

## The `vc` toolkit

| Call | What it does |
|---|---|
| `vc.root` | The element holding your markup. Query inside it: `vc.root.querySelector('#sum')`. |
| `vc.dragDrop({items, targets, accepts, onDrop, onReject})` | Makes `items` draggable onto `targets`. Works with mouse, touch, tap-then-tap and keyboard. `accepts(item, target)` returns true or false. `onDrop(item, target)` must move the item into place (for example `target.appendChild(item)`). `onReject(item, target)` is optional. It plays the drop and reject sounds and the shake itself, so don't add your own. Returns `{ place(item, target) }` for a "do it for me" button. |
| `vc.say(text, mood)` | Vee, the mascot, says something. `mood` is `'happy'`, `'sad'` or `''`. |
| `vc.done(text)` | Call when the learner has finished the activity. Makes Next glow; `text` is optional and is said by Vee. |
| `vc.burst(element, count)` | Confetti from an element. |
| `vc.roll(element, from, to, ms, suffix)` | Counts a number up inside an element: `vc.roll(el, 0, 9, 600)`. `suffix` is optional (`'%'`, `' rows'`). |
| `vc.flip(container, change)` | Runs `change()` (which reorders the container's children) and animates each child from its old place to its new one. Works on any container inside `vc.root`, including a `buckets` grid. |
| `vc.sfx.click() / drop() / good() / bad() / nope() / crush() / tick()` | Sound effects. Silent unless the user turned sound on. |
| `vc.calm()` | True when the user asked for no motion. `burst`, `roll` and `flip` already respect it; check it before any animation of your own. |
| `vc.fmt(text)`, `vc.esc(text)` | Turn lesson-style text (backticks, bold) or raw text into safe HTML. |

## Ready-made styles

These classes already look right in the page, so use them before writing CSS:

- Layout and text: `row` (centered button row), `muted`, `small`, `center`, `hl` (highlight a piece of code).
- Buttons: `btn`, `btn ghost`, `pill`. A `disabled` button is dimmed for you, and the
  `hidden` attribute hides any element.
- Code: `<pre>` and `<code>`.
- Drag pieces: `tray` (where items start), `chip` (a draggable item), `buckets` (a grid of
  targets), `bucket` (one target, put a `<div class="pile">` inside for dropped chips),
  `total` (a big result number).
- Group colours: add `g0` to `g5` to a bucket or row.
- Colours for your own CSS: `var(--accent)`, `var(--good)`, `var(--bad)`, `var(--cool)`,
  `var(--muted)`, `var(--line)`, `var(--deep)`, `var(--card)`.

## Rules that keep it safe

1. **Never touch anything outside `vc.root`.** No `document.body`, no header, no quiz, no
   storage, no network. One-off `setTimeout` calls are fine; no `setInterval` or loops
   that keep running after the learner moves on.
2. **No pass code logic.** You don't have the code and must not look for it.
3. **Always offer a way through**: a "Do it for me" button, or accept the learner pressing
   Next without finishing.
4. **Wrong moves teach.** On a reject, say why in one short line (`vc.say`), don't just shake.
5. **Phone-sized screens.** Assume 340px of width. Wrap, don't overflow.
6. **Keep it under about 80 lines of JavaScript.** If it needs more, the idea is too big:
   simplify the interaction, not the code style.
7. **Real numbers.** Any total or result you show must match the lesson's data exactly.

## A complete example

`examples/pandas-playground/quiz-example/` in the plugin holds the groupby scene:
`pandas-groupby.scene.html` (a tray of six chips and three buckets) and
`pandas-groupby.scene.js` (about 35 lines using `vc.dragDrop`, `vc.roll` and `vc.done`).
Read both before writing your first scene, for the shape. Then design your own
interaction for the topic in front of you.
