// تأخير بند التقييم على التطبيق: الحالات نفسها tests/defer_cases.json، والمشهد نفسه على المجدول وطبقة الخطوات والحفظ.
//
//     node tests/test_defer.mjs [مجلد app]
//
// القاعدة والمتوقع في tests/test_defer.py.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { Activity, GateRun, ShortCheckRun, CheckRun, RetentionRun, ContentSource, driveSteps } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const CASES = JSON.parse(readFileSync(new URL('defer_cases.json', import.meta.url), 'utf8')).cases;
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const results = [];
const canon = (x) => (Array.isArray(x) ? x.map(canon) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, canon(x[k])])) : x);
const same = (a, b) => JSON.stringify(canon(a)) === JSON.stringify(canon(b));

function expect(title, got, want) {
  const ok = same(got, want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${title}`);
  if (!ok) console.log(`        ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
}

function keyOf(w) {
  if (w.activity === 'gate') {
    if (w.alternate) return `alt:${w.type}:${w.alt_index}`;
    return w.role === 'gate' ? `gate:${w.pos}` : `comp:${w.type}:${w.pos}`;
  }
  if (w.activity === 'short') return `short:${w.pos}`;
  if (w.activity === 'check') return `${w.alternate ? 'checkalt' : 'check'}:${w.slot}`;
  return `ret:${w.pos}`;
}

function make(c) {
  if (c.act === 'gate') return new GateRun({ skill: 'S', types: c.types });
  if (c.act === 'short') return new ShortCheckRun({ skill: 'S', types: c.types });
  if (c.act === 'check') return new CheckRun({ skill: 'S', check_id: 'S/check/1', content_version: 1 });
  return new RetentionRun({ skill: 'S', round: 1 });
}

function runCase(c) {
  const source = (_skill, w) => {
    const k = keyOf(w);
    return k in c.facts ? { id: k, fact: [c.facts[k]] } : null;
  };
  let act = make(c);
  const shown = [];
  const marked = [];
  const recs = [];
  let gen = driveSteps(act, source, recs, null, null, () => ['p', [c.prev]]);
  let r = gen.next();
  while (!r.done) {
    const [item, w] = r.value;
    const o = shown.length < c.script.length ? c.script[shown.length] : 'c';
    shown.push(item.id);
    if (w.fact_just_seen) marked.push(item.id);
    const got = [o === 'i' ? [['interrupt']] : [['confirm', o === 'c' ? 1 : 2]], 1, true];
    r = gen.next(got);
    if (c.roundtrip === shown.length && !r.done) {   // يُحفظ النشاط بعد هذا البند ويُنشأ من لقطته
      act = Activity.fromDict(JSON.parse(JSON.stringify(act.toDict())));
      gen = driveSteps(act, source, recs);
      r = gen.next();
    }
  }
  const out = { shown, marked, result: act.result, defer: act.defer ?? null, records: recs.map((x) => x.item) };
  if ('errors' in c) out.errors = act.errors;
  if ('answers' in c) out.answers = Object.fromEntries(Object.keys(c.answers).map((k) => [k, act.answers[k]]));
  if ('correct' in c) out.correct = act.correct;
  return out;
}

console.log('=== تأخير بند التقييم، بلغة JavaScript');
for (const c of CASES) {
  const want = { records: c.shown };
  for (const k of ['shown', 'marked', 'result', 'defer', 'errors', 'answers', 'correct']) if (k in c) want[k] = c[k];
  expect(c.name, runCase(c), want);
}

// 2) على المجدول وطبقة الخطوات والحفظ
const SCENE = { '1-4-2/gate/01': { numbers: { n: 7 }, answer: 3, fact: [3, 7] },
  '1-4-2/gate/02': { numbers: { n: 4 }, answer: 6, fact: [4, 6] },
  '1-4-2/gate/03': { numbers: { n: 8 }, answer: 2, fact: [2, 8] },
  '1-4-2/gate/18': { numbers: { n: 5 }, answer: 5, fact: [5, 5] },
  '1-4-2/gate/19': { numbers: { n: 9 }, answer: 1, fact: [1, 9] } };
const num = (k) => `1-4-2/gate/${String(k).padStart(2, '0')}`;
const PLAIN = [1, 2, 3, 4, 5, 6, 7, 8, 9].map(num);
const ORDER = [2, 1, 3, 4, 5, 6, 7, 8, 9].map(num);
const secs = (w) => (w.activity === 'check' ? 60 : 25);
const ASSESS = ['gate', 'short', 'check', 'retention'];

function scene(inject, closeAt = null) {
  const src = new ContentSource(ITEMS);
  const box = { sc: null, done: !inject };
  const pick = (s, w) => {
    let it = src.pick(s, w);
    if (it && SCENE[it.id]) it = { ...it, ...SCENE[it.id] };
    if (!box.done && !w.peek && it && it.id === '1-4-2/gate/01') {
      box.done = true;                            // الحقن: آخر بند عُرض للمهارة من نشاط آخر، بحقيقة gate/01
      box.sc.last = { session: box.sc.cur, skill: '1-4-2', activity: 'lesson', item: '1-4-2/lesson/x', fact: [3, 7],
        counts: true };
    }
    return it;
  };
  let eng = new Engine(undefined, { group: 'young' });
  eng.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  let sc = new Scheduler(eng, TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false });
  box.sc = sc;
  let st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  const shown = [];
  let pendingClose = closeAt;
  let n = 0;
  while (st.pending !== null && n < 400) {
    const [item, w] = st.pending;
    if (pendingClose !== null && item.id === pendingClose) {
      const r = persist.restore(JSON.parse(JSON.stringify(st.snapshot())), { types: TYPES, source: pick, answer: null,
        item_seconds: secs, records: [], today: null });
      eng = r.engine;
      sc = r.scheduler;
      box.sc = sc;
      st = new Stepper(eng, sc);
      st.open(sc.g_run(20));
      pendingClose = null;
      continue;
    }
    n += 1;
    if (item.id.startsWith('1-4-2/gate/')) shown.push([item.id, w.fact_just_seen ?? null]);
    const evs = ['lesson', 'practice'].includes(w.activity) ? [['end']]
      : [['confirm', item.answer], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
    for (const ev of evs) st.event(st.seq, ev);
    if (shown.length === 9 && shown[8][0] === item.id) break;
  }
  const recs = sc.records.filter((r) => r.skill === '1-4-2' && r.activity === 'gate').map((r) => r.item);
  return [shown.map((x) => x[0]), shown.map((x) => x[1]).filter((m) => m), recs, eng.derive()['1-4-2'] ?? null];
}

const plain = scene(false);
expect('م1. بلا حقن: بوابة 1-4-2 بترتيب المحتوى، بلا وسم', plain.slice(0, 3), [PLAIN, [], PLAIN]);
const cont = scene(true);
expect('م2. بالحقن: يُبدأ بالبند الثاني ثم الأول، بلا وسم، وسجل لكل بند بترتيب عرضه', cont.slice(0, 3), [ORDER, [], ORDER]);
expect('م3. حالة المهارة بعد البوابة واحدة بالتأخير وبدونه، وهي الإعفاء', [cont[3], plain[3]], ['exempt', 'exempt']);
const again = scene(true, '1-4-2/gate/01');
expect('م4. إغلاق والبند المؤجَّل مطلوب لم يُعرض، ثم استعادة: الترتيب والسجلات وحالة المهارة كالمتصل', again, cont);
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
