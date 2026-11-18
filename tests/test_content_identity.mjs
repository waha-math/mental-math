// ربط المحاولة بهوية المحتوى على التطبيق (ك1): المشهد نفسه في tests/test_content_identity.py، الحالات 5 إلى 12.
//
//     node tests/test_content_identity.mjs [مجلد app]
//
// البصمات يحسبها المولّد ويتحقق منها التحميل في بايثون (الحالات 1 إلى 4 هناك). التطبيق يقرؤها ولا يحسبها، فالحزمة
// المتغيرة هنا تأخذ بصمة مكتوبة باليد.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const A = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8'));
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const results = [];
const canon = (x) => (Array.isArray(x) ? x.map(canon) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, canon(x[k])])) : x);
function expect(title, got, want) {
  const ok = JSON.stringify(canon(got)) === JSON.stringify(canon(want));
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${title}`);
  if (!ok) console.log(`        ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
}

const TARGET = '1-4-2/gate/04';
const ident = (p) => ({ version: p.version, digest: p.digest });
const B = JSON.parse(JSON.stringify(A));
{
  const it = B.items.find((i) => i.id === TARGET);
  it.answer = (it.answer % 9) + 1;
  it.numbers = { ...it.numbers, n: 10 - it.answer };
  it.fact = [it.answer, 10 - it.answer].sort((x, y) => x - y);
  it.v = 'changed-item';
  B.digest = 'changed-pack';
  B.version = A.version + 1;
}
const IDA = ident(A);
const IDB = ident(B);
const oldIt = A.items.find((i) => i.id === TARGET);
const newIt = B.items.find((i) => i.id === TARGET);
const secs = (w) => (w.activity === 'check' ? 60 : 25);
const ASSESS = ['gate', 'short', 'check', 'retention'];
const pickOf = (pack) => { const s = new ContentSource(pack.items, true, ident(pack)); return (k, w) => s.pick(k, w); };

function build(pack) {
  const eng = new Engine(undefined, { group: 'young' });
  eng.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  const sc = new Scheduler(eng, TYPES, pickOf(pack), null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false, content: ident(pack) });
  return [eng, sc];
}

function answer(st) {
  const [item, w] = st.pending;
  const evs = ['lesson', 'practice'].includes(w.activity) ? [['end']]
    : [['confirm', item.answer], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
  for (const ev of evs) st.event(st.seq, ev);
}

function closedInGate() {
  const [eng, sc] = build(A);
  const st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  while (st.pending[0].id !== '1-4-2/gate/03') answer(st);
  st.show(st.seq);
  return [JSON.parse(JSON.stringify(st.snapshot())), sc.records.length];
}

function reopen(rec, pack, more = {}) {
  return persist.restore(JSON.parse(JSON.stringify(rec)), { types: TYPES, source: pickOf(pack), answer: null,
    item_seconds: secs, records: [], today: null, content: ident(pack), ...more });
}

function gateItems(eng, sc) {
  const st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  const out = {};
  let n = 0;
  while (st.pending !== null && st.pending[0].id.startsWith('1-4-2/gate/') && n < 12) {
    const it = st.pending[0];
    out[it.id] = [it.answer, it.v];
    n += 1;
    answer(st);
  }
  return [out, st];
}

console.log('=== ربط المحاولة بهوية المحتوى، بلغة JavaScript');
const [rec, nBefore] = closedInGate();
expect('5. اللقطة تحمل هوية الحزمة التي بدأت بها المحاولة، والبند المعروض يحمل بصمة تعريفه',
  [rec.scheduler.opts.content, rec.scheduler.opts.content_version, rec.current.journal.v],
  [IDA, IDA.version, A.items.find((i) => i.id === '1-4-2/gate/03').v]);

let r = reopen(rec, A);
expect('6. المحتوى لم يتغير: لا ملاحظة عن المحتوى، والمحاولة على حزمتها',
  [r.notes.filter((n) => n[0].startsWith('content')), r.scheduler.content], [[], IDA]);

r = reopen(rec, B, { packs: { [IDA.digest]: pickOf(A) } });
let [got, st] = gateItems(r.engine, r.scheduler);
expect(`7. المحتوى تغيّر والحزمة القديمة متاحة: البوابة تُكمَل، و${TARGET} يُعرض بجوابه وبصمته القديمين، والمحاولة باقية على حزمتها`,
  [got[TARGET] ?? null, r.scheduler.content, st.snapshot().scheduler.opts.content,
    r.notes.filter((n) => n[0].startsWith('content'))],
  [[oldIt.answer, oldIt.v], IDA, IDA, []]);

const mine = [];
let x = null;
try {
  persist.restore(JSON.parse(JSON.stringify(rec)), { types: TYPES, source: pickOf(B), answer: null, item_seconds: secs,
    records: mine, today: null, content: IDB });
} catch (err) {
  x = err;
}
expect('8. المحتوى تغيّر والحزمة القديمة غير متاحة: يُرفض الاستئناف باسمه، ويُذكر النشاط الجاري، ولا يُمس سجل المستدعي',
  [x instanceof persist.ContentChanged && [x.bound, x.offered, x.pending], mine], [[IDA, IDB, [['gate', '1-4-2']]], []]);

r = reopen(rec, B, { restart: true });
const last = r.scheduler.records[r.scheduler.records.length - 1];
expect('9. إعادة بدء صريحة: ما وقع في البند المعروض يبقى سجلًا مستبعدًا بسببه، وما قبله من السجلات باقٍ، والبوابة تُسقط بمدخل',
  [r.scheduler.records.length, last.item, last.void ?? null, last.unsettled ?? null,
    r.notes.filter((n) => ['void_item', 'content_restart', 'content_changed'].includes(n[0])),
    r.scheduler.log.some((l) => l[1] === 'carry_dropped:content_changed')],
  [nBefore + 1, '1-4-2/gate/03', 'content_changed', true,
    [['void_item', '1-4-2', '1-4-2/gate/03', 'content_changed'], ['content_restart', 'gate', '1-4-2'],
      ['content_changed', IDA.version, IDB.version]], true]);
const snap = JSON.parse(JSON.stringify(persist.snapshot(r.engine, r.scheduler)));
[got, st] = gateItems(r.engine, r.scheduler);
expect(`10. بعدها البوابة تبدأ من الحزمة الجديدة: ${TARGET} بجوابه وبصمته الجديدين، والمحاولة مربوطة بالجديدة`,
  [got[TARGET] ?? null, r.scheduler.content, snap.scheduler.opts.content], [[newIt.answer, newIt.v], IDB, IDB]);
const r2 = reopen(snap, B);
expect('11. اللقطة بعد إعادة البدء تُستعاد بالحزمة الجديدة بلا ملاحظة ولا إسقاط ثانٍ',
  [r2.notes.filter((n) => n[0].startsWith('content') || n[0] === 'void_item'), r2.scheduler.records.length],
  [[], nBefore + 1]);

const [e0, s0] = build(A);
const r3 = reopen(JSON.parse(JSON.stringify(persist.snapshot(e0, s0))), B);
expect('12. المحتوى تغيّر ولا نشاط جارٍ: تُربط المحاولة بالحزمة المتاحة، بملاحظة',
  [r3.scheduler.content, r3.scheduler.content_version, r3.notes.filter((n) => n[0].startsWith('content'))],
  [IDB, IDB.version, [['content_upgraded', IDA.version, IDB.version]]]);
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
