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
    const o = (c.by_id ?? {})[item.id] ?? (shown.length < c.script.length ? c.script[shown.length] : 'c');
    shown.push(item.id);
    if (w.fact_just_seen) marked.push(item.id);
    const got = [o === 'i' ? [['interrupt']] : o === 'h' ? [['support', 'requested'], ['interrupt']]
      : [['confirm', o === 'c' ? 1 : 2]], 1, true];
    r = gen.next(got);
    if (c.roundtrip === shown.length && !r.done) {   // يُحفظ النشاط بعد هذا البند ويُنشأ من لقطته
      act = Activity.fromDict(JSON.parse(JSON.stringify(act.toDict())));
      gen = driveSteps(act, source, recs);
      r = gen.next();
    }
  }
  const out = { shown, marked, result: act.result, defer: act.defer ?? null, records: recs.map((x) => x.item),
    ahead: Object.fromEntries(recs.filter((x) => x.ahead_of).map((x) => [x.item, x.ahead_of])) };
  if ('errors' in c) out.errors = act.errors;
  if ('answers' in c) out.answers = Object.fromEntries(Object.keys(c.answers).map((k) => [k, act.answers[k]]));
  if ('correct' in c) out.correct = act.correct;
  if ('weak' in c) out.weak = recs.filter((x) => x.after_exposure).map((x) => x.item);   // ت2
  return out;
}

console.log('=== تأخير بند التقييم، بلغة JavaScript');
for (const c of CASES) {
  const want = { records: c.shown };
  for (const k of ['shown', 'marked', 'result', 'defer', 'errors', 'answers', 'correct', 'ahead', 'weak']) {
    if (k in c) want[k] = c[k];
  }
  expect(c.name, runCase(c), want);
}

// ت2 على النشاط مباشرة: نتيجة exposed في فحص الاستقلال وفحص الاحتفاظ
for (const c of JSON.parse(readFileSync(new URL('defer_cases.json', import.meta.url), 'utf8')).feeds) {
  const act = make(c);
  for (const o of c.feeds) act.feed(o);
  const w = act.want();
  const got = { result: act.result, slot: act.slot ?? null, total_cuts: act.total_cuts ?? null, correct: act.correct,
    hold: act.hold ?? null, role: w ? w.role : null, events: act.done ? act.events().map((e) => e.type) : [], done: act.done };
  expect(c.name, Object.fromEntries(Object.keys(c.want).map((k) => [k, got[k]])), c.want);
}

// 2) على المجدول وطبقة الخطوات والحفظ
const SCENE = { '1-4-2/gate/01': { numbers: { n: 7 }, answer: 3, fact: [3, 7] },
  '1-4-2/gate/02': { numbers: { n: 4 }, answer: 6, fact: [4, 6] },
  '1-4-2/gate/03': { numbers: { n: 8 }, answer: 2, fact: [2, 8] },
  '1-4-2/gate/18': { numbers: { n: 5 }, answer: 5, fact: [5, 5] },
  '1-4-2/gate/19': { numbers: { n: 9 }, answer: 1, fact: [1, 9] },
  // بقية بنود البوابة مثبتة بأعدادها في الحزمة 4 (انظر نسخة بايثون)
  '1-4-2/gate/04': { numbers: {n: 1}, answer: 9, fact: [1, 9] },
  '1-4-2/gate/05': { numbers: {n: 5}, answer: 5, fact: [5, 5] },
  '1-4-2/gate/06': { numbers: {n: 9, ctx: 'ctx_bus'}, answer: 1, fact: [1, 9] },
  '1-4-2/gate/07': { numbers: {n: 6, ctx: 'ctx_balloons'}, answer: 4, fact: [4, 6] },
  '1-4-2/gate/08': { numbers: {n: 2}, answer: 8, fact: [2, 8] },
  '1-4-2/gate/09': { numbers: {n: 3}, answer: 7, fact: [3, 7] } };
const num = (k) => `1-4-2/gate/${String(k).padStart(2, '0')}`;
const PLAIN = [1, 2, 3, 4, 5, 6, 7, 8, 9].map(num);
const ORDER = [2, 1, 3, 4, 5, 6, 7, 8, 9].map(num);
const secs = (w) => (w.activity === 'check' ? 60 : 25);
const ASSESS = ['gate', 'short', 'check', 'retention', 'describe'];

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

// وسوم الطلب تبقى في السجل حين تختم الاستعادةُ البند: المشهدان م5 وم6 في tests/test_defer.py
function settled(pins, target) {
  const src = new ContentSource(ITEMS);
  const box = { sc: null, done: false };
  const pick = (s, w) => {
    let it = src.pick(s, w);
    if (it && pins[it.id]) it = { ...it, ...pins[it.id] };
    if (!box.done && !w.peek && it && it.id === '1-4-2/gate/01') {
      box.done = true;
      box.sc.last = { session: box.sc.cur, skill: '1-4-2', activity: 'lesson', item: '1-4-2/lesson/x', fact: [3, 7],
        counts: true };
    }
    return it;
  };
  const eng = new Engine(undefined, { group: 'young' });
  eng.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  const sc = new Scheduler(eng, TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false });
  box.sc = sc;
  const st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  let n = 0;
  while (st.pending !== null && st.pending[0].id !== target && n < 400) {
    const [item, w] = st.pending;
    n += 1;
    const evs = ['lesson', 'practice'].includes(w.activity) ? [['end']]
      : [['confirm', item.answer], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
    for (const ev of evs) st.event(st.seq, ev);
  }
  st.show(st.seq);
  const r = persist.restore(JSON.parse(JSON.stringify(st.snapshot())), { types: TYPES, source: pick, answer: null,
    item_seconds: secs, records: [], today: null });
  const rec = r.scheduler.records.filter((x) => x.item === target).pop();
  return { unsettled: rec.unsettled ?? null, fact_just_seen: rec.fact_just_seen ?? null, ahead_of: rec.ahead_of ?? null };
}

expect('م5. بند عُرض قبل بند أُخّر، ثم إغلاق واستعادة تختمه: سجله يحمل ما أُخّر',
  settled(SCENE, '1-4-2/gate/02'), { unsettled: true, fact_just_seen: null, ahead_of: ['1-4-2/gate/01'] });
const SAME = Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8, 9].map((k) => [num(k), { numbers: { n: 7 }, answer: 3, fact: [3, 7] }]));
expect('م6. بند لا موضع يُؤخَّر إليه عُرض موسومًا، ثم إغلاق واستعادة تختمه: سجله يحمل الوسم',
  settled(SAME, '1-4-2/gate/01'), { unsettled: true, fact_just_seen: '1-4-2/lesson/x', ahead_of: null });

const plain = scene(false);
expect('م1. بلا حقن: بوابة 1-4-2 بترتيب المحتوى، بلا وسم', plain.slice(0, 3), [PLAIN, [], PLAIN]);
const cont = scene(true);
expect('م2. بالحقن: يُبدأ بالبند الثاني ثم الأول، بلا وسم، وسجل لكل بند بترتيب عرضه', cont.slice(0, 3), [ORDER, [], ORDER]);
expect('م3. حالة المهارة بعد البوابة واحدة بالتأخير وبدونه، وهي الإعفاء', [cont[3], plain[3]], ['exempt', 'exempt']);
const again = scene(true, '1-4-2/gate/01');
expect('م4. إغلاق والبند المؤجَّل مطلوب لم يُعرض، ثم استعادة: الترتيب والسجلات وحالة المهارة كالمتصل', again, cont);

// 4) أثر تغيّر الحكم على المهارة وما بعدها (ت1): المشهد نفسه في tests/test_defer.py، القسم 4
const SCENE_T1 = { '1-4-2/gate/01': { numbers: { n: 7 }, answer: 3, fact: [3, 7] },
  '1-4-2/gate/02': { numbers: { n: 4 }, answer: 6, fact: [4, 6] },
  '1-4-2/gate/03': { numbers: { n: 7 }, answer: 3, fact: [3, 7] },
  '1-4-2/gate/04': { numbers: { n: 9 }, answer: 1, fact: [1, 9] },
  '1-4-2/gate/05': { numbers: { n: 5 }, answer: 5, fact: [5, 5] },
  '1-4-2/gate/18': { numbers: { n: 8 }, answer: 2, fact: [2, 8] },
  '1-4-2/gate/19': { numbers: { n: 4 }, answer: 6, fact: [4, 6] } };

function sceneT1(inject) {
  const src = new ContentSource(ITEMS);
  const box = { sc: null, done: !inject };
  const pick = (s, w) => {
    let it = src.pick(s, w);
    if (it && SCENE_T1[it.id]) it = { ...it, ...SCENE_T1[it.id] };
    if (!box.done && !w.peek && it && it.id === '1-4-2/gate/01') {
      box.done = true;
      box.sc.last = { session: box.sc.cur, skill: '1-4-2', activity: 'lesson', item: '1-4-2/lesson/x', fact: [3, 7],
        counts: true };
    }
    return it;
  };
  const eng = new Engine(undefined, { group: 'young' });
  eng.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  const sc = new Scheduler(eng, TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'],
    learning: true, cap: 240, item_seconds: secs, records: [], retention: false });
  box.sc = sc;
  const st = new Stepper(eng, sc);
  st.open(sc.g_run(20));
  const shown = [];
  let after = null;
  let n = 0;
  while (st.pending !== null && n < 400) {
    const [item, w] = st.pending;
    n += 1;
    if (item.id.startsWith('1-4-2/gate/')) shown.push(item.id);
    else if (shown.length) { after = [item.id.split('/').slice(0, -1).join('/'), w.activity]; break; }
    let evs;
    if (item.id === '1-4-2/gate/01') evs = [['support', 'requested']];
    else if (['1-4-2/gate/02', '1-4-2/gate/03'].includes(item.id)) evs = [['confirm', item.answer + 1]];
    else if (['lesson', 'practice'].includes(w.activity)) evs = [['end']];
    else evs = [['confirm', item.answer], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
    for (const ev of evs) st.event(st.seq, ev);
  }
  return { shown, after,
    attempts: eng.s.attempts.filter((a) => a.skill === '1-4-2' && a.what === 'gate').map((a) => a.result),
    status: eng.derive()['1-4-2'] ?? null,
    treatment: eng.s.evidence.filter((x) => x.skill === '1-4-2').map((x) => x.treatment ?? null) };
}

const tPlain = sceneT1(false);
const tDefer = sceneT1(true);
expect('ث3. على المجدول بلا حقن: يُعرض gate/01 وحده، ومحاولة البوابة «طلب دعم»، ولا حالة للمهارة',
  [tPlain.shown, tPlain.attempts, tPlain.status], [['1-4-2/gate/01'], ['help'], null]);
expect('ث4. بالحقن: يُعرض gate/02 ثم gate/03، ومحاولة البوابة «إخفاق»، وحالة المهارة تعثّر',
  [tDefer.shown, tDefer.attempts, tDefer.status], [['1-4-2/gate/02', '1-4-2/gate/03'], ['fail'], 'stumbled']);
expect('ث5. ما بعد البوابة يختلف (مقيس): بعد طلب الدعم افتتاح الدرس ببنوده الثابتة، وبعد الإخفاق ببنود «جرّب أولًا»، وعلاج التعثّر regular',
  [tPlain.after, tDefer.after, tPlain.treatment, tDefer.treatment],
  [['1-4-2/opening', 'opening'], ['1-4-2/tryfirst', 'opening'], [], ['regular']]);
// 5) ت2 على المجدول: المشهدان ع11 وع12 في tests/test_defer.py، بالتثبيت نفسه والمتوقع نفسه
{
  const P2 = Object.fromEntries([7, 4, 7, 8, 7, 9, 7, 5, 7].map((n, k) => [num(k + 1),
    { numbers: { n }, answer: 10 - n, fact: [n, 10 - n].sort((x, y) => x - y) }]));
  P2[num(18)] = { numbers: { n: 9 }, answer: 1, fact: [1, 9] };
  const sceneT2 = (noAlts) => {
    const src = new ContentSource(ITEMS);
    const box = { sc: null, done: false };
    const pick = (s, w) => {
      if (noAlts && w.activity === 'gate' && w.alternate) return null;
      let it = src.pick(s, w);
      if (it && P2[it.id]) it = { ...it, ...P2[it.id] };
      if (!box.done && !w.peek && it && it.id === num(1)) {
        box.done = true;
        box.sc.last = { session: box.sc.cur, skill: '1-4-2', activity: 'lesson', item: '1-4-2/lesson/x', fact: [3, 7],
          counts: true };
      }
      return it;
    };
    const eng = new Engine(undefined, { group: 'young' });
    eng.apply({ id: 'd0', type: 'teacher_open', skill: '1-4-1', bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
    const sc = new Scheduler(eng, TYPES, pick, null, { group: 'young', scope: ['1-4-1', '1-4-2'], learning: true,
      cap: 240, item_seconds: secs, records: [], retention: false });
    box.sc = sc;
    const st = new Stepper(eng, sc);
    st.open(sc.g_run(20));
    const shown = [];
    const tries = () => eng.s.attempts.filter((a) => a.skill === '1-4-2' && a.what === 'gate').map((a) => a.result);
    let n = 0;
    while (st.pending !== null && n < 400 && !tries().length) {
      const [item, w] = st.pending;
      n += 1;
      if (item.id.startsWith('1-4-2/gate/')) shown.push([item.id, Boolean(w.fact_just_seen)]);
      const evs = ['lesson', 'practice'].includes(w.activity) ? [['end']]
        : [['confirm', item.answer], ...(ASSESS.includes(w.activity) ? [] : [['end']])];
      for (const ev of evs) st.event(st.seq, ev);
    }
    const plain = sc.records.filter((r) => r.status === 'complete' && r.first && !r.support_before.length).length;
    return { shown: shown.map((x) => x[0]), marked: shown.filter((x) => x[1]).map((x) => x[0]),
      weak: sc.records.filter((r) => r.after_exposure).map((r) => r.item), attempts: tries(),
      status: eng.derive()['1-4-2'] ?? null,
      stumbles: eng.s.evidence.filter((x) => x.skill === '1-4-2' && x.kind === 'stumble').length,
      independent: sc.indicators().independent.num - plain };
  };
  expect('ع11 (ت2). على المجدول: الأول موسوم وإجابته الصحيحة «أداء بعد تعرض مباشر» لا تدخل عدّ الصحيح المستقل. يُطلب بديل نوعه، '
    + 'وتُجتاز البوابة بالبنود المستقلة، فالمهارة معفاة', sceneT2(false),
  { shown: [num(1), num(18), ...[2, 3, 4, 5, 6, 7, 8, 9].map(num)], marked: [num(1)], weak: [num(1)], attempts: ['pass'],
    status: 'exempt', stumbles: 0, independent: -1 });
  expect('ع12 (ت2). والبدائل محجوبة: البوابة تُعلَّق بلا نتيجة بعد بندها الأول. لا إعفاء ولا تعثّر: نقص البدائل ليس إخفاقًا',
    sceneT2(true),
    { shown: [num(1)], marked: [num(1)], weak: [num(1)], attempts: ['interrupted'], status: null, stumbles: 0,
      independent: -1 });
}

console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
