// الفحص الوصفي للمقارنة. القاعدة والتوقعات في tests/test_describe.py، والمساران يُطابَقان بشريط المرجع
// tests/describe_tape.json: ما عُرض والحالة الدائمة كاملة، والثاني بإغلاق أثناء الفحص.
//
//     node tests/test_describe.mjs [مجلد app]
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine, canonical } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const BY = new Map(ITEMS.map((i) => [i.id, i]));
const DESC = ITEMS.filter((i) => i.role === 'descriptive_check').map((i) => i.id);
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const TAPE = JSON.parse(readFileSync(new URL('./describe_tape.json', import.meta.url), 'utf8'));
const results = [];
const dump = (x) => canonical(x ?? null);
function check(title, got, want) {
  const ok = dump(got) === dump(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${title}`);
  if (!ok) console.log(`        المتوقع ${dump(want).slice(0, 500)}\n        الناتج  ${dump(got).slice(0, 500)}`);
}
console.log('=== الفحص الوصفي للمقارنة، التطبيق');
const st0 = new Stepper(null, null);
const allowed = (ev) => { st0.pending = [BY.get(DESC[0]), { activity: 'describe', role: 'descriptive_check', pos: 0 }]; st0.raw = []; return st0.allowed(ev); };
check('عقد الحدث كما في المرجع',
  [allowed(['confirm', 'A']), allowed(['confirm', 'same']), allowed(['confirm', 3]), allowed(['confirm', 'C']),
    allowed(['support', 'requested']), allowed(['support', 'hint']), allowed(['end'])],
  [null, null, 'بند البطاقة يُجاب ببطاقة', 'بطاقة ليست من بطاقات البند', null,
    'بند التقييم يقبل طلب «أحتاج مساعدة» (requested) وحده', 'بند التقييم ينتهي بالتأكيد أو بطلب المساعدة']);

// طفل test_phase0: يعرف المهارة بعد أن يرى درسها
const known = new Set();
const events = (item, w) => {
  const a = w.activity;
  if (a === 'lesson' || a === 'practice') { if (a === 'lesson') known.add(item.skill); return [['end']]; }
  const ans = known.has(item.skill) ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1);
  return [['confirm', ans], ...(['gate', 'short', 'check', 'retention', 'describe'].includes(a) ? [] : [['end']])];
};
const src = () => { const s = new ContentSource(ITEMS); return (k, w) => s.pick(k, w); };
function fresh() {
  known.clear();
  const e = new Engine(undefined, { group: 'older' });
  [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]].forEach(([skill, bypass], k) =>
    e.apply({ id: 'd' + k, type: 'teacher_open', skill, bypass, reason: 'قرار الشريحة في 10.2' }));
  const sc = new Scheduler(e, TYPES, src(), null, { group: 'older', scope: new Set(['3-5-1', '3-5-2', '3-5-3']), learning: true,
    cap: 600, item_seconds: () => 45, records: [], retention: true, day_cap: 3000 });
  return { e, sc, trace: [] };
}
function run(r, gen, d, stopAt = null) {
  r.sc.today = d;
  const st = new Stepper(r.e, r.sc);
  st.open(gen);
  while (st.pending !== null) {
    const [item, w] = st.pending;
    r.trace.push([d, r.sc.cur, item.id, w.activity]);
    st.show(st.seq);
    if (item.id === stopAt) return st.snapshot();
    for (const ev of events(item, w)) if (st.event(st.seq, ev) === 'rejected') throw new Error(st.reject);
  }
  return null;
}
const fin = (r) => JSON.parse(dump({ ...persist.stateOf(r.sc), engine: r.e.dump(), records: r.sc.records }));
const a = fresh();
for (let d = 0; d <= 14; d++) run(a, a.sc.g_session(), d);
check('المسار الكامل يطابق شريط المرجع', [dump(a.trace) === dump(TAPE.full.trace), dump(fin(a)) === dump(TAPE.full.final)], [true, true]);

const c = fresh();
const day = TAPE.full.trace.find((t) => t[3] === 'describe')[0];
for (let d = 0; d < day; d++) run(c, c.sc.g_session(), d);
const snap = run(c, c.sc.g_session(), day, DESC[1]);
const r = persist.restore(JSON.parse(JSON.stringify(snap)), { types: TYPES, source: src(), answer: null, item_seconds: () => 45,
  records: [], today: day });
c.e = r.engine; c.sc = r.scheduler;
run(c, c.sc.g_continue(), day);
for (let d = day + 1; d <= 14; d++) run(c, c.sc.g_session(), d);
check('الإغلاق أثناء الفحص يطابق شريط المرجع، والملاحظة describe_dropped',
  [dump(c.trace) === dump(TAPE.closed.trace), dump(fin(c)) === dump(TAPE.closed.final), r.notes.filter((n) => n[0] === 'describe_dropped')],
  [true, true, [['describe_dropped', '3-5-3']]]);
const ok = results.filter(Boolean).length;
console.log(`النتيجة: نجح ${ok} من ${results.length}`);
process.exit(ok === results.length ? 0 : 1);
