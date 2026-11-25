// The learner does the "split" by hand, then presses a button for "apply + combine".
const one = s => vc.root.querySelector(s), all = s => [...vc.root.querySelectorAll(s)];
const sums = { Europe: 9, Asia: 8, EM: 3 };
let placed = 0;

const board = vc.dragDrop({
  items: all('.chip'),
  targets: all('.bucket'),
  accepts: (chip, bucket) => chip.dataset.k === bucket.dataset.k,
  onDrop: (chip, bucket) => {
    bucket.querySelector('.pile').appendChild(chip);
    bucket.querySelector('.sumline').textContent = [...bucket.querySelectorAll('.chip')].map(c => c.dataset.w).join(' + ');
    if (++placed === 6) {
      one('#sum').disabled = false;
      one('#auto').hidden = true;
      vc.say('That was the split. Nothing is added up yet.', 'happy');
    }
  },
  onReject: chip => vc.say(`${chip.dataset.t} says ${chip.dataset.k}, so it goes in the ${chip.dataset.k} pile.`, 'sad'),
});

one('#auto').onclick = () => {
  one('#auto').disabled = true;
  all('#tray .chip').forEach((chip, i) => setTimeout(() => board.place(chip, one(`.bucket[data-k="${chip.dataset.k}"]`)), i * 250));
};

one('#sum').onclick = () => {
  one('#sum').disabled = true;
  one('#gcode').innerHTML = "df.groupby('region')<span class=\"hl\">['weight'].sum()</span>";
  all('.bucket').forEach((bucket, i) => setTimeout(() => {
    bucket.querySelector('.sumline').textContent += ' =';
    bucket.querySelector('.pile').innerHTML = '<div class="total">0%</div>';
    vc.roll(bucket.querySelector('.total'), 0, sums[bucket.dataset.k], 600, '%');
    vc.burst(bucket);
    vc.sfx.crush();
    if (i === 2) vc.done('Split, apply, combine. That is the whole trick.');
  }, i * 450));
};
