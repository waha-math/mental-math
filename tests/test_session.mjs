// جلسة واحدة للواجهة (Scheduler.g_session): تكرارها يساوي g_run. الحالات والنتائج المتوقعة في tests/test_session.py.
//
//     node tests/test_session.mjs [مجلد app]
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
    const assess = ['gate', 'short', 'check', 'retention'].includes(a);
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


function play(st, kid, stopAt = null, n = 0) {
  while (st.pending !== null) {
    if (stopAt !== null && n === stopAt) return n;
    const [item, w] = st.pending;
    for (const ev of kid.events(item, w)) st.event(st.seq, ev);
    n += 1;
  }
  return n;
}
const final = (e, sc) => ({ ...persist.stateOf(sc), engine: e.dump(), records: sc.records });

// جلسة واحدة. تعيد [هل عُقدت، عدد ما أُجيب، الطبقة]
function one(e, sc, kid, cap, stopAt = null, n = 0) {
  const st = new Stepper(e, sc);
  st.open(sc.g_session(cap));
  n = play(st, kid, stopAt, n);
  return [st.finished ? st.result : null, n, st];
}

function scase(name, wrong, help, label) {
  const c = SCEN[name];
  const b0 = build(name);
  const s0 = new Stepper(b0.e, b0.sc);
  s0.open(b0.sc.g_run(c.sessions));
  const total = play(s0, new Kid(wrong, help));
  const base = dump(final(b0.e, b0.sc));
  const bad = [];

  // أ) في الذاكرة: جلسة بعد جلسة حتى false
  let { e, sc } = build(name);
  let kid = new Kid(wrong, help), held = 0, r;
  for (;;) {
    [r] = one(e, sc, kid, c.sessions);
    if (r !== true) break;
    held += 1;
    if (sc.cur !== null) bad.push(`الجلسة ${sc.cur} بقيت مفتوحة بعد انتهاء مولّدها`);
  }
  if (r !== false) bad.push(`النداء الأخير أعاد ${r} لا false`);
  if (held !== b0.sc.sessions) bad.push(`عُقدت ${held} جلسة، وفي g_run ${b0.sc.sessions}`);
  if (dump(final(e, sc)) !== base) bad.push('أ) الحالة النهائية تخالف g_run');
  const before = dump(final(e, sc));
  const [r2, n2] = one(e, sc, kid, c.sessions);
  if (r2 !== false || n2 || dump(final(e, sc)) !== before) bad.push('نداء ثانٍ بعد النهاية غيّر شيئًا أو عرض بندًا');

  // ب) إغلاق بين كل جلستين
  ({ e, sc } = build(name));
  kid = new Kid(wrong, help);
  for (;;) {
    const [rr, , st] = one(e, sc, kid, c.sessions);
    if (rr !== true) break;
    ({ e, sc } = reopen(name, st.snapshot()));
  }
  if (dump(final(e, sc)) !== base) bad.push('ب) مع إغلاق بين الجلسات: الحالة النهائية تخالف g_run');

  // ج) إغلاق عند كل طلب بند في المسار كله، ثم g_session تكمل الجلسة نفسها
  const diff = [];
  for (let k0 = 0; k0 < total; k0++) {
    ({ e, sc } = build(name));
    kid = new Kid(wrong, help);
    let n = 0, k = k0;
    for (;;) {
      const [rr, nn, st] = one(e, sc, kid, c.sessions, k, n);
      n = nn;
      if (st.pending !== null) {
        const cur = sc.cur;
        ({ e, sc } = reopen(name, st.snapshot()));
        if (sc.cur !== cur) diff.push([k0, `الجلسة بعد الاستعادة ${sc.cur} وكانت ${cur}`]);
        k = null;
        continue;
      }
      if (rr !== true) break;
    }
    if (dump(final(e, sc)) !== base) diff.push([k0, 'الحالة النهائية']);
  }
  if (diff.length) bad.push(`ج) ${diff.length} من ${total} موضع إغلاق تخالف. أولها: ${JSON.stringify(diff.slice(0, 3))}`);
  check(`${label}: ${b0.sc.sessions} جلسة و${total} طلب بند`, bad);
}

console.log('=== جلسة واحدة للواجهة (g_session)، التطبيق');
for (const [name, wrong, help, label] of [
  ['young', [], [], 'الصغير في 1-4'],
  ['young', ['1-4-1/evidence/01', '1-4-1/checkA/03', '1-4-1/checkA/05'], ['1-4-2/evidence/01'], 'الصغير، بأخطاء وطلب تلميح'],
  ['older', [], [], 'الكبيران في 3-5'],
  ['older', ['3-5-1/checkA/01', '3-5-1/checkA/03', '3-5-2/evidence/01'], [], 'الكبيران، بأخطاء'],
  ['retention', [], [], 'الصغير في 1-4-1 مع فحوص الاحتفاظ']]) scase(name, wrong, help, label);
const okAll = results.every(Boolean);
console.log(okAll ? `نجحت الاختبارات كلها: ${results.length}` : `أخفق ${results.filter((x) => !x).length} من ${results.length}`);
process.exit(okAll ? 0 : 1);
