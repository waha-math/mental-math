// المراجعة 22 على التطبيق: يعيد شريط الأحداث نفسه tests/r22_tape.json (يولّده tests/test_r22.py --write)، بلا عشوائية.
//
//     node tests/test_r22.mjs [مجلد app]
//
// المشهد والقاعدة والمتوقع في tests/test_r22.py.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const TAPE = JSON.parse(readFileSync(new URL('r22_tape.json', import.meta.url), 'utf8'));
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const DISPLAY = ['lesson', 'practice'];
const results = [];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const fact = (it) => {
  const n = it.numbers;
  if ('a' in n) return [n.a, n.b];
  const v = n.n ?? n.e;
  return [v, 10 - v].sort((x, y) => x - y);
};

function expect(title, got, want) {
  const ok = same(got, want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${title}`);
  if (!ok) console.log(`        ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
}

function e0() {
  const e = new Engine(undefined, { group: 'young' });
  e.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  return e;
}
const src = new ContentSource(ITEMS);
// بنود المشهد كما كانت في محتوى 03d2e0d، أيًّا كان المحتوى الآن (كما في tests/test_r22.py)
const SCENE = { '1-4-2/gate/01': { numbers: { n: 7 }, answer: 3, fact: [3, 7] },
  '1-4-2/gate/02': { numbers: { n: 4 }, answer: 6, fact: [4, 6] },
  '1-4-2/gate/03': { numbers: { n: 8 }, answer: 2, fact: [2, 8] },
  '1-4-2/tryfirst/03': { numbers: { n: 8 }, answer: 2, fact: [2, 8] },
  '1-4-2/tryfirst/04': { numbers: { n: 6 }, answer: 4, fact: [4, 6] } };
const pick = (s, w) => {
  const it = src.pick(s, w);
  return it && SCENE[it.id] ? { ...it, ...SCENE[it.id] } : it;
};
const secs = (w) => (w.activity === 'check' ? 60 : 25);
const persist = await load('persist.mjs');

// closeAt: يُغلق التطبيق والبند بهذا المعرّف مطلوب لم يُعرض، ثم تُستعاد اللقطة ويُكمَل الشريط
function run(closeAt = null) {
  let sc = new Scheduler(e0(), TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false });
  let eng = sc.e;
  let st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  const out = [];
  let err = null;
  let pendingClose = closeAt;
  while (st.pending !== null) {
    if (pendingClose !== null && st.pending[0].id === pendingClose) {
      const r = persist.restore(JSON.parse(JSON.stringify(st.snapshot())), { types: TYPES, source: pick, answer: null,
        item_seconds: secs, records: [], today: null });
      eng = r.engine;
      sc = r.scheduler;
      st = new Stepper(eng, sc);
      st.open(sc.g_run(20));
      pendingClose = null;
      continue;
    }
    const [item, w] = st.pending;
    const k = out.length;
    if (k >= TAPE.length || TAPE[k].item !== item.id) {
      err = `البند رقم ${k}: ${item.id}، وفي الشريط ${k < TAPE.length ? TAPE[k].item : 'لا شيء'}`;
      break;
    }
    out.push({ session: eng.s.current, skill: item.skill, activity: w.activity, item: item.id, fact: fact(item),
      just_seen: w.fact_just_seen ?? null, last: sc.last ?? null });
    for (const ev of TAPE[k].events) st.event(st.seq, ev);
  }
  if (err === null && out.length !== TAPE.length) err = `انتهى التشغيل عند ${out.length} والشريط ${TAPE.length}`;
  return { out, err };
}
const { out, err } = run();

console.log('=== المراجعة 22، بلغة JavaScript');
expect('1. الشريط يُعاد كله: البنود المعروضة هي بنود الشريط', [err, out.length], [null, TAPE.length]);
// R23-02: آخر بند عُرض (last) عند كل بند من الشريط، كما كتبه المرجع في الشريط
const off = [];
out.forEach((x, k) => { if (!same(x.last, TAPE[k].last ?? null)) off.push(k); });
expect(`1ب. آخر بند عُرض عند كل بند يطابق ما في الشريط (${TAPE.length} بندًا، منها ${TAPE.filter((t) => t.last).length} لها آخر بند)`,
  off.slice(0, 3), []);
expect('2. الجلسة 10: بعد gate/03 يُبدأ «جرّب أولًا» بالبند الآخر من نوعه، لا بالذي يكرر الحقيقة',
  out.filter((x) => x.session === 'S10' && x.skill === '1-4-2').slice(0, 5).map((x) => x.item),
  ['1-4-2/gate/01', '1-4-2/gate/02', '1-4-2/gate/03', '1-4-2/tryfirst/04', '1-4-2/tryfirst/03']);
const bad = [];
for (let i = 1; i < out.length; i += 1) {
  const [a, b] = [out[i - 1], out[i]];
  if (a.session === b.session && a.skill === b.skill && a.item !== b.item && same(a.fact, b.fact)
    && !DISPLAY.includes(b.activity) && !b.just_seen) bad.push([a.item, b.item]);
}
expect('3. في المسار كله: لا بندان متتاليان بالحقيقة نفسها للمهارة نفسها في الجلسة نفسها، خارج دخول بنود العرض '
  + 'التعليمي وما وُسم', bad, []);
const again = run('1-4-2/tryfirst/04');
expect('9. إغلاق وبند «جرّب أولًا» الأول مطلوب لم يُعرض، ثم استعادة: الشريط يُكمَل بالبنود نفسها',
  [again.err, same(again.out.map((x) => x.item), out.map((x) => x.item))], [null, true]);

// R23-01: الاستعادة تختم البند الجاري وتتقدم به، فيجب أن يتحدث معها آخر بند عُرض، بقواعد التعرّض نفسها (كما في
// tests/test_r22.py)
function afterFirstTry(events, close, today = null) {
  let sc = new Scheduler(e0(), TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false });
  let st = new Stepper(sc.e, sc);
  st.open(sc.g_run(20));
  let k = 0;
  while (st.pending[0].id !== '1-4-2/tryfirst/04') {
    for (const ev of TAPE[k].events) st.event(st.seq, ev);
    k += 1;
  }
  if (events === null) st.show(st.seq);
  for (const ev of events || []) st.event(st.seq, ev);
  if (close) {
    const r = persist.restore(JSON.parse(JSON.stringify(st.snapshot())), { types: TYPES, source: pick, answer: null,
      item_seconds: secs, records: [], today });
    if (today !== null) {                         // يوم جديد: الاستعادة تختم الجلسة، فلا «آخر بند» لها
      const again = JSON.parse(JSON.stringify(persist.snapshot(r.engine, r.scheduler)));
      const r2 = persist.restore(JSON.parse(JSON.stringify(again)), { types: TYPES, source: pick, answer: null,
        item_seconds: secs, records: [], today });
      return [r.scheduler.cur, r.scheduler.last, same(JSON.parse(JSON.stringify(persist.snapshot(r2.engine, r2.scheduler))), again)];
    }
    sc = r.scheduler;
    st = new Stepper(r.engine, sc);
    st.open(sc.g_run(20));
  } else {
    st.event(st.seq, ['end']);                    // في التشغيل المتصل ينتهي بند التعليم بـend بعد إجابة مؤكدة
  }
  const [item, w] = st.pending;
  return [item.id.slice(6), w.reshown, ((sc.last || {}).item || '').slice(6), (sc.last || {}).counts ?? null];
}
const want = ['tryfirst/03', 0, 'tryfirst/04', true];
expect('10. إجابة مؤكدة صحيحة ثم إغلاق قبل end واستعادة: البند التالي وآخر بند عُرض كما لو أُنهي البند بلا إغلاق',
  [afterFirstTry([['confirm', 4]], true), afterFirstTry([['confirm', 4]], false)], [want, want]);
expect('11. طلب دعم ثم إغلاق واستعادة: البند يُحتسب تعرّضًا، والتالي البند الآخر',
  afterFirstTry([['support', 'hint']], true), want);
expect('12. العرض وحده ثم إغلاق واستعادة: يُعاد البند نفسه موسومًا، وآخر بند عُرض هو لكنه لا يُحتسب تعرّضًا',
  afterFirstTry(null, true), ['tryfirst/04', 1, 'tryfirst/04', false]);

expect('13. إجابة مؤكدة ثم إغلاق واستعادة في يوم جديد: الجلسة تُختم ولا «آخر بند» لها، وحفظ المستعاد واستعادته لا يغيّره',
  afterFirstTry([['confirm', 4]], true, 10 ** 6), [null, null, true]);

// المسار 319 من متجهات المجدول (try_from_gate: false): بعد البوابة يأتي الافتتاح بالبندين الثابتين. الشريط
// tests/r22_tape_fixed.json، والمشهد وزرع التصادم كما في tests/test_r22.py
{
  const TAPE2 = JSON.parse(readFileSync(new URL('r22_tape_fixed.json', import.meta.url), 'utf8'));
  const box = {};
  const pick2 = (s, w) => {
    let it = src.pick(s, w);
    const x = box.sc.last;
    // بنود بوابة المشهد الأربعة مثبتة بأعدادها في الحزمة 4 (انظر نسخة بايثون)
    const GATE4 = { '1-4-2/gate/01': 7, '1-4-2/gate/02': 6, '1-4-2/gate/03': 8, '1-4-2/gate/04': 1 };
    if (it && it.id in GATE4) {
      const n = GATE4[it.id];
      it = { ...it, numbers: { n }, answer: 10 - n, fact: [n, 10 - n].sort((p, q) => p - q) };
    }
    if (it && it.id.endsWith('/opening/01') && x && x.activity === 'gate' && x.skill === it.skill
      && x.session === box.sc.cur && x.counts) return { ...it, fact: [...x.fact] };
    return it;
  };
  const sc = new Scheduler(e0(), TYPES, pick2, null, { group: 'young', scope: ['1-4-1', '1-4-2'], learning: true,
    cap: 240, item_seconds: secs, records: [], retention: false, try_from_gate: false });
  box.sc = sc;
  const st = new Stepper(sc.e, sc);
  st.open(sc.g_run(20));
  const ids = [];
  let err2 = null;
  while (st.pending !== null) {
    const [item] = st.pending;
    const k = ids.length;
    if (k >= TAPE2.length || TAPE2[k].item !== item.id) {
      err2 = `البند رقم ${k}: ${item.id}، وفي الشريط ${k < TAPE2.length ? TAPE2[k].item : 'لا شيء'}`;
      break;
    }
    ids.push(item.id);
    for (const ev of TAPE2[k].events) st.event(st.seq, ev);
  }
  const at = ids.indexOf('1-4-2/gate/04');
  expect('14. بعد البوابة والبندان الثابتان (المسار 319): الأول يكرر حقيقة آخر بند فيها فلا يُعرض ولا سجل له، ويُعرض الثاني',
    [err2, ids.length === TAPE2.length, ids.slice(at, at + 3), sc.records.filter((r) => r.item === '1-4-2/opening/01').length],
    [null, true, ['1-4-2/gate/04', '1-4-2/opening/02', '1-4-2/opening/03'], 0]);
}

// علاج كل نشاط عند دخوله ببند يكرر حقيقة آخر ما عُرض من نشاط آخر، على طبقة البنود مباشرة
const { OpeningRun, EvidenceRun, GateRun, driveSteps } = await load('items.mjs');
const T3 = ['ف2', 'ف3', 'ف4'];
let o = new OpeningRun({ skill: '1-4-2', types: T3, try_types: ['ف3', 'ف3'], typed: true });
const steps = [o.want().type_index, o.repeated('a'), o.want().type_index, o.repeated('b'), o.want().role, o.try_out];
expect('4. افتتاح بنوعَي خطأ من نوع واحد: يُبدأ بالبند الآخر، وإن كرر هو أيضًا لم يُعرض ونتيجته void وتأتي الموجَّهة',
  steps, [0, true, 1, true, 'opening.try', ['void']]);
o.feed('correct');
expect('5. بند «جرّب أولًا» بنتيجة void لا يتخطى الشرح ولو صح الآخر', [o.stage, o.done], ['guided', false]);
o = new OpeningRun({ skill: '1-4-2', types: T3, typed: true });
expect('6. افتتاح بالبندين الثابتين: لا بند آخر، فلا يُعرض ونتيجته void', [o.repeated('a'), o.try_out, o.pos], [true, ['void'], 1]);
const v = new EvidenceRun({ skill: '1-4-2', types: T3 });
const r1 = v.repeated('x');
const w1 = v.want();
const r2 = v.repeated('alt');
if (v.want().alternate === 2) v.unavailable();
expect('7. دليل الفهم: يُطلب بديل النوع لموضعه، وإن كرر البديل الحقيقة انتهت الجولة بلا حكم',
  [r1, w1.role, w1.replaces, r2, v.result], [true, 'evidence.alternate', 'x', true, 'no_alternate']);
const gate = new GateRun({ skill: '1-4-2', types: T3 });
const recs = [];
const gen = driveSteps(gate, () => ({ id: 'g1', fact: [2, 8] }), recs, null, null, () => ['p9', [2, 8]]);
const first = gen.next().value;
gen.next([[['confirm', 1]], 2, true]);
expect('8. نشاط تقييم ولا موضع يُؤخَّر إليه البند (كل بنوده بالحقيقة نفسها): يُعرض موسومًا في الطلب وفي سجله بالبند الذي سبقه',
  [gate.repeated('g1'), first[1].fact_just_seen ?? null, recs[0].fact_just_seen ?? null], [false, 'p9', 'p9']);
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
