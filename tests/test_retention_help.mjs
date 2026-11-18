// طلب المساعدة في فحص الاحتفاظ على التطبيق (ت3 في مراجعة 04e0168): المشهد نفسه في tests/test_retention_help.py،
// بالحالات الست عشرة نفسها والتوقعات نفسها.
//
//     node tests/test_retention_help.mjs [مجلد app]
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

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const SKILL = '1-4-1';
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

// الطفل النموذجي في test_phase0: يعرف المهارة بعد أن يرى درسها
class Kid {
  constructor() { this.known = new Set(); }

  events(item, w) {
    const a = w.activity;
    if (a === 'lesson' || a === 'practice') {
      if (a === 'lesson') this.known.add(item.skill);
      return [['end']];
    }
    const assess = ['gate', 'short', 'check', 'retention'].includes(a);
    const ans = this.known.has(item.skill) ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1);
    return [['confirm', ans], ...(assess ? [] : [['end']])];
  }
}

let KID = null;
function answer(st, how = 'c') {
  const [item, w] = st.pending;
  const evs = how === 'h' ? [['support', 'requested']] : how === 'w' ? [['confirm', item.answer + 1]] : KID.events(item, w);
  for (const ev of evs) st.event(st.seq, ev);
}

// حتى أول بند في أول فحص احتفاظ، ثم correctFirst إجابات صحيحة فيه. stripAlternates: محتوى بلا بدائل لبنود الاحتفاظ
function toRetention({ stripAlternates = false, correctFirst = 0 } = {}) {
  const e = new Engine(undefined, { group: 'young' });
  e.apply({ id: 'd0', type: 'teacher_open', skill: SKILL, bypass: ['1-3-3'], reason: 'قرار الشريحة في 10.2' });
  const src = new ContentSource(ITEMS);
  const source = (s, w) => (stripAlternates && w.role === 'deferred_check.alternate' ? null : src.pick(s, w));
  const sc = new Scheduler(e, TYPES, source, null, { group: 'young', scope: [SKILL], learning: true, cap: 240,
    item_seconds: secs, records: [], retention: true });
  KID = new Kid();
  const st = new Stepper(e, sc);
  st.open(sc.g_run(100));
  while (st.pending[1].activity !== 'retention') answer(st);
  for (let i = 0; i < correctFirst; i++) answer(st);
  return { e, sc, st };
}

// ما يُعرض حتى تُختم الجلسة ses: [النشاط، المعرّف]. الجلسة تُعطى صريحة: طبقة الخطوات تفتح التالية عند ختم آخر بند
function restOfSession(e, st, ses, limit = 60) {
  const out = [];
  while (st.pending !== null && e.s.current === ses && out.length < limit) {
    out.push([st.pending[1].activity, st.pending[0].id]);
    answer(st);
  }
  return out;
}
const sessions = (e, st, n) => Array.from({ length: n }, () => restOfSession(e, st, e.s.current));
const kinds = (shown) => shown.map(([a]) => a).filter((a, i, l) => i === 0 || l[i - 1] !== a);
const of = (shown, a) => shown.filter(([x]) => x === a).map(([, i]) => i);
const facts = (e, ses = null) => ({
  results: e.s.retention.filter((r) => ses === null || r.session === ses).map((r) => [r.round, r.correct, r.label]),
  notes: e.s.retention_notes.filter((n) => n.valid && (ses === null || n.session === ses)).map((n) => [n.round, n.what]),
});
const dayOf = (e, what) => e.s.retention_notes.filter((n) => n.what === what).map((n) => n.day);
const tags = (sc, p) => sc.log.map((x) => x[1]).filter((x) => String(x).startsWith(p));
const code = (v) => v.code ?? null;

console.log('=== طلب المساعدة في فحص الاحتفاظ، بلغة JavaScript');
// 1) حالة المراجع: طلب مساعدة في البند الأول
let { e, sc, st } = toRetention();
const first = st.pending[0].id;
let ses = e.s.current;
const teachBefore = e.s.sessions[ses].teach;
answer(st, 'h');
const after = restOfSession(e, st, ses);
expect('1. طلب المساعدة في البند الأول ينهي الجولة: لا نتيجة احتفاظ، والطلب محفوظ بجولته وبنده، وما بقي من بنود الجولة لا يُعرض',
  [facts(e, ses).results, facts(e, ses).notes[0], e.s.retention_notes.filter((n) => n.what === 'help').map((n) => n.items),
    of(after, 'retention'), tags(sc, 'retention_')[0]],
  [[], [1, 'help'], [[first]], [], 'retention_help']);
const practice = of(after, 'practice');
expect('2. ثم التثبيت في الجلسة نفسها وقبل أي شيء آخر: أول أربعة بنود من تدريب المهارة، بحدثي بدء واكتمال في المحرك، وحصة الجلسة مستهلكة به، '
  + 'والمهارة باقية مستوفاة ودرسها لم يُستأنف',
  [kinds(after).slice(0, 1), practice.length, practice.every((i) => i.startsWith(SKILL + '/practice/')),
    facts(e, ses).notes, text(e.s.retention_notes.filter((n) => n.what === 'consolidated').map((n) => n.items)) === text([practice]),
    e.s.sessions[ses].teach - teachBefore, e.direct(SKILL), e.s.opened[SKILL].taught.includes(ses), tags(sc, 'carry_')],
  [['practice'], 4, true, [[1, 'help'], [1, 'consolidating'], [1, 'consolidated']], true, 1, 'met', false, []]);
const rec = sc.records.filter((r) => r.item === first).pop();
expect('3. سجل البند يحفظ الطلب: منقطع، بلا إجابة، ونوع الدعم requested',
  [rec.status, rec.values, rec.support], ['interrupted', [], ['requested']]);

// 2) بعد إجابتين صحيحتين: لا 2 من 5
({ e, sc, st } = toRetention({ correctFirst: 2 }));
ses = e.s.current;
answer(st, 'h');
restOfSession(e, st, ses);
expect('4. طلب المساعدة في البند الثالث بعد إجابتين صحيحتين: لا نتيجة (ليست 2 من 5)',
  [facts(e, ses).results, facts(e, ses).notes[0]], [[], [1, 'help']]);

// 3) الجولة اللاحقة: في يوم لاحق. محتوى بلا بدائل: إحالة إلى البالغ، ولا حلقة
({ e, sc, st } = toRetention({ stripAlternates: true }));
ses = e.s.current;
answer(st, 'h');
const sameDay = restOfSession(e, st, ses);
const later = sessions(e, st, 4);
expect('5. الجولة لا تُعاد في يوم الطلب، وتُطلب في اليوم التالي. وبلا بدائل في المحتوى: تُحال إلى البالغ بلا نتيجة ولا إخفاق، '
  + 'ولا يُعرض بند احتفاظ في أربع جلسات بعدها',
  [of(sameDay, 'retention'), dayOf(e, 'referred')[0] - dayOf(e, 'help')[0], facts(e),
    later.flatMap((x) => of(x, 'retention')), e.retentionNext(SKILL), tags(sc, 'retention_')],
  [[], 1, { results: [], notes: [[1, 'help'], [1, 'consolidating'], [1, 'consolidated'], [1, 'referred']] }, [], null,
    ['retention_help', 'retention_no_alternate']]);
// بعد الإحالة لا شيء ينتظر الطفل، فالتشغيل الأول انتهى: قرار البالغ يقع بين فتحين للتطبيق، ويُتابَع بتشغيل جديد
const ended = st.pending === null;
const r = e.apply({ id: 'adult-1', type: 'retention_release', skill: SKILL, reason: 'يعيدها البالغ ببنودها' });
const rAgain = e.apply({ id: 'adult-2', type: 'retention_release', skill: SKILL, reason: 'مرة ثانية' });
st = new Stepper(e, sc);
st.open(sc.g_run(100));
const redo = sessions(e, st, 1)[0];
expect('5ب. بعد الإحالة ينتهي التشغيل بلا بند منتظر. وقرار البالغ يعيد الجولة ببنودها الأصلية، ونتيجتها «أداء مؤجل». وقرار ثانٍ '
  + 'بلا إحالة يُرفض',
  [ended, r.ok, code(rAgain), of(redo, 'retention').slice(0, 1), facts(e).results],
  [true, true, 'not_referred', [first], [[1, 5, 'deferred_performance']]]);

// 4) ببدائل متاحة (محتوى الشريحة)
({ e, sc, st } = toRetention());
ses = e.s.current;
answer(st, 'h');
restOfSession(e, st, ses);
const nxt = sessions(e, st, 1)[0];
const shown = of(nxt, 'retention');
const idsOf = (role) => ITEMS.filter((i) => i.skill === SKILL && i.group === 'deferred' && i.role === role).map((i) => i.id);
const original = idsOf('deferred_check'), alternate = idsOf('deferred_check.alternate');
expect('6. ببدائل متاحة: في اليوم التالي تُعرض الجولة أول الجلسة ببنود بديلة خمسة ليس فيها بند من بنود الجولة الأصلية، '
  + 'ونتيجتها «أداء مؤجل»',
  [kinds(nxt).slice(0, 1), shown.length, shown.every((i) => alternate.includes(i)), shown.filter((i) => original.includes(i)),
    facts(e).results, dayOf(e, 'help')[0] + 1 === e.s.retention[0].day],
  [['retention'], 5, true, [], [[1, 5, 'deferred_performance']], true]);

// 5) الإغلاق والاستعادة بعد الطلب مباشرة
function reopen(st0) {
  const src = new ContentSource(ITEMS);
  const back = persist.restore(JSON.parse(JSON.stringify(st0.snapshot())), { types: TYPES, source: (s, w) => src.pick(s, w),
    answer: null, item_seconds: secs, records: [] });
  const st2 = new Stepper(back.engine, back.scheduler);
  st2.open(back.scheduler.g_run(100));
  return { e: back.engine, sc: back.scheduler, st: st2 };
}

({ e, sc, st } = toRetention());
ses = e.s.current;
answer(st, 'h');
let b = reopen(st);
const after2 = restOfSession(b.e, b.st, ses);
expect('7. إغلاق بعد الطلب مباشرة ثم استعادة: الجولة المنتهية لا تعود ولا تصدر عنها نتيجة، وما يُعرض بعدها ما يُعرض في المتصل، '
  + 'والتثبيت يكتمل مرة واحدة',
  [facts(b.e, ses), of(after2, 'retention'), text(after2) === text(after), b.sc.saved.filter((k) => k.kind === 'retention')],
  [{ results: [], notes: [[1, 'help'], [1, 'consolidating'], [1, 'consolidated']] }, [], true, []]);

// 5ب) الإغلاق في أثناء التثبيت، بعد بندين منه
({ e, sc, st } = toRetention());
ses = e.s.current;
answer(st, 'h');
const seen2 = [st.pending[0].id];
answer(st);
seen2.push(st.pending[0].id);
answer(st);
b = reopen(st);
const rest2 = restOfSession(b.e, b.st, ses);
expect('7ب. إغلاق بعد بندين من التثبيت ثم استعادة: يُكمَل من بنده الثالث في الجلسة نفسها بلا حدث بدء ثانٍ ولا حصة ثانية، ثم يكتمل',
  [text(of(rest2, 'practice')) === text(practice.slice(2)), text(seen2) === text(practice.slice(0, 2)), facts(b.e, ses).notes,
    b.e.s.sessions[ses].teach - teachBefore],
  [true, true, [[1, 'help'], [1, 'consolidating'], [1, 'consolidated']], 1]);

// 6) إبطال جلسة الطلب والتثبيت
({ e, sc, st } = toRetention());
ses = e.s.current;
answer(st, 'h');
restOfSession(e, st, ses);
e.apply({ id: 'inv', type: 'invalidate_session', target: ses });
expect('8. إبطال جلسة الطلب: الطلب والتثبيت يبقيان في السجل غير صالحين، ومحاولة الجولة تعود 1 ببنودها الأصلية، ولا تثبيت مستحق',
  [e.s.sessions[ses].invalid, e.s.retention_notes.map((n) => [n.what, n.valid]), e.retentionAttempt(SKILL),
    e.consolidationOwed(), e.retentionNext(SKILL) !== null],
  [true, [['help', false], ['consolidating', false], ['consolidated', false]], 1, [], true]);

// 7) المحرك وحده: التثبيت لا يُقبل بلا طلب، والجولة لا تُقبل قبله
({ e, sc, st } = toRetention());
ses = e.s.current;
const ask = (type, session, more = {}) => code(e.preflight({ id: 'x', type, session, skill: SKILL, ...more }));
const noHelp = ask('consolidation_started', ses);
answer(st, 'h');                                  // بعدها بدأ التثبيت في الجلسة نفسها
const during = [ask('retention_result', ses, { correct: 5 }), ask('consolidation_started', ses),
  code(e.may_continue('show', ses, SKILL)), e.may_continue('consolidate', ses, SKILL).ok];
restOfSession(e, st, ses);
const nxtSes = e.s.current;                       // الجلسة التالية مفتوحة: السؤال فيها، فجلسة التثبيت خُتمت
const done = [ask('consolidation_done', nxtSes), ask('consolidation_started', nxtSes),
  code(e.may_continue('consolidate', nxtSes, SKILL))];
expect('9. في المحرك: لا تثبيت بلا طلب مساعدة. وفي أثنائه لا تُقبل نتيجة الجولة ولا بدء ثانٍ (الحصة مستهلكة)، وعرض الدرس '
  + 'مرفوض وعرض التثبيت مقبول. وبعد اكتماله لا اكتمال ثانٍ ولا بدء ولا عرض',
  [noHelp, during, done],
  ['no_consolidation', ['consolidation_first', 'quota_teach', 'lesson_idle', true],
    ['no_consolidation', 'no_consolidation', 'no_consolidation']]);
// 8) السقف في أثناء التثبيت (الحساب في نسخة بايثون): يحلّ وقد عُرضت البنود كلها، ثم يحلّ وقد بقي بند
({ e, sc, st } = toRetention({ correctFirst: 3 }));
ses = e.s.current;
sc.cap = 200;
answer(st, 'h');
const shown10 = restOfSession(e, st, ses);
const nxt10 = e.s.current;
const after10 = sessions(e, st, 1)[0];
expect('10. السقف يحلّ وقد عُرضت بنود التثبيت كلها: يكتمل في جلسته ولا يُحفظ، ولا يأخذ حصة الجلسة التالية، والجولة البديلة أول '
  + 'الجلسة التالية مباشرة (قبل الإصلاح مضت جلسة كاملة بلا بند)',
  [text(of(shown10, 'practice')) === text(practice), facts(e, ses).notes, sc.saved.filter((c) => c.consolidate),
    facts(e, nxt10).notes, kinds(after10).slice(0, 1), Number(nxt10.slice(1)) - Number(ses.slice(1))],
  [true, [[1, 'help'], [1, 'consolidating'], [1, 'consolidated']], [], [], ['retention'], 1]);
({ e, sc, st } = toRetention({ correctFirst: 3 }));
ses = e.s.current;
sc.cap = 175;
answer(st, 'h');
const shown11 = restOfSession(e, st, ses);
const saved11 = sc.log.filter((x) => x[0] === Number(ses.slice(1)) && x[1] === 'capped');   // سجل المجدول: المحفوظ استؤنف
const nxt11 = e.s.current;
const after11 = sessions(e, st, 1)[0];
expect('11. السقف يحلّ بعد ثلاثة بنود من التثبيت: يُحفظ عند بنده الرابع، ويُستأنف في الجلسة التالية بحدث بدء يأخذ حصتها، فيُعرض '
  + 'الرابع وحده ويكتمل. والجولة لا تُطلب في تلك الجلسة',
  [text(of(shown11, 'practice')) === text(practice.slice(0, 3)), saved11, facts(e, ses).notes,
    text(of(after11, 'practice')) === text(practice.slice(3)), facts(e, nxt11).notes, of(after11, 'retention'),
    e.s.sessions[nxt11].teach],
  [true, [[Number(ses.slice(1)), 'capped', SKILL]], [[1, 'help'], [1, 'consolidating']], true,
    [[1, 'consolidating'], [1, 'consolidated']], [], 1]);
// 9) نتيجة منخفضة تستحق تثبيتًا (القاعدة والتوقعات في نسخة بايثون)
{
  const toRound = (st0, rnd) => {
    while (st0.pending !== null && !(st0.pending[1].activity === 'retention' && st0.pending[1].round === rnd)) answer(st0);
  };
  ({ e, sc, st } = toRetention());
  ses = e.s.current;
  const day1 = e.s.sessions[ses].day;
  const teachLow = e.s.sessions[ses].teach;
  answer(st, 'w');
  answer(st, 'w');
  const low = restOfSession(e, st, ses);
  const nx = e.retentionNext(SKILL);
  expect('12. خطآن في الجولة الأولى: تكتمل بنودها الخمسة ونتيجتها 3 من 5 محفوظة. ثم التثبيت في الجلسة نفسها بحصتها، مسجَّلًا على '
    + 'الجولة الأولى. والجولة الثانية بموعدها بعد 21 يومًا من يوم الفحص، لا تتوقف عليه',
  [kinds(low), of(low, 'retention').length, text(of(low, 'practice')) === text(practice), facts(e, ses),
    e.s.sessions[ses].teach - teachLow, nx[0] === 2 && nx[1] === day1 + 21, e.consolidationOwed()],
  [['retention', 'practice'], 3, true,
    { results: [[1, 3, 'retention']], notes: [[1, 'consolidating'], [1, 'consolidated']] }, 1, true, []]);
  toRound(st, 2);
  const ses2 = e.s.current;
  const second = restOfSession(e, st, ses2);
  const round2 = ITEMS.filter((i) => i.skill === SKILL && i.role === 'deferred_check' && i.slot === 2).map((i) => i.id);
  expect('13. الجولة الثانية في موعدها ببنودها الأصلية، ونتيجتها «أداء مؤجل» لأن تثبيتًا وقع في الفاصل. ولا تثبيت بعدها',
    [e.s.sessions[ses2].day - day1, text(of(second, 'retention')) === text(round2), facts(e, ses2), of(second, 'practice')],
    [21, true, { results: [[2, 5, 'deferred_performance']], notes: [] }, []]);
  toRound(st, 3);
  const ses3 = e.s.current;
  answer(st, 'w');
  answer(st, 'w');
  answer(st, 'w');
  const third = restOfSession(e, st, ses3);
  expect('14. ثلاثة أخطاء في الجولة الثالثة: 2 من 5، ولا جولة بعدها، والتثبيت يُعرض مع ذلك في جلستها. ثم ينتهي المسار',
    [facts(e, ses3), text(of(third, 'practice')) === text(practice), e.retentionNext(SKILL), e.retentionPending(),
      st.pending === null],
    [{ results: [[3, 2, 'retention']], notes: [[3, 'consolidating'], [3, 'consolidated']] }, true, null, [], true]);
}

console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
