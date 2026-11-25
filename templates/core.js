// Vibe Check core: shared by every look. build stamps this into the page.
// It owns the parts that must never break: reading the quiz data, the quiz
// rules (retry misses, pass bar), the pass code and the answer trail.
const VC = (() => {
  let data = null;
  try { data = JSON.parse(document.getElementById('vc-data').textContent); } catch (e) { data = null; }

  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // Lesson text is plain text with two extras: `code` and **bold**.
  const fmt = s => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
  // Code lines can mark the part to look at with [[double brackets]].
  const code = s => esc(s).replace(/\[\[(.+?)\]\]/g, '<span class="hl">$1</span>');

  const passCode = () => { try { return data && data.code ? atob(data.code) : ''; } catch (e) { return ''; } };

  // "order" questions list their items in the right order; the page shows them
  // scrambled the same way every time, and never already solved.
  function scramble(n, seed) {
    const a = Array.from({ length: n }, (_, i) => i);
    let s = (seed * 9301 + 49297) % 233280;
    for (let i = n - 1; i > 0; i--) { s = (s * 9301 + 49297) % 233280; const j = Math.floor(s / 233280 * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    if (n > 1 && a.every((v, i) => v === i)) a.push(a.shift());
    return a;
  }

  class Quiz {
    constructor() {
      this.qs = (data && data.questions) || [];
      const bar = data && data.pass_bar;
      this.need = Number.isInteger(bar) ? Math.max(1, Math.min(bar, this.qs.length)) : this.qs.length;
      this.queue = this.qs.map((_, i) => i); this.retry = []; this.round = 1; this.pos = 0;
      this.trail = this.qs.map(() => []);   // every answer given, per question
      this.right = new Set();
      this.disputed = new Set();
    }
    get index() { return this.queue[this.pos]; }
    get question() { return this.qs[this.index]; }
    // mark: the option number picked ("0".."8"), or "y"/"n" for an order question
    record(qi, mark, ok) { this.trail[qi].push(String(mark)); if (ok) this.right.add(qi); else if (!this.retry.includes(qi)) this.retry.push(qi); }
    // Move on. Returns "question", "retry" (a new round of the missed ones) or "done".
    next() {
      this.pos++;
      if (this.round > 1 && this.right.size >= this.need) return 'done';
      if (this.pos < this.queue.length) return 'question';
      if (this.right.size >= this.need || !this.retry.length) return 'done';
      this.queue = this.retry; this.retry = []; this.round++; this.pos = 0;
      return 'retry';
    }
    // "That's not what it should do": a possible bug in the code, not a miss. Marked "d" in the trail.
    dispute(qi) { this.trail[qi].push('d'); this.disputed.add(qi); this.right.add(qi); this.retry = this.retry.filter(x => x !== qi); }
    clean(i) { return this.disputed.has(i) || this.trail[i].length === 1; }
    firstTry() { return this.qs.filter((_, i) => this.right.has(i) && this.clean(i)).length; }
    xp() { return this.qs.reduce((n, _, i) => n + (this.right.has(i) ? (this.clean(i) ? 20 : 10) : 0), 0); }
    // What the Copy button gives: the pass code, a dot, then the answer trail.
    resultCode() { return passCode() + '.' + this.trail.map(a => a.join('') || 'x').join('-'); }
  }

  function copy(text, button, doneText) {
    const fail = () => { button.textContent = 'Select it and copy'; };
    try { navigator.clipboard.writeText(text).then(() => { button.textContent = doneText || 'Copied'; }, fail); } catch (e) { fail(); }
  }

  return { data, esc, fmt, code, passCode, scramble, Quiz, copy };
})();
