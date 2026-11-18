// سجل البند وإبطال جلسة على التطبيق (ك2): المشهد نفسه في tests/test_record_audit.py، بالحالات الثماني نفسها.
//
//     node tests/test_record_audit.mjs [مجلد app]
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource, indicators, leftOut } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const A = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8'));
const IDA = { version: A.version, digest: A.digest };
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const ASSESS = ['gate', 'short', 'check', 'retention'];
const secs = (w) => (w.activity === 'check' ? 60 : 25);
const results = [];
const canon = (x) => (Array.isArray(x) ? x.map(canon) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, canon(x[k])])) : x);
const text = (x) => JSON.stringify(canon(x));
function expect(title, got, want) {
  const ok = text(got) === text(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${title}`);
  if (!ok) console.log(`        ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
}
const pickOf = () => { const s = new ContentSource(A.items, true, IDA); return (k, w) => s.pick(k, w); };

function play(sessions = 4) {
  const e = new Engine(undefined, { group: 'young' });
  e.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  const sc = new Scheduler(e, TYPES, pickOf(), null, { group: 'young', scope: ['1-4-1', '1-4-2'], learning: true,
    cap: 240, item_seconds: secs, records: [], retention: false, content: IDA });
  let tick = 1000;
  const st = new Stepper(e, sc, () => { tick += 1; return tick; });
  st.open(sc.g_run(20));
  let asked = false;
  let k = 0;
  const ended = () => e.s.order.filter((s) => e.s.sessions[s].ended).length;
  while (st.pending !== null && ended() < sessions) {
    const [item, w] = st.pending;
    const sibling = e.s.order.length === 1;
    k += 1;
    let evs;
    if (['lesson', 'practice'].includes(w.activity)) evs = [['end']];
    else if (e.s.order.length >= 2 && ASSESS.includes(w.activity) && !asked) { evs = [['support', 'requested']]; asked = true; }
    else evs = [['confirm', item.answer + (sibling && k === 2 ? 1 : 0)], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
    for (const ev of evs) st.event(st.seq, ev);
  }
  return [e, sc, st];
}

console.log('=== سجل البند وإبطال جلسة، بلغة JavaScript');
const [e, sc, st] = play();
const T = e.s.order[0];
const mine = sc.records.filter((r) => r.session === T);
const others = sc.records.filter((r) => r.session !== T);
expect('1. كل سجل يحمل معرّفًا لا يتكرر، وجلسته، وإصدار حزمته، والجواب الذي صُحّح به، وقيم إجاباته، ووقته',
  [new Set(sc.records.map((r) => r.id)).size === sc.records.length, sc.records.slice(0, 3).map((r) => r.id),
    sc.records.every((r) => e.s.order.includes(r.session)), [...new Set(sc.records.map((r) => r.pack))],
    sc.records.every((r) => 'key' in r && 'values' in r && 'support' in r && 'v' in r && r.at),
    mine.length > 3 && others.length > 3],
  [true, ['i0', 'i1', 'i2'], true, [IDA.version], true, true]);
const helped = others.filter((r) => r.support.length);
expect('2. ما وقع محفوظ بقيمه: في جلسة الأخ إجابة البند الثاني الجواب زائد واحد والباقي الجواب نفسه، وطلب صاحب الملف المساعدة بنوعه وبلا إجابة',
  [mine.map((r) => r.values[0] - r.key), mine.slice(0, 3).map((r) => r.first),
    helped.map((r) => [r.support, r.values, r.session !== T])],
  [[0, 1, ...Array(mine.length - 2).fill(0)], [true, false, true], [[['requested'], [], true]]]);
const byId = Object.fromEntries(A.items.map((i) => [i.id, i]));
expect('3. بصمة البند في سجله هي بصمة تعريفه في الحزمة، والجواب المحفوظ جوابه فيها',
  sc.records.every((r) => r.v === byId[r.item].v && r.key === byId[r.item].answer), true);

const before = sc.indicators();
const nRecords = sc.records.length;
const snapBefore = text(sc.records);
const r = e.apply({ id: 'inv-1', type: 'invalidate_session', target: T });
const after = sc.indicators();
const doneT = mine.filter((x) => !x.void && x.status === 'complete');
expect('4. إبطال الجلسة بعد اكتمالها: مؤشر الإجابة الأولى ينقص مقامه بعدد بنودها المكتملة وبسطه بما صحّ منها، والمؤشرات هي مؤشرات بقية السجلات',
  [r.ok, doneT.length > 0, before.first_answer.den - after.first_answer.den,
    before.first_answer.num - after.first_answer.num, text(after) === text(indicators(others)), text(after) !== text(before)],
  [true, true, doneT.length, doneT.filter((x) => x.first).length, true, true]);
expect('5. التاريخ باقٍ للمراجعة: السجلات كلها كما هي بقيمها، والمستبعد معدود بسببه',
  [sc.records.length, text(sc.records) === snapBefore, sc.left_out()],
  [nRecords, true, { void: 0, session: mine.length, unlinked: 0 }]);
const r2 = e.apply({ id: 'inv-2', type: 'invalidate_session', target: T });
expect('6. إعادة الإبطال تُرفض ولا تضاعف الأثر', [r2.ok, text(sc.indicators()) === text(after)], [false, true]);
const back = persist.restore(JSON.parse(JSON.stringify(st.snapshot())), { types: TYPES, source: pickOf(), answer: null,
  item_seconds: secs, records: [], today: null, content: IDA });
expect('7. بعد حفظ واستعادة: المؤشرات والمستبعد كما هما، والسجلات المنتهية بقيمها',
  [text(back.scheduler.indicators()) === text(after), back.scheduler.left_out().session,
    text(back.scheduler.records.slice(0, nRecords)) === text(sc.records.slice(0, nRecords))],
  [true, mine.length, true]);
const bare = sc.records.map((x) => { const { session, ...rest } = x; return rest; });
expect('8. سجلات بلا معرّف جلسة لا تُنسب تخمينًا: تبقى في المؤشرات، ويُذكر عددها',
  [text(indicators(bare, [T])) === text(before), leftOut(bare, [T])], [true, { void: 0, session: 0, unlinked: nRecords }]);
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
