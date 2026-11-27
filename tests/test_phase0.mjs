// المرحلة 0 على التطبيق بلغة JavaScript: التوقف عند انتظار الطفل، والإغلاق، والاستعادة، وتكملة الجلسة نفسها.
//
//     node tests/test_phase0.mjs [مجلد app]
//
// المجلد الاختياري يشغّلها على نسخة أخرى من التطبيق (مثلًا الالتزام 0189879).
// الحالات والنتائج المتوقعة نفسها في tests/test_phase0.py. أنواع دليل الفهم للمهارات الخمس من صفوفها في الخريطة.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine, canonical } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource, indicators } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const results = [];
const dump = (x) => canonical(x ?? null);

function check(title, bad) {
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${title}`);
  for (const b of bad.slice(0, 4)) console.log('        ' + b);
}

// طفل نموذجي: يعرف المهارة بعد أن يرى درسها. wrong: بنود يخطئ فيها. help: بنود يطلب فيها تلميحًا أولًا
class Kid {
  constructor(wrong = [], help = []) {
    this.known = new Set();
    this.wrong = new Set(wrong);
    this.help = new Set(help);
  }

  events(item, w) {
    const a = w.activity;
    if (a === 'lesson' || a === 'practice') {
      if (a === 'lesson') this.known.add(item.skill);
      return [['end']];
    }
    const assess = ['gate', 'short', 'check', 'retention', 'describe'].includes(a);
    const ok = this.known.has(item.skill) && !this.wrong.has(item.id);
    const ans = ok ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1);
    return [...(this.help.has(item.id) ? [['support', 'hint']] : []), ['confirm', ans], ...(assess ? [] : [['end']])];
  }
}

const SCEN = {
  young: { group: 'young', scope: ['1-4-1', '1-4-2'], decisions: [['1-4-1', ['1-3-3']]], cap: 240, sessions: 14,
    secs: (w) => (w.activity === 'check' ? 60 : 25) },
  older: { group: 'older', scope: ['3-5-1', '3-5-2', '3-5-3'],
    decisions: [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]], cap: 600, sessions: 16,
    secs: () => 45 },
};
SCEN.retention = { ...SCEN.young, scope: ['1-4-1'], retention: true, sessions: 100 };   // فحوص الاحتفاظ الثلاثة

function build(name, wrapSource = null) {
  const c = SCEN[name];
  const e = new Engine(undefined, { group: c.group });
  c.decisions.forEach(([skill, bypass], k) => e.apply({ id: 'd' + k, type: 'teacher_open', skill, bypass,
    reason: 'قرار الشريحة في 10.2' }));
  const src = new ContentSource(ITEMS);
  let source = (s, w) => src.pick(s, w);
  if (wrapSource) source = wrapSource(source);
  const sc = new Scheduler(e, TYPES, source, null, { group: c.group, scope: c.scope, learning: true, cap: c.cap,
    item_seconds: c.secs, records: [], retention: c.retention ?? false });
  return { e, sc };
}

function reopen(name, rec, today = null) {
  const c = SCEN[name];
  const src = new ContentSource(ITEMS);
  const r = persist.restore(JSON.parse(JSON.stringify(rec)), { types: TYPES, source: (s, w) => src.pick(s, w),
    answer: null, item_seconds: c.secs, records: [], today });
  return { e: r.engine, sc: r.scheduler, notes: r.notes };
}

// يجيب الطفل عن الطلبات حتى ينتهي المولّد، أو حتى الطلب رقم stopAt (لا يُعرض ولا يُجاب). يعيد عدد ما أُجيب
function play(st, kid, stopAt = null, n = 0) {
  while (st.pending !== null) {
    if (stopAt !== null && n === stopAt) return n;
    const [item, w] = st.pending;
    for (const ev of kid.events(item, w)) st.event(st.seq, ev);
    n += 1;
  }
  return n;
}

// الحالة الدائمة كاملة: كل ما يحفظه persist من المجدول (stateOf، ومنه العدّادات n وموضع الجلسة stage والوقت elapsed
// وعدّادات البحث وسجل المجدول والمخزنان)، والمحرك، وسجلات البنود. لا حقل مستثنى
const final = (e, sc) => ({ ...persist.stateOf(sc), engine: e.dump(), records: sc.records });

function sweep(name, wrong = [], help = []) {
  const c = SCEN[name];
  const { e, sc } = build(name);
  const st = new Stepper(e, sc);
  st.open(sc.g_run(c.sessions));
  const total = play(st, new Kid(wrong, help));
  const base = JSON.parse(JSON.stringify(final(e, sc)));
  const bad = [];
  const b0 = build(name), kid0 = new Kid(wrong, help);    // الغلاف المتزامن يعطي النتيجة نفسها
  b0.sc.answer = (item, w) => {
    const evs = kid0.events(item, w);
    if (w.activity === 'lesson' || w.activity === 'practice') return 'correct';
    return [evs, item.answer, ['gate', 'short', 'check', 'retention', 'describe'].includes(w.activity)];
  };
  b0.sc.run(c.sessions);
  if (dump(final(b0.e, b0.sc)) !== dump(base)) bad.push('التشغيل خطوة خطوة يخالف الغلاف المتزامن');
  if (base.refused.length) bad.push(`المحرك رفض ${base.refused.length} اقتراحًا في التشغيل المتصل`);
  const diff = [];
  for (let k = 0; k < total; k++) {
    const b1 = build(name), kid = new Kid(wrong, help);
    const s1 = new Stepper(b1.e, b1.sc);
    s1.open(b1.sc.g_run(c.sessions));
    play(s1, kid, k);
    const rec = s1.snapshot();
    try {
      const r = reopen(name, rec);
      const s2 = new Stepper(r.e, r.sc);
      s2.open(r.sc.g_run(c.sessions));
      play(s2, kid);
      const got = final(r.e, r.sc);
      if (dump(got) !== dump(base)) diff.push([k, Object.keys(base).filter((f) => dump(got[f]) !== dump(base[f])).join('، ')]);
    } catch (x) {
      diff.push([k, 'استثناء ' + x]);
    }
  }
  if (diff.length) bad.push(`${diff.length} من ${total} موضع إغلاق تخالف التشغيل المتصل. أولها: ${JSON.stringify(diff.slice(0, 3))}`);
  return { bad, total, base };
}

console.log(`=== المرحلة 0، بلغة JavaScript، على التطبيق في ${appDir}`);
console.log('أ) إغلاق عند كل طلب بند قبل عرضه، ثم استعادة وتكملة: النتيجة كما في التشغيل المتصل');
for (const [name, wrong, help, label] of [
  ['young', [], [], 'الصغير في 1-4، بسقف 240 ثانية'],
  ['young', ['1-4-1/evidence/01', '1-4-1/checkA/03', '1-4-1/checkA/05'], ['1-4-2/evidence/01'],
    'الصغير، بأخطاء في دليل الفهم والفحص وطلب تلميح'],
  ['older', [], [], 'الكبيران في 3-5، بسقف 600 ثانية'],
  ['older', ['3-5-1/checkA/01', '3-5-1/checkA/03', '3-5-2/evidence/01'], [], 'الكبيران، بأخطاء في الفحص ودليل الفهم'],
  ['retention', [], [], 'الصغير في 1-4-1 مع فحوص الاحتفاظ الثلاثة']]) {
  const { bad, total, base } = sweep(name, wrong, help);
  check(`${label}: ${total} موضع إغلاق في ${base.sessions} جلسة و${base.records.length} سجل بند`, bad);
}

// ---------------------------------------------------------------- ب) حالات بنتائج مكتوبة يدويًا
// مسار الصغير بلا أخطاء: S1 بوابة 1-4-1، S2 افتتاح ودرس حتى السقف، S3 دليل الفهم، S4 بدء الفحص: الخانات 1 إلى 4،
// S5 الخانات 5 إلى 8، S6 الخانتان 9 و10 والنتيجة. الطلب 16 الخانة 1، و17 الخانة 2، و25 الخانة 10.
function at(n, wrapSource = null) {
  const { e, sc } = build('young', wrapSource);
  const st = new Stepper(e, sc), kid = new Kid();
  st.open(sc.g_run(14));
  play(st, kid, n);
  return { e, sc, st, kid };
}

const count = (e, typ, session = null, more = {}) => e.s.log.filter((x) => x.type === typ
  && (session === null || x.session === session) && Object.entries(more).every(([k, v]) => x[k] === v)).length;

function expect(bad, label, got, want) {
  if (dump(got) !== dump(want)) bad.push(`${label}: ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
}

function caseShown() {
  const { st, kid } = at(17);
  st.show(st.seq);
  const { e: e2, sc: sc2, notes } = reopen('young', st.snapshot());
  const bad = [];
  expect(bad, 'ملاحظات الاستعادة', notes,
    [['unsettled_item', '1-4-1', '1-4-1/checkA/03', 'interrupted'], ['current_saved', 'check', '1-4-1']]);
  expect(bad, 'الجلسة الجارية في المحرك والمجدول وعدد الجلسات والوقت المستهلك',
    [e2.s.current, sc2.cur, sc2.sessions, sc2.elapsed], ['S4', 'S4', 4, 60]);
  const last = sc2.records[sc2.records.length - 1];
  expect(bad, 'سجل البند المعروض', [last.item, last.status, last.first, last.unsettled],
    ['1-4-1/checkA/03', 'interrupted', null, true]);
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_run(14));
  const [item, w] = s2.pending;
  expect(bad, 'البند التالي بعد العودة', [item.id, w.role, w.slot, sc2.cur], ['1-4-1/checkA/04', 'check.alternate', 2, 'S4']);
  play(s2, kid);
  expect(bad, 'بدايات S4 واستئنافات الفحص فيها', [count(e2, 'session_start', 'S4'), count(e2, 'check_resumed', 'S4')], [1, 0]);
  expect(bad, 'نتيجة فحص 1-4-1', e2.s.log.filter((x) => x.type === 'independence_result' && x.skill === '1-4-1')
    .map((x) => x.result), ['pass']);
  expect(bad, 'مرات ظهور البند المنقطع في السجلات', sc2.records.filter((r) => r.item === '1-4-1/checkA/03').length, 1);
  return bad;
}

function caseSupport() {
  const { st, kid } = at(12);
  const r = st.event(st.seq, ['support', 'hint']);
  const { e: e2, sc: sc2 } = reopen('young', st.snapshot());
  const last = sc2.records[sc2.records.length - 1];
  const bad = [];
  expect(bad, 'نتيجة الحدث', r, 'open');
  expect(bad, 'سجل البند', [last.item, last.status, last.first, last.support_before, last.unsettled],
    ['1-4-1/evidence/01', 'interrupted', null, ['hint'], true]);
  expect(bad, 'الجلسة', [sc2.cur, sc2.sessions, count(e2, 'session_start', 'S3'), count(e2, 'resume_lesson', 'S3')],
    ['S3', 3, 1, 1]);
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_continue());
  play(s2, kid);
  expect(bad, 'بعد تكملة الجلسة: استئنافات الدرس في S3، والجلسة الجارية', [count(e2, 'resume_lesson', 'S3'), sc2.cur], [1, null]);
  return bad;
}

function caseNonfinal() {
  const { st } = at(13);
  const r = st.event(st.seq, ['confirm', 5]);
  const { sc: sc2 } = reopen('young', st.snapshot());
  const last = sc2.records[sc2.records.length - 1];
  const bad = [];
  expect(bad, 'نتيجة الحدث', r, 'open');
  expect(bad, 'سجل البند', [last.item, last.status, last.first, last.final, last.unsettled],
    ['1-4-1/evidence/02', 'complete', false, 'incomplete', true]);   // 3.1: مكتمل لأن إجابة أولى أُكّدت
  expect(bad, 'الجلسة', [sc2.cur, sc2.sessions], ['S3', 3]);
  return bad;
}

function caseFinal() {
  const { e, sc, st, kid } = at(25);
  st.show(st.seq);
  const before = st.snapshot(), old = st.seq;
  const nRec = before.records.length;                     // سجلات البنود في اللقطة قبل الإجابة
  const r1 = st.event(old, ['confirm', 4]);
  const r2 = st.event(old, ['confirm', 4]);
  const bad = [];
  expect(bad, 'نتيجة الإجابة ثم تكرارها', [r1, r2], ['next', 'ignored']);
  expect(bad, 'نتائج الفحص في المحرك، وحالة المحاولة، وعدد السجلات الجديدة',
    [count(e, 'independence_result'), e.s.checks['1-4-1/check/1'].state, sc.records.length - nRec], [1, 'closed', 1]);
  const after = st.snapshot();
  try {
    const { e: e2, sc: sc2, notes } = reopen('young', after);
    expect(bad, 'بعد الاستعادة من اللقطة الجديدة', [count(e2, 'independence_result'), sc2.records.length, notes],
      [1, nRec + 1, [['current_saved', 'gate', '1-4-2']]]);
    const s2 = new Stepper(e2, sc2);
    s2.open(sc2.g_run(14));
    expect(bad, 'البند التالي لم يُعرض فيُطلب نفسه', s2.pending[0].id, '1-4-2/gate/01');
    play(s2, kid);
    expect(bad, 'نتائج فحص 1-4-1 بعد إكمال المسار', count(e2, 'independence_result', null, { skill: '1-4-1' }), 1);
  } catch (x) {
    if (!(x instanceof persist.Inconsistent)) throw x;
    bad.push('اللقطة بعد الانتقال رُفضت: ' + x.message);
  }
  const { e: e3, sc: sc3 } = reopen('young', before);
  const last = sc3.records[sc3.records.length - 1];
  expect(bad, 'الاستعادة مما قبل الانتقال', [count(e3, 'independence_result'), e3.s.checks['1-4-1/check/1'].state,
    last.item, last.status, last.unsettled, sc3.records.length], [0, 'pending', '1-4-1/checkA/19', 'interrupted', true, nRec + 1]);
  return bad;
}

function caseCap() {
  const { e, sc } = build('young');
  const st = new Stepper(e, sc), kid = new Kid();
  for (const g of ['g_search', 'g_start_session', 'g_follow_learning', 'g_follow_learning']) {
    st.open(sc[g]());
    play(st, kid);
  }
  const bad = [];
  expect(bad, 'بعد بلوغ السقف: المولّد، والجلسة، والمحفوظ', [st.finished, e.s.current, sc.cur, sc.elapsed,
    sc.saved.map((c) => [c.kind, c.act.slot])], [true, null, null, 240, [['check', 5]]]);
  const rec = st.snapshot();
  expect(bad, 'النشاط الجاري في اللقطة', rec.current, null);
  const { e: e2, sc: sc2, notes } = reopen('young', rec);
  expect(bad, 'ملاحظات الاستعادة والجلسة', [notes, sc2.cur, sc2.sessions], [[], null, 4]);
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_follow_learning());
  expect(bad, 'الجلسة التالية', [sc2.cur, count(e2, 'check_resumed', 'S5'), s2.pending[0].id, sc2.elapsed],
    ['S5', 1, '1-4-1/checkA/09', 0]);
  return bad;
}

function caseBroken() {
  const failing = (src) => (skill, w) => {
    if (w.activity === 'check' && w.slot === 3) throw new RangeError('تعذّر تحميل البند');
    return src(skill, w);
  };
  const { st } = at(17, failing);
  st.show(st.seq);
  const before = st.snapshot();
  const bad = [];
  try {
    st.event(st.seq, ['confirm', 3]);
    bad.push('لم يظهر استثناء التحميل');
  } catch (x) {
    if (!(x instanceof RangeError)) throw x;
  }
  expect(bad, 'الطبقة معطّلة', st.broken, true);
  for (const [label, fn] of [['لقطة', () => st.snapshot()], ['حدث', () => st.event(st.seq, ['confirm', 3])]]) {
    try {
      fn();
      bad.push(`${label} بعد انتقال لم يكتمل قُبل`);
    } catch (x) { /* متوقع */ }
  }
  const { e: e2, sc: sc2 } = reopen('young', before);
  expect(bad, 'الاستعادة من المحفوظ السابق', [sc2.cur, sc2.elapsed, sc2.records[sc2.records.length - 1].item,
    count(e2, 'independence_result')], ['S4', 60, '1-4-1/checkA/03', 0]);
  return bad;
}

function caseSession() {
  let { e, sc, st, kid } = at(17);
  const seen = [];
  for (let i = 0; i < 3; i++) {
    ({ e, sc } = reopen('young', st.snapshot()));
    seen.push([sc.cur, sc.sessions, sc.searches, sc.elapsed]);
    st = new Stepper(e, sc);
    st.open(sc.g_continue());
    if (st.pending !== null) {
      const [item, w] = st.pending;
      for (const ev of kid.events(item, w)) st.event(st.seq, ev);
    }
  }
  play(st, kid);
  const bad = [];
  expect(bad, 'الجلسة وعددها وجلسات البحث والوقت بعد كل استعادة', seen,
    [['S4', 4, 1, 60], ['S4', 4, 1, 120], ['S4', 4, 1, 180]]);
  expect(bad, 'أحداث S4: بداية، بدء فحص، استئناف فحص، استئناف درس، ختم',
    ['session_start', 'check_started', 'check_resumed', 'resume_lesson', 'session_end'].map((t) => count(e, t, 'S4')),
    [1, 1, 0, 0, 1]);
  expect(bad, 'بنود S4 المعروضة: الخانات الأربع ثم السقف', sc.records.filter((r) => r.activity === 'check').map((r) => r.item),
    ['1-4-1/checkA/01', '1-4-1/checkA/03', '1-4-1/checkA/05', '1-4-1/checkA/07']);
  expect(bad, 'بعد السقف', [sc.cur, sc.sessions, sc.saved.map((c) => [c.kind, c.act.slot])], [null, 4, [['check', 5]]]);
  return bad;
}

function caseNewday() {
  const { e, st } = at(17);
  const day = e.s.sessions.S4.day;
  const { e: e2, sc: sc2, notes } = reopen('young', st.snapshot(), day + 1);
  const bad = [];
  expect(bad, 'يوم S4', day, 3);
  expect(bad, 'ملاحظات الاستعادة في يوم جديد', notes, [['current_saved', 'check', '1-4-1'], ['session_closed', 'S4']]);
  expect(bad, 'الجلسة بعدها', [sc2.cur, e2.s.current, sc2.stage], [null, null, null]);
  sc2.today = day + 1;
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_follow_learning());
  expect(bad, 'الجلسة الجديدة', [sc2.cur, e2.s.sessions.S5.day, count(e2, 'check_resumed', 'S5'), s2.pending[1].slot],
    ['S5', 4, 1, 2]);
  const r3 = reopen('young', st.snapshot(), day);
  expect(bad, 'الاستعادة في اليوم نفسه', [r3.notes, r3.sc.cur], [[['current_saved', 'check', '1-4-1']], 'S4']);
  return bad;
}

// القاعدة: كل بند خُتم يدخل العدّاد مرة واحدة. المسار المتصل يعرض 20 بند فحص (10 لكل مهارة) و40 بندًا مسجَّلًا
function caseCounters() {
  const bad = [];
  const b0 = build('young');
  const s0 = new Stepper(b0.e, b0.sc);
  s0.open(b0.sc.g_run(14));
  play(s0, new Kid());
  expect(bad, 'بلا إغلاق: عدّاد بنود الفحص وعدد السجلات', [b0.sc.n.check, b0.sc.records.length], [20, 40]);
  let { st, kid } = at(17);
  expect(bad, 'عدّاد الفحص في اللقطة بعد خانة واحدة', st.snapshot().scheduler.state.n.check ?? null, 1);
  const r2 = reopen('young', st.snapshot());
  const s2 = new Stepper(r2.e, r2.sc);
  s2.open(r2.sc.g_run(14));
  play(s2, kid);
  expect(bad, 'بعد إغلاق قبل العرض واستعادة: العدّاد والسجلات', [r2.sc.n.check, r2.sc.records.length], [20, 40]);
  ({ st, kid } = at(17));
  st.show(st.seq);
  const r3 = reopen('young', st.snapshot());
  expect(bad, 'بعد الاستعادة مباشرة: الخانة 1 والخانة 2 المنقطعة', [r3.sc.n.check, r3.sc.records.length], [2, 11]);   // بوابة 2، افتتاح 3، دليل فهم 4، فحص 2. بنود الدرس بلا سجل
  const s3 = new Stepper(r3.e, r3.sc);
  s3.open(r3.sc.g_run(14));
  play(s3, kid);
  expect(bad, 'بعد إكمال المسار: البند المنقطع وبديله محتسبان مرة واحدة', [r3.sc.n.check, r3.sc.records.length], [21, 41]);
  return bad;
}

const baseCounts = (sc) => [sc.records.length, { ...sc.n }];
const voidOf = (records, item) => records.filter((r) => r.item === item)
  .map((r) => [r.status, r.first, r.final, r.support_before, r.support_unanswered || [], r.void ?? null]);

// القاعدة (8.3): إبطال جلسة أسهمت في محاولة غير مكتملة يجعلها «تحتاج إعادة بدء»، فلا تُستأنف. والاستئناف في الجلسة
// نفسها لا يستهلك حصة، لكنه يتحقق من الصلاحية لحظة التنفيذ
function caseValidRestore() {
  const { e, st } = at(21);
  const r = e.apply({ id: 't1', type: 'invalidate_session', target: 'S4' });
  const { e: e2, sc: sc2 } = reopen('young', st.snapshot());
  const before = baseCounts(sc2);
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_continue());
  const bad = [];
  expect(bad, 'قبول الإبطال وحالة المحاولة', [r.ok, e2.s.checks['1-4-1/check/1'].state], [true, 'needs_restart']);
  expect(bad, 'بعد الاستعادة: لا بند معروض، والمولّد انتهى، والجلسة خُتمت', [s2.pending, s2.finished, sc2.cur], [null, true, null]);
  expect(bad, 'سجل المجدول', sc2.log.slice(-1), [[5, 'carry_dropped:check_state', '1-4-1']]);
  expect(bad, 'المخزنان', [sc2.saved, sc2.parked], [[], {}]);
  expect(bad, 'السجلات والعدّادات لم تتغير', baseCounts(sc2), before);
  expect(bad, 'عدّاد بنود الفحص: الخانات الخمس', sc2.n.check, 5);
  expect(bad, 'أحداث S5: استئناف واحد، ولا نتيجة', [count(e2, 'check_resumed', 'S5'), count(e2, 'independence_result')], [1, 0]);
  return bad;
}

function caseValidLive() {
  const bad = [];
  let { e, sc, st } = at(21);
  let before = baseCounts(sc);
  e.apply({ id: 't1', type: 'invalidate_session', target: 'S4' });
  const shown = st.show(st.seq);
  expect(bad, 'قبل العرض: لم يُعرض، وسبب التوقف للبالغ', [shown, st.halt], [false, ['S5', 'check_state', '1-4-1', 'check']]);
  expect(bad, 'قبل العرض: سجل المجدول بلا إجابة مُهملة', sc.log.filter((x) => x[0] === 5),
    [[5, 'carry_dropped:check_state', '1-4-1']]);
  expect(bad, 'قبل العرض: السجلات والعدّادات', baseCounts(sc), before);
  ({ e, sc, st } = at(21));
  st.show(st.seq);
  before = baseCounts(sc);
  const old = st.seq;
  e.apply({ id: 't1', type: 'invalidate_session', target: 'S4' });
  const r1 = st.event(old, ['confirm', 7]);
  const r2 = st.event(old, ['confirm', 7]);
  expect(bad, 'بعد العرض: نتيجة الإجابة ثم تكرارها', [r1, r2], ['void', 'ignored']);
  expect(bad, 'بعد العرض: سجل المجدول', sc.log.filter((x) => x[0] === 5),
    [[5, 'carry_dropped:check_state', '1-4-1'], [5, 'answer_void:check_state', '1-4-1']]);
  // البند عُرض قبل الإبطال: عرضه يُحفظ سجلًا مستبعدًا بلا إجابة (R17-01، و9.1: عرض البند حدث في السجل). والإجابة التي
  // جاءت بعد الإبطال ليست فيه، ولا عدّاد ولا نتيجة
  expect(bad, 'بعد العرض: سجل واحد مستبعد بلا إجابة، والعدّادات كما هي، ولا نتيجة',
    [sc.records.length - before[0], dump(sc.n) === dump(before[1]), voidOf(sc.records, '1-4-1/checkA/11'),
      count(e, 'independence_result')],
    [1, true, [['interrupted', null, 'incomplete', [], [], 'check_state']], 0]);
  expect(bad, 'بعد العرض: الجلسة خُتمت والمحاولة كما هي', [e.s.sessions.S5.ended, e.s.checks['1-4-1/check/1'].state],
    [true, 'needs_restart']);
  return bad;
}

// القاعدة (8.3): إبطال الدليل الذي فتح مهارة يعلّق أنشطتها حتى إعادة التحقق. هذا منع مؤقت: يُركن النشاط بتقدّمه
function caseValidTemporary() {
  const { e, sc, st } = at(39);
  st.show(st.seq);
  const before = baseCounts(sc);
  const r = e.apply({ id: 't1', type: 'invalidate_session', target: 'S6' });
  const res = st.event(st.seq, ['confirm', 4]);
  const bad = [];
  expect(bad, 'الإبطال والتعليق', [r.ok, Object.keys(e.s.suspended).sort()], [true, ['1-4-2']]);
  expect(bad, 'نتيجة الإجابة وسبب التوقف', [res, st.halt], ['void', ['S8', 'suspended', '1-4-2', 'evidence']]);
  const p = sc.parked['1-4-2'] || {};
  expect(bad, 'النشاط مركون بتقدّمه: بند واحد منجز', [p.kind ?? null, (p.act || {}).shown ?? null, p.items ?? null],
    ['evidence', { evidence: 1 }, ['1-4-2/evidence/01']]);
  expect(bad, 'سجل المجدول في S8', sc.log.filter((x) => x[0] === 8),
    [[8, 'carry_parked:suspended', '1-4-2'], [8, 'answer_void:suspended', '1-4-2']]);
  expect(bad, 'سجل واحد مستبعد للبند المعروض بلا إجابة (R17-01)، والعدّادات كما هي',
    [sc.records.length - before[0], dump(sc.n) === dump(before[1]), voidOf(sc.records, '1-4-2/evidence/02')],
    [1, true, [['interrupted', null, 'incomplete', [], [], 'suspended']]]);
  expect(bad, 'S8 خُتمت', e.s.sessions.S8.ended, true);
  return bad;
}

// القاعدة (R17-01): ما سُجّل في البند قبل تغيّر الصلاحية يبقى محفوظًا مع سبب استبعاده، مرة واحدة. لا يتقدم النشاط به،
// ولا يدخل المؤشرات، والحدث الذي جاء بعد التغيّر لا يُحتسب
// يكمل المسار إلى نهايته، ويعيد بنود دليل فهم المهارة التي عُرضت: المعرّف والدور والبند الذي يحل محله وعدّ الإعادة
function servedAfter(e, st, kid, skill = '1-4-2') {
  const out = [];
  while (st.pending !== null) {
    const [item, w] = st.pending;
    if (w.activity === 'evidence' && item.skill === skill) {
      out.push([item.id.slice(-2), w.role, (w.replaces || '').slice(-2), w.reshown]);
    }
    for (const ev of kid.events(item, w)) st.event(st.seq, ev);
  }
  return out;
}

const proofs = (e, skill = '1-4-2') => e.s.log.filter((x) => x.type === 'understanding_proved' && x.skill === skill)
  .map((x) => (x.items || []).map((i) => i.slice(-2)));

function caseVoidHistory() {
  const bad = [];
  const ITEM = '1-4-2/evidence/02';                         // S8، دليل فهم 1-4-2. قبله بند واحد منجز
  const inval = (e) => e.apply({ id: 't1', type: 'invalidate_session', target: 'S6' });
  // أ) إجابة مؤكدة خاطئة ثم طلب تلميح، ثم التعليق، ثم إنهاء
  let { e, sc, st } = at(39);
  let n0 = dump(sc.n);
  const ind0 = dump(indicators(sc.records));
  let r = [st.event(st.seq, ['confirm', 999]), st.event(st.seq, ['support', 'hint'])];
  const held = st.snapshot().current.journal.raw;
  inval(e);
  r.push(st.event(st.seq, ['end']));
  expect(bad, 'أ: نتائج الأحداث الثلاثة', r, ['open', 'open', 'void']);
  expect(bad, 'أ: اللقطة قبل التعليق تحمل الحدثين', held, [['confirm', 999], ['support', 'hint']]);
  const want = [['complete', false, 'incomplete', [], ['hint'], 'suspended']];
  expect(bad, 'أ: سجل البند بعد التوقف: مرة واحدة، بالإجابة الأولى والتلميح وسبب الاستبعاد', voidOf(sc.records, ITEM), want);
  const p = sc.parked['1-4-2'] || {};
  expect(bad, 'أ: النشاط مركون عند بنده المنجز الواحد، بلا البند المستبعد', [(p.act || {}).shown ?? null, p.items ?? null],
    [{ evidence: 1 }, ['1-4-2/evidence/01']]);
  expect(bad, 'أ: العدّادات والمؤشرات لا يدخلها البند المستبعد', [dump(sc.n) === n0, dump(indicators(sc.records)) === ind0],
    [true, true]);
  const snap = st.snapshot();
  const j = (snap.current || {}).journal || {};
  expect(bad, 'أ: اللقطة بعد التوقف: السجل فيها مرة، وليس في بند جارٍ', [voidOf(snap.records, ITEM), j.item === ITEM],
    [want, false]);
  let r2 = reopen('young', snap);
  let r3 = reopen('young', persist.snapshot(r2.e, r2.sc));
  expect(bad, 'أ: بعد استعادتين', [voidOf(r2.sc.records, ITEM), voidOf(r3.sc.records, ITEM)], [want, want]);
  expect(bad, 'أ: النشاط باقٍ مركونًا ولا دليل فهم جديد',
    ['1-4-2' in r3.sc.parked, count(r3.e, 'understanding_proved', null, { skill: '1-4-2' })], [true, 0]);
  // ب) طلب دعم بلا إجابة قبل التعليق، ثم إجابة بعده
  ({ e, sc, st } = at(39));
  r = [st.event(st.seq, ['support', 'hint'])];
  inval(e);
  r.push(st.event(st.seq, ['confirm', 4]));
  expect(bad, 'ب: نتائج الحدثين', r, ['open', 'void']);
  expect(bad, 'ب: سجل البند: منقطع ومعه التلميح، والإجابة اللاحقة ليست فيه', voidOf(sc.records, ITEM),
    [['interrupted', null, 'incomplete', ['hint'], [], 'suspended']]);
  // ج) بند عُرض بلا حدث، ثم إجابة بعد التعليق: عرضه محفوظ (9.1: عرض البند حدث في السجل)، والإجابة لا تُحتسب
  ({ e, sc, st } = at(39));
  st.show(st.seq);
  inval(e);
  const rc = st.event(st.seq, ['confirm', 4]);
  expect(bad, 'ج: نتيجة الإجابة وسجل البند المعروض', [rc, voidOf(sc.records, ITEM)],
    ['void', [['interrupted', null, 'incomplete', [], [], 'suspended']]]);
  // د) الحدثان في اللقطة، والتعليق قبل الاستعادة: الاستعادة تحفظهما مستبعدَين ولا تعطيهما للنشاط
  ({ e, sc, st } = at(39));
  n0 = dump(sc.n);
  st.event(st.seq, ['confirm', 999]);
  st.event(st.seq, ['support', 'hint']);
  inval(e);
  r2 = reopen('young', st.snapshot());
  expect(bad, 'د: ملاحظات الاستعادة', r2.notes,
    [['void_item', '1-4-2', ITEM, 'suspended'], ['current_saved', 'evidence', '1-4-2']]);
  expect(bad, 'د: السجل والعدّاد والنشاط المحفوظ', [voidOf(r2.sc.records, ITEM), dump(r2.sc.n) === n0,
    r2.sc.saved.filter((c) => c.kind === 'evidence').map((c) => c.act.shown)], [want, true, [{ evidence: 1 }]]);
  const s2 = new Stepper(r2.e, r2.sc);
  s2.open(r2.sc.g_continue());
  r3 = reopen('young', s2.snapshot());
  expect(bad, 'د: بعد التكملة واستعادة ثانية: مركون، والسجل مرة واحدة', ['1-4-2' in r3.sc.parked, voidOf(r3.sc.records, ITEM)],
    [true, want]);

  // R18-01: الاستبعاد من التقييم لا يمحو التعرّض. بعد رفع التعليق لا يعود البند الذي أُجيب عنه وطُلب فيه تلميح دليلًا
  // جديدًا: يحل محله بديل نوعه في الجولة (25: ف2، الجولة 1، حقيقته 1 و9 لم ترد في بنود نوعه الأربعة). ثم ف3 (05، 06)
  // ثم ف4 (09، 10) كما هي. والبند 01 المنجز قبل التعليق باقٍ في الدليل
  const AFTER = [['25', 'evidence.alternate', '02', 0], ['05', 'evidence', '', 0], ['06', 'evidence', '', 0],
    ['09', 'evidence', '', 0], ['10', 'evidence', '', 0]];
  const PROOF = [['01', '25', '05', '06', '09', '10']];
  const exposedThenVoid = (source = null) => {
    const x = at(39, source);
    x.st.event(x.st.seq, ['confirm', 999]);
    x.st.event(x.st.seq, ['support', 'hint']);
    inval(x.e);
    x.st.event(x.st.seq, ['end']);
    return x;
  };
  const verdict = (label, e1, sc1, got) => {
    const alt = sc1.records.filter((q) => q.item === '1-4-2/evidence/25')
      .map((q) => [q.status, q.first, q.replaces ?? null, q.fact_seen_before ?? null, q.void ?? null]);
    expect(bad, label + ': البنود المعروضة بعد رفع التعليق', got, AFTER);
    expect(bad, label + ': دليل الفهم مرة واحدة ببنوده، وليس البند المستبعد منها', proofs(e1), PROOF);
    expect(bad, label + ': السجل المستبعد مرة واحدة، ولا سجل آخر للبند', voidOf(sc1.records, ITEM), want);
    expect(bad, label + ': سجل البديل يذكر البند الذي حلّ محله وأن حقيقته سبق عرضها', alt,
      [['complete', true, ITEM, true, null]]);
  };
  // هـ) المسار المتصل إلى نهايته
  let x = exposedThenVoid();
  verdict('هـ', x.e, x.sc, servedAfter(x.e, x.st, x.kid));
  // و) إغلاق بعد التوقف مباشرة، ثم استعادة وتكملة
  x = exposedThenVoid();
  let y = reopen('young', x.st.snapshot());
  let sy = new Stepper(y.e, y.sc);
  sy.open(y.sc.g_run(14));
  verdict('و', y.e, y.sc, servedAfter(y.e, sy, x.kid));
  // ز) إغلاق والبديل مطلوب لم يُعرض بعد، ثم استعادة وتكملة
  x = exposedThenVoid();
  while (x.st.pending !== null && x.st.pending[1].role !== 'evidence.alternate') {
    for (const ev of x.kid.events(...x.st.pending)) x.st.event(x.st.seq, ev);
  }
  y = reopen('young', x.st.snapshot());
  sy = new Stepper(y.e, y.sc);
  sy.open(y.sc.g_run(14));
  verdict('ز', y.e, y.sc, servedAfter(y.e, sy, x.kid));
  // ح) لا بديل في المحتوى: نفاده يُعلن في سجل المجدول، والجولة تنتهي بلا حكم (لا «لم يثبت»). لا يُعاد البند 02.
  // ثم الجولة الثانية ببنودها: ف2 (13، 14) ثم ف3 (17، 18) ثم ف4 (21، 22)
  x = exposedThenVoid((src) => (s, w) => (w.role === 'evidence.alternate' ? null : src(s, w)));
  let got = servedAfter(x.e, x.st, x.kid);
  const marks = x.sc.log.filter((q) => q[2] === '1-4-2' && q[1].startsWith('evidence_')).map((q) => q[1]);
  expect(bad, 'ح: نفاد البدائل معلن، وبلا «لم يثبت»', marks, ['evidence_no_alternate']);
  expect(bad, 'ح: بنود الجولة الثانية، وليس البند 02 منها', got.map((g) => g[0]), ['13', '14', '17', '18', '21', '22']);
  expect(bad, 'ح: دليل الفهم ببنود الجولة الثانية وحدها', proofs(x.e), [['13', '14', '17', '18', '21', '22']]);
  expect(bad, 'ح: السجل المستبعد باقٍ مرة واحدة', voidOf(x.sc.records, ITEM), want);
  // ط) بند عُرض بلا حدث ثم استُبعد: لم تُقبل فيه إجابة في محاولة صالحة، فيُعاد عرضه نفسه موصوفًا بالإعادة (3.5)، ويدخل الدليل
  x = at(39);
  x.st.show(x.st.seq);
  inval(x.e);
  x.st.event(x.st.seq, ['end']);
  got = servedAfter(x.e, x.st, x.kid);
  expect(bad, 'ط: البند نفسه يُعاد عرضه وعدّ الإعادة 1', got.slice(0, 2), [['02', 'evidence', '', 1], ['05', 'evidence', '', 0]]);
  expect(bad, 'ط: الدليل ببنوده الأصلية', proofs(x.e), [['01', '02', '05', '06', '09', '10']]);
  return bad;
}

// القاعدة (R19-01): تاريخ التعرّض في السجلات، لا في كائن النشاط. التعليق أثناء أول بند في دليل الفهم يُسقط النشاط (لم
// يكتمل فيه بند)، ثم يُنشأ نشاط جديد بعد رفع التعليق. البند 01 (ف2، الجولة 1) إن طُلب فيه دعم أو أُكدت فيه إجابة لا
// يعود: بديله 25. وإن عُرض فقط ولم تُقبل فيه إجابة في محاولة صالحة أُعيد عرضه وعدّ الإعادة 1. وبلا بدائل في المحتوى:
// يُعلن النفاد، ثم الجولة الثانية ببنودها
function caseFirstItem() {
  const bad = [];
  const ITEM = '1-4-2/evidence/01';
  const ALT = [['25', 'evidence.alternate', '01', 0], ['02', 'evidence', '', 0], ['05', 'evidence', '', 0],
    ['06', 'evidence', '', 0], ['09', 'evidence', '', 0], ['10', 'evidence', '', 0]];
  const SAME = [['01', 'evidence', '', 1], ...ALT.slice(1)];
  const ROUND2 = ['13', '14', '17', '18', '21', '22'].map((i) => [i, 'evidence', '', 0]);
  const KINDS = [['طلب دعم فقط', [['support', 'hint']], ['interrupted', null, 'incomplete', ['hint'], [], 'suspended'], ALT],
    ['إجابة مؤكدة', [['confirm', 999]], ['complete', false, 'incomplete', [], [], 'suspended'], ALT],
    ['العرض وحده', null, ['interrupted', null, 'incomplete', [], [], 'suspended'], SAME]];
  const without = (src) => (s, w) => (w.role === 'evidence.alternate' ? null : src(s, w));
  const run = (evs, mode, bare) => {
    let { e, sc, st, kid } = at(38, bare ? without : null);
    if (st.pending[0].id !== ITEM || e.s.current !== 'S8') throw new Error('الموضع 38 ليس أول بند دليل الفهم في S8');
    if (evs === null) st.show(st.seq);
    for (const ev of evs || []) st.event(st.seq, ev);
    e.apply({ id: 't1', type: 'invalidate_session', target: 'S6' });
    if (mode !== 'قبل التوقف') st.event(st.seq, ['confirm', 6]);   // تصل بعد التعليق: لا تُحتسب
    if (mode !== 'متصل') {
      ({ e, sc } = reopen('young', st.snapshot()));
      if (bare) sc.source = without(sc.source);
      st = new Stepper(e, sc);
      st.open(sc.g_run(14));
    }
    return { e, sc, got: servedAfter(e, st, kid) };
  };
  for (const [name, evs, rec, after] of KINDS) {
    for (const mode of ['متصل', 'قبل التوقف', 'بعد التوقف']) {
      const label = `${name}، ${mode}`;
      let r = run(evs, mode, false);
      expect(bad, label + ': البنود المعروضة بعد رفع التعليق', r.got, after);
      expect(bad, label + ': دليل الفهم مرة واحدة ببنوده', proofs(r.e), [after.map((g) => g[0])]);
      expect(bad, label + ': السجل المستبعد مرة واحدة' + (after === SAME ? '' : '، ولا سجل آخر للبند'),
        voidOf(r.sc.records, ITEM).filter((q) => q[5]), [rec]);
      expect(bad, label + ': عدد سجلات البند', voidOf(r.sc.records, ITEM).length, after === SAME ? 2 : 1);
      if (after === SAME) continue;
      r = run(evs, mode, true);                             // المحتوى بلا بدائل
      const marks = r.sc.log.filter((q) => q[2] === '1-4-2' && q[1].startsWith('evidence_')).map((q) => q[1]);
      expect(bad, label + '، بلا بدائل: النفاد معلن مرة، وبلا «لم يثبت»', marks, ['evidence_no_alternate']);
      expect(bad, label + '، بلا بدائل: الجولة الثانية ببنودها، وليس 01 منها', r.got, ROUND2);
      expect(bad, label + '، بلا بدائل: الدليل ببنود الجولة الثانية', proofs(r.e), [ROUND2.map((g) => g[0])]);
      expect(bad, label + '، بلا بدائل: السجل المستبعد مرة واحدة', voidOf(r.sc.records, ITEM), [rec]);
    }
  }
  return bad;
}

// القاعدة (R18-01 في افتتاح الدرس): إعادة البند للتعليم غير استعماله دليلًا لقرار.
// افتتاح 1-4-2 في S7: «جرّب أولًا» tryfirst/03 ثم tryfirst/04، ثم الموجَّهة opening/03 و04 و05.
// الطفل هنا يخطئ قبل الدرس، ثم يعرف المهارة بعد التعليق (كأنه تعلّمها خارج التطبيق)، ليظهر أثر البند المعاد
function caseOpeningVoid() {
  const bad = [];
  const finish = (e, sc, st, kid) => {
    kid.known.add('1-4-2');
    const out = [];
    while (st.pending !== null) {
      const [item, w] = st.pending;
      if (w.activity === 'opening' && item.skill === '1-4-2') out.push([item.id.slice(6), w.reshown, Boolean(w.repeated)]);
      for (const ev of kid.events(item, w)) st.event(st.seq, ev);
    }
    const res = e.s.log.filter((x) => x.type === 'lesson_opening_result' && x.skill === '1-4-2').map((x) => x.outcome);
    const marked = sc.records.filter((r) => r.repeated_after_void).map((r) => r.item.slice(6));
    return [out, res, marked];
  };
  const run = (n, evs, mode) => {
    let { e, sc, st, kid } = at(n);
    const first = st.pending[0].id;
    for (const ev of evs) st.event(st.seq, ev);
    e.apply({ id: 't1', type: 'invalidate_session', target: 'S6' });
    if (mode !== 'قبل التوقف') st.event(st.seq, ['end']);
    if (mode !== 'متصل') {
      ({ e, sc } = reopen('young', st.snapshot()));
      st = new Stepper(e, sc);
      st.open(sc.g_run(14));
    }
    return [first.slice(6), ...finish(e, sc, st, kid)];
  };
  const GUIDED = [['opening/03', 0, false], ['opening/04', 0, false], ['opening/05', 0, false]];
  const EXPOSED = [['confirm', 999], ['support', 'hint']];
  for (const mode of ['متصل', 'قبل التوقف', 'بعد التوقف']) {
    // أ) أول بند «جرّب أولًا» مستهلك: لا يُعرض ثانية ولا بديل له. الثاني يُعرض ويصح، ولا يُتخطى الشرح بهما: تأتي
    //    الموجَّهة الثلاث، وتصح كلها فينتهي الدرس مبكرًا بها (skip)، لا بالبند المستهلك
    expect(bad, `أ، ${mode}`, run(28, EXPOSED, mode), ['tryfirst/03', [['tryfirst/04', 0, false], ...GUIDED], ['skip'], []]);
    // ب) ثاني بند «جرّب أولًا» مستهلك (والأول أُجيب خطأً قبل التعليق): لا يُعرض ثانية، ثم الموجَّهة الثلاث
    expect(bad, `ب، ${mode}`, run(29, EXPOSED, mode), ['tryfirst/04', GUIDED, ['skip'], []]);
    // ج) أول بند موجَّه مستهلك: يُعاد عرضه للتعليم موسومًا بأنه مكرر، ونجاحه لا ينهي الدرس مبكرًا ولا يُسجَّل تعثّر:
    //    الدرس كاملًا (full_help)، ولا تُعرض بقية الموجَّهة
    expect(bad, `ج، ${mode}`, run(30, EXPOSED, mode), ['opening/03', [['opening/03', 1, true]], ['full_help'], ['opening/03']]);
  }
  // د) بند موجَّه عُرض ولم تُقبل فيه إجابة في محاولة صالحة: يُعاد عرضه موسومًا بالإعادة، ويُحتسب كغيره
  const { e, sc, st, kid } = at(30);
  st.show(st.seq);
  e.apply({ id: 't1', type: 'invalidate_session', target: 'S6' });
  st.event(st.seq, ['end']);
  const [out, res] = finish(e, sc, st, kid);
  expect(bad, 'د: المعروض بلا إجابة مقبولة', [out, res], [[['opening/03', 1, false], ...GUIDED.slice(1)], ['skip']]);
  return bad;
}

const RESULTS = ['pass', 'fail', 'help'];
const VARIANTS = { gate: [...RESULTS, 'interrupted'].map((result) => ({ result })), short: [{ ok: true }, { ok: false }],
  opening: ['skip', 'full_error', 'full_help'].map((outcome) => ({ outcome })), evidence: [{}],
  check: RESULTS.map((result) => ({ result })), retention: [0, 1, 2, 3, 4, 5].map((correct) => ({ correct })) };
const TYPE = { gate: 'gate_result', short: 'short_check_result', opening: 'lesson_opening_result',
  evidence: 'understanding_proved', check: 'independence_result', retention: 'retention_result' };

function verdicts(e, sc) {
  const v = sc.live;
  if (v === null || v.kind === 'show') return null;
  const act = v.act, kind = v.kind;
  const base = { type: TYPE[kind], id: 'ask', session: sc.cur, skill: act.skill };
  if (kind === 'check') base.check_id = act.check_id;
  const got = VARIANTS[kind].map((extra) => {
    const r = e.preflight({ ...base, ...extra });
    return r.ok ? 'ok' : r.code;
  });
  const c = e.may_continue(kind, sc.cur, act.skill, act.check_id ?? null);
  return [kind, got, c.ok ? 'ok' : c.code];
}

function caseValidHealthy() {
  const bad = [];
  const a = at(21);
  const r2 = reopen('young', a.st.snapshot());
  const s2 = new Stepper(r2.e, r2.sc);
  s2.open(r2.sc.g_continue());
  expect(bad, 'سليمة: البند المعروض، واستئنافات S5، وحصتها التعليمية المستهلكة',
    [s2.pending[0].id, count(r2.e, 'check_resumed', 'S5'), r2.e.s.sessions.S5.teach], ['1-4-1/checkA/11', 1, 1]);
  // حكم الاستمرار لا يقرأ النتيجة: عند كل طلب بند في المسار، وبعد كل إبطال، حكم قبول حدث الختام واحد لكل قيم
  // نتيجته، وهو حكم may_continue نفسه
  const seen = {}, split = [];
  const probe = (e, sc, label) => {
    const v = verdicts(e, sc);
    if (v === null) return;
    const [kind, got, c] = v;
    (seen[kind] ||= new Set()).add(c);
    if (new Set(got).size !== 1 || got[0] !== c) split.push([label, kind, got, c]);
  };
  const b = build('retention');
  const st = new Stepper(b.e, b.sc), kid = new Kid();
  st.open(b.sc.g_run(100));
  for (let k = 0; st.pending !== null; k++) {
    probe(b.e, b.sc, k);
    const [item, w] = st.pending;
    for (const ev of kid.events(item, w)) st.event(st.seq, ev);
  }
  for (const [n, target] of [[21, 'S4'], [21, 'S3'], [39, 'S6'], [1, null], [13, 'S2']]) {
    const x = at(n);
    if (target) x.e.apply({ id: 't1', type: 'invalidate_session', target });
    else x.e.apply({ id: 't1', type: 'session_end', session: x.sc.cur });   // جلسة خُتمت من خارج المجدول
    probe(x.e, x.sc, [n, target]);
  }
  expect(bad, 'مواضع يختلف فيها الحكم باختلاف النتيجة', split, []);
  // جرد لما بلغه الفحص، لا نتيجة مشتقة من قاعدة: يثبت أن المقارنة جرت على أحكام قبول ورفض متنوعة
  expect(bad, 'الأنواع المفحوصة وأحكامها',
    Object.fromEntries(Object.keys(seen).sort().map((k) => [k, [...seen[k]].sort()])),
    { check: ['check_state', 'ok', 'understanding_first'], evidence: ['lesson_idle', 'ok', 'suspended'],
      gate: ['no_session', 'ok'], opening: ['ok'], retention: ['ok'] });
  return bad;
}

// القاعدة (3.1 و3.6): «أحتاج مساعدة» في بند فحص ينهي البند منقطعًا ومعه الطلب، ويغلق المحاولة «انتهت بطلب دعم»،
// لا «لم تُجتز». والمحاولة التالية في يوم لاحق وببنود جديدة
function caseHelpCheck() {
  const { e, sc, st, kid } = at(17);
  st.show(st.seq);
  const old = st.seq;
  const r1 = st.event(old, ['support', 'requested']);
  const r2 = st.event(old, ['support', 'requested']);
  const bad = [];
  expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored']);
  expect(bad, 'نتائج الفحص في المحرك وحالة المحاولة', [e.s.log.filter((x) => x.type === 'independence_result')
    .map((x) => x.result), e.s.checks['1-4-1/check/1'].state], [['help'], 'closed']);
  expect(bad, 'سجل البند: مرة واحدة، منقطع، ومعه الطلب، بلا إجابة', sc.records.filter((r) => r.item === '1-4-1/checkA/03')
    .map((r) => [r.status, r.first, r.support_before, r.final]), [['interrupted', null, ['requested'], 'incomplete']]);
  // المولّد مضى إلى اليوم التالي وبدأ المحاولة الثانية (3.6: بعد «انتهت بطلب دعم» يكفي اليوم اللاحق)، فالفحص الجاري في
  // اللقطة هو المحاولة الثانية. المحاولة الأولى مغلقة ولا تُفتح
  const { e: e2, sc: sc2 } = reopen('young', st.snapshot());
  expect(bad, 'بعد الاستعادة: الفحص المحفوظ هو المحاولة الثانية وحدها، والأولى مغلقة بنتيجة واحدة',
    [sc2.saved.filter((c) => c.kind === 'check').map((c) => c.act.check_id), count(e2, 'independence_result'),
      e2.s.checks['1-4-1/check/1'].state], [['1-4-1/check/2'], 1, 'closed']);
  const s2 = new Stepper(e2, sc2);
  s2.open(sc2.g_run(14));
  play(s2, kid);
  const second = e2.s.log.filter((x) => x.type === 'check_started' && x.check_id === '1-4-1/check/2');
  expect(bad, 'المحاولة الثانية: بدأت مرة، وفي يوم بعد يوم الأولى (3)',
    [second.length, second.length > 0 && e2.s.sessions[second[0].session].day > 3], [1, true]);
  const later = sc2.records.filter((r) => r.activity === 'check' && r.skill === '1-4-1').slice(2)
    .map((r) => r.item.split('/')[1]);
  expect(bad, 'بنود المحاولة الثانية كلها من مجموعتها الجديدة', [...new Set(later)].sort(), ['checkB']);
  expect(bad, 'نتائج فحص 1-4-1 بترتيبها', e2.s.log.filter((x) => x.type === 'independence_result' && x.skill === '1-4-1')
    .map((x) => x.result), ['help', 'pass']);
  return bad;
}

// القاعدة (6.1): طلب الدعم في البوابة ينهيها «انتهت بطلب دعم»، ولا تُسجَّل المهارة «متعثّر فيها»
function caseHelpGate() {
  const { e, sc, st } = at(0);
  const old = st.seq;
  const r1 = st.event(old, ['support', 'requested']);
  const r2 = st.event(old, ['support', 'requested']);
  const bad = [];
  expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored']);
  expect(bad, 'نتائج البوابة في المحرك', e.s.log.filter((x) => x.type === 'gate_result').map((x) => x.result), ['help']);
  expect(bad, 'حالة المهارة ليست «متعثّر فيها»', e.derive()['1-4-1'] !== 'stumbled', true);
  const rec = sc.records[0];
  expect(bad, 'سجل البند', [rec.item, rec.status, rec.first, rec.support_before],
    ['1-4-1/gate/01', 'interrupted', null, ['requested']]);
  expect(bad, 'عدد سجلات البوابة: بند واحد', sc.records.length, 1);
  return bad;
}

// العقد: الحدث غير المسموح يُرفض قبل أي تغيير، بسبب واضح
function caseContract() {
  const bad = [];
  const refused = (n, events, label) => {
    const { st } = at(n);
    st.show(st.seq);
    const before = dump(st.snapshot()), seq = st.seq;
    const got = events.map((ev) => [st.event(seq, ev), Boolean(st.reject)]);
    expect(bad, label + ': كلها مرفوضة بسبب', got, events.map(() => ['rejected', true]));
    expect(bad, label + ': لا تغيير في اللقطة ولا في الطلب', [dump(st.snapshot()) === before, st.seq === seq, st.raw], [true, true, []]);
    return [st, seq];
  };
  let [st, seq] = refused(12, [['support', 'requested'], ['support', 'adult'], ['end'], ['foo'], ['confirm'],
    ['confirm', '6'], 'confirm', ['support'], []], 'بند تعليم (دليل فهم)');
  expect(bad, 'بند تعليم: تلميح ثم إجابة ثم إنهاء', [st.event(seq, ['support', 'hint']), st.event(seq, ['confirm', 6]),
    st.event(seq, ['end'])], ['open', 'open', 'next']);
  [st, seq] = refused(17, [['support', 'hint'], ['support', 'someone'], ['support', 'adult'], ['end'], ['interrupt']],
    'بند تقييم (فحص)');
  expect(bad, 'بند تقييم: التأكيد ينهيه', st.event(seq, ['confirm', 3]), 'next');
  [st, seq] = refused(5, [['confirm', 5], ['support', 'hint'], ['support', 'requested']], 'بند عرض (درس)');
  expect(bad, 'بند عرض: الإنهاء', st.event(seq, ['end']), 'next');
  return bad;
}

// مستوى البند وحده (3.1 بقرار 17 نوفمبر): الطلب ينهي بند فحص الاحتفاظ منقطعًا ومعه الطلب. أثره على الجولة (تنتهي بلا
// نتيجة، ثم تثبيت، ثم جولة في يوم لاحق ببنود بديلة) نُفّذ في ت3 وتفحصه tests/test_retention_help
function caseHelpRetention() {
  const { e, sc } = build('retention');
  const st = new Stepper(e, sc), kid = new Kid();
  st.open(sc.g_run(100));
  while (st.pending !== null && st.pending[1].activity !== 'retention') {
    const [item, w] = st.pending;
    for (const ev of kid.events(item, w)) st.event(st.seq, ev);
  }
  const item = st.pending[0], old = st.seq;
  const r1 = st.event(old, ['support', 'requested']);
  const r2 = st.event(old, ['support', 'requested']);
  const bad = [];
  expect(bad, 'نتيجة الطلب ثم تكراره', [r1, r2], ['next', 'ignored']);
  expect(bad, 'سجل البند: مرة واحدة، منقطع، ومعه الطلب', sc.records.filter((r) => r.item === item.id)
    .map((r) => [r.activity, r.status, r.first, r.support_before]), [['retention', 'interrupted', null, ['requested']]]);
  return bad;
}

console.log('ب) حالات بنتائج مكتوبة يدويًا');
for (const [title, fn] of [
  ['1. إغلاق عند عرض البند (الخانة 2 من الفحص): يُختم «غير محسوم» منقطعًا، والجلسة S4 نفسها تُكمَل بوقتها (60 ثانية) '
    + 'وببديل الخانة، بلا بداية جلسة ولا استئناف فحص، ويُجتاز الفحص، والبند المنقطع في السجلات مرة واحدة', caseShown],
  ['2. إغلاق بعد طلب دعم في بند دليل فهم: السجل منقطع ومعه الدعم، والجلسة S3 تُكمَل بلا استئناف درس ثانٍ', caseSupport],
  ['3. إغلاق بعد إجابة غير نهائية (خاطئة) في بند دليل فهم: الإجابة الأولى الخاطئة محفوظة، والبند «مكتمل» بقاعدة 3.1 '
    + 'ونتيجته النهائية «لم تكتمل»', caseNonfinal],
  ['4. الإجابة النهائية انتقال واحد: آخر خانة تُصدر نتيجة الفحص مرة واحدة، وتكرار التأكيد يُهمل. اللقطة بعده تُستعاد '
    + 'كاملة والبند التالي يُطلب نفسه. والمحفوظ قبله كامل: لا نتيجة في المحرك والبند «غير محسوم»', caseFinal],
  ['5. بلوغ السقف بعد ختم البند: تُختم الجلسة ويُحفظ الفحص عند الخانة 5، واللقطة بلا نشاط جارٍ، والجلسة التالية تستأنفه '
    + 'بحدث واحد ووقت من الصفر', caseCap],
  ['6. استثناء داخل الانتقال: الطبقة تتعطل فلا لقطة ولا حدث بعده، والمحفوظ السابق يُستعاد كاملًا', caseBroken],
  ['7. ثلاثة إغلاقات في جلسة واحدة: لا جلسة جديدة ولا جلسة بحث، والوقت 60 ثم 120 ثم 180 لا يبدأ من الصفر، ولا حدث '
    + 'استئناف يستهلك حصة، والسقف يحلّ بعد الخانة الرابعة كما في التشغيل المتصل', caseSession],
  ['8. انتقال يوم الأسرة: الاستعادة في يوم جديد تختم S4، والجلسة التالية S5 تستأنف الفحص بحدثه. وفي اليوم نفسه تبقى '
    + 'S4 مفتوحة', caseNewday],
  ['9. العدّادات (R16-03): كل بند خُتم يُحتسب مرة واحدة. 20 بند فحص و40 سجلًا بلا إغلاق وبعد إغلاق واستعادة. والبند '
    + 'الذي يُختم منقطعًا أثناء الاستعادة يدخل العدّاد عندها، فيصير المجموع 21 و41 مع بديله', caseCounters],
  ['10. الصلاحية قبل الاستعادة (R16-01): أُبطلت S4 والفحص في S5 ينتظر الخانة 6، ثم حُفظ واستُعيد. لا يُعرض بند: يُسقط '
    + 'النشاط «يحتاج إعادة بدء»، وتُختم الجلسة، والسجلات والعدّادات كما هي، ولا نتيجة', caseValidRestore],
  ['11. الصلاحية في الجلسة الحية (R16-01): إبطال قبل عرض السؤال التالي فلا يُعرض، وإبطال بعد عرضه وقبل تأكيده فلا '
    + 'تُحتسب الإجابة دليلًا ولا خطأً، وتكرارها يُهمل. والسبب يُحفظ للبالغ', caseValidLive],
  ['12. المنع المؤقت (R16-01): تعليق المهارة أثناء دليل فهمها يركن النشاط بتقدّمه ولا يُسقطه، والإجابة لا تُحتسب',
    caseValidTemporary],
  ['13. حالة سليمة: الاستئناف في الجلسة نفسها بلا حصة ولا حدث إضافيين. وحكم الاستمرار لا يقرأ النتيجة: هو حكم '
    + 'قبول حدث الختام لكل قيم نتيجته، عند كل طلب بند وبعد كل إبطال', caseValidHealthy],
  ['14. «أحتاج مساعدة» في فحص الاستقلال (R16-02): طلب واحد ينهي البند والمحاولة «انتهت بطلب دعم» بلا إخفاق، وتكراره '
    + 'يُهمل، واللقطة بعده لا تعيد فتح الفحص، والمحاولة الثانية في يوم لاحق ببنود جديدة', caseHelpCheck],
  ['15. «أحتاج مساعدة» في البوابة (R16-02): تنتهي «انتهت بطلب دعم»، ولا تُسجَّل المهارة «متعثّر فيها»', caseHelpGate],
  ['16. عقد الأحداث (R16-02): نوع غير مسموح للبند يُرفض بسبب قبل أي تغيير، في بند تعليم وبند تقييم وبند عرض',
    caseContract],
  ['17. «أحتاج مساعدة» في فحص الاحتفاظ، مستوى البند وحده: ينتهي البند منقطعًا ومعه الطلب، وتكراره يُهمل',
    caseHelpRetention],
  ['18. تاريخ البند عند توقف نشاطه (R17-01): الإجابة المؤكدة وطلب التلميح قبل تغيّر الصلاحية يبقيان في سجل البند مرة '
    + 'واحدة مع سبب الاستبعاد، عبر الحفظ والاستعادة المتكررين. لا يتقدم النشاط بهما ولا يدخلان العدّاد ولا المؤشرات، '
    + 'والحدث اللاحق للتغيّر لا يُحتسب. وكذلك طلب دعم بلا إجابة، وبند عُرض بلا حدث، والتعليق قبل الاستعادة. '
    + 'وبعد رفع التعليق (R18-01): البند الذي أُجيب عنه وطُلب فيه تلميح لا يعود دليلًا، ويحل محله بديل نوعه، في المسار '
    + 'المتصل وبعد الإغلاق والاستعادة. وبلا بديل يُعلن النفاد ولا يُعاد البند. والبند الذي عُرض بلا حدث يُعاد عرضه',
    caseVoidHistory],
  ['19. التعليق أثناء أول بند في دليل الفهم (R19-01): النشاط يُسقط ثم يُنشأ من جديد، وتاريخ التعرّض باقٍ في السجلات. '
    + 'طلب دعم فقط، أو إجابة مؤكدة: البند لا يعود ويحل محله بديله. العرض وحده: يُعاد عرضه موسومًا. كلٌّ في المسار '
    + 'المتصل، ومع حفظ واستعادة قبل التوقف وبعده، وبمحتوى بلا بدائل، إلى ما بعد رفع التعليق وإصدار الدليل',
    caseFirstItem],
  ['20. افتتاح الدرس بعد بند مستهلك (R18-01): بند «جرّب أولًا» المستهلك لا يُعرض ثانية ولا يتخطى الشرح ولا يُعدّ '
    + 'خطأ. والبند الموجَّه المستهلك يُعاد للتعليم موسومًا بأنه مكرر، ونجاحه لا ينهي الدرس مبكرًا ولا يُسجَّل تعثّر. '
    + 'في المسار المتصل ومع حفظ واستعادة قبل التوقف وبعده. والمعروض بلا إجابة مقبولة يُعاد موسومًا ويُحتسب',
    caseOpeningVoid]]) {
  let bad;
  try { bad = fn(); } catch (x) { bad = ['استثناء: ' + (x.stack || x).toString().split('\n').slice(0, 2).join(' ')]; }
  check(title, bad);
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
