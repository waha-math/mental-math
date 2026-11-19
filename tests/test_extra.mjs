// الجلسة الإضافية: الطفل الذي يريد أن يستمر بعد جلسة يومه (قرار الأب، 19 نوفمبر 2026). القاعدة والتوقعات في
// tests/test_extra.py، والمسارات نفسها تُطابَق بشريط المرجع tests/extra_tape.json: ما عُرض والحالة الدائمة كاملة.
//
//     node tests/test_extra.mjs [مجلد app]
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

const TEACHING = ['opening', 'lesson', 'evidence', 'practice'];
const PRACTICE = (s) => ITEMS.filter((i) => i.skill === s && i.role === 'practice').map((i) => i.id);
const TAPE = JSON.parse(readFileSync(new URL('./extra_tape.json', import.meta.url), 'utf8'));
// الشريحة (10.2). السقف وحد اليوم بقرار الأب: 6 دقائق و30 دقيقة للصغير، و10 و50 للكبيرين. ثواني البند قيمة اختبار
const SCEN = {
  young: { group: 'young', scope: ['1-4-1', '1-4-2'], decisions: [['1-4-1', ['1-3-3']]], cap: 360, day_cap: 1800, secs: 30 },
  older: { group: 'older', scope: ['3-5-1', '3-5-2', '3-5-3'],
    decisions: [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]], cap: 600, day_cap: 3000, secs: 45 },
};
const final = (e, sc) => ({ ...persist.stateOf(sc), engine: e.dump(), records: sc.records });
const src = () => { const s = new ContentSource(ITEMS); return (k, w) => s.pick(k, w); };
const eq = (a, b) => dump(a) === dump(b);

// طفل يتعلّم يمضي يومًا بعد يوم. extra: هل يطلب الاستمرار كلما عُرض عليه؟
class Run {
  constructor(name, extra = true, over = {}) {
    const c = { ...SCEN[name], ...over };
    Object.assign(this, { c, extra, kid: new Kid(), trace: [], n: 0, shown: false, notes: [] });
    this.e = new Engine(undefined, { group: c.group });
    c.decisions.forEach(([skill, bypass], k) => this.e.apply({ id: 'd' + k, type: 'teacher_open', skill, bypass,
      reason: 'قرار الشريحة في 10.2' }));
    this.sc = new Scheduler(this.e, TYPES, src(), null, { group: c.group, scope: new Set(c.scope), learning: true,
      cap: c.cap, item_seconds: () => c.secs, records: [], retention: true, day_cap: c.day_cap });
  }

  reopen(rec, today) {
    const r = persist.restore(JSON.parse(JSON.stringify(rec)), { types: TYPES, source: src(), answer: null,
      item_seconds: () => this.c.secs, records: [], today });
    this.e = r.engine;
    this.sc = r.scheduler;
    return r.notes;
  }

  // جلسة واحدة. stop: رقم طلب البند (في المسار كله) الذي يُغلق التطبيق عنده. تعيد اللقطة عند الإغلاق، أو null
  session(gen, day, stop = null) {
    this.sc.today = day;
    const st = new Stepper(this.e, this.sc);
    st.open(this.sc[gen]());
    while (st.pending !== null) {
      const [item, w] = st.pending;
      if (stop !== null && this.n === stop) {
        if (this.shown) st.show(st.seq);
        return st.snapshot();
      }
      const ses = this.sc.cur;                     // تُلتقط قبل الإجابة: الطبقة قد تختم الجلسة بعدها
      this.trace.push([ses, this.e.s.sessions[ses].kind, day, item.id, w.activity]);
      this.n += 1;
      for (const ev of this.kid.events(item, w)) st.event(st.seq, ev);
    }
    this.last = st;
    return null;
  }

  day(d, stop = null, reopenDay = null) {
    const gens = ['g_session', ...(this.extra ? Array(20).fill('g_extra') : [])];
    for (const gen of gens) {
      if (gen === 'g_extra' && !this.sc.can_extra(d)) break;
      let rec = this.session(gen, d, stop);
      while (rec !== null) {                       // أُغلق التطبيق: يُستعاد ثم تُكمَل الجلسة الجارية
        stop = null;
        const back = reopenDay === null ? d : reopenDay;
        this.notes = this.reopen(rec, back);
        if (back !== d) return;
        rec = this.sc.cur !== null ? this.session('g_session', d) : null;
      }
    }
  }

  days(first, last) {
    for (let d = first; d <= last; d++) this.day(d);
    return this;
  }

  of({ kind = null, day = null } = {}) {
    return this.trace.filter((t) => (kind === null || t[1] === kind) && (day === null || t[2] === day));
  }

  firstDay(skill, activity) {
    const t = this.trace.find((x) => x[3].startsWith(skill + '/') && x[4] === activity);
    return t ? t[2] : null;
  }

  tape() {
    return { trace: this.trace, final: final(this.e, this.sc) };
  }
}
const ids = (ts) => ts.map((t) => t[3]);
const same = (name, run) => (eq(TAPE[name], run.tape()) ? [] : [`${name}: المسار أو الحالة النهائية تخالف شريط المرجع`]);

console.log('=== الجلسة الإضافية، التطبيق (القاعدة والتوقعات في tests/test_extra.py)');

// 1) الصغير: الدرس الذي قطعه السقف يُكمَل في يومه
const a = new Run('young').days(0, 12), b = new Run('young', false).days(0, 12);
let bad = [...same('young', a), ...same('young_control', b)];
const x1 = a.of({ kind: 'extra', day: 1 });
const cut = b.of({ day: 1 }).length;
const rest = ids(b.of({ day: 2 }).filter((t) => TEACHING.includes(t[4])));
if (!eq(a.of({ day: 0 }), b.of({ day: 0 })) || !eq(a.of({ kind: 'start' }), b.of({ kind: 'start' }))) bad.push('الجلسات العادية قبل أول إضافية تخالف');
if (cut * 30 < 360 || (cut - 1) * 30 >= 360) bad.push(`السقف لم يقطع جلسة البدء حيث يجب: ${cut}`);
if (!x1.length || new Set(x1.map((t) => t[0])).size !== 1) bad.push('اليوم 1: المتوقع جلسة إضافية واحدة');
if (!rest.length || !eq(ids(x1).slice(0, rest.length), rest)) bad.push('الإضافية لم تبدأ ببنود الدرس الباقية نفسها');
if (!eq(ids(x1).slice(rest.length), PRACTICE('1-4-1'))) bad.push('بعد اكتمال الدرس: المتوقع تدريب المهارة مرة واحدة');
if (a.of({ kind: 'extra' }).some((t) => !TEACHING.includes(t[4]))) bad.push('في الإضافيات نشاط غير تعليمي');
if (!eq([a.firstDay('1-4-1', 'check'), b.firstDay('1-4-1', 'check')], [2, 3])) bad.push('يوم فحص استقلال 1-4-1');
if (a.e.derive()['1-4-1'] !== 'met' || a.e.derive()['1-4-2'] !== 'met' || !eq(a.e.derive(), b.e.derive())) bad.push('حالة المهارتين في النهاية');
check('الصغير: السقف يقطع درس 1-4-1، والإضافية في اليوم نفسه تكمله بالبنود التي كانت ستُعرض غدًا، ثم تدريب المهارة مرة. لا نشاط '
  + 'تقييم فيها. وفحص الاستقلال يتقدم يومًا، والمهارتان مستوفاتان في المسارين. ويطابق شريط المرجع', bad);

// 2) لا إضافية حيث لا تجوز
bad = [];
let r = new Run('young');
r.day(0);
if (r.sc.can_extra(0)) bad.push('بعد جلسة البحث (قبل جلسة البدء) عُرضت إضافية');
r.sc.today = 0;
const st0 = new Stepper(r.e, r.sc), before = dump(final(r.e, r.sc));
st0.open(r.sc.g_extra());
if (st0.result !== false || st0.pending !== null || dump(final(r.e, r.sc)) !== before) bad.push('g_extra حيث لا تجوز غيّرت شيئًا أو عرضت بندًا');
r.session('g_session', 1);
if (!r.sc.can_extra(1) || r.sc.can_extra(2)) bad.push('بعد جلسة اليوم 1: المتوقع إضافية متاحة لليوم 1 لا لليوم 2');
if (!eq(r.sc.extra_plan(1), [['resume', '1-4-1']])) bad.push('خطة الإضافية: ' + dump(r.sc.extra_plan(1)));
const n0 = new Run('young', true, { day_cap: null });
n0.day(0);
n0.session('g_session', 1);
if (n0.sc.can_extra(1) || n0.sc.used !== null) bad.push('بلا حد لليوم عُرضت إضافية أو حُفظ زمن اليوم');
if (a.trace.some((t) => t[1] === 'extra' && t[2] >= 5)) bad.push('إضافية بعد استيفاء المهارتين');
check('لا إضافية قبل جلسة البدء، ولا في يوم بلا جلسة، ولا بلا حد لليوم، ولا بعد استيفاء المهارتين. و g_extra حيث لا تجوز لا '
  + 'تغيّر شيئًا', bad);

// 3) المستوفاة لا تُدرَّب، والاحتفاظ يبقى «احتفاظ»
bad = [];
for (const [run, name] of [[a, 'بالإضافية'], [b, 'بدونها']]) {
  const got = run.e.s.retention.map((x) => [x.skill, x.round, x.label, run.e.s.sessions[x.session].kind]);
  const want = [['1-4-1', 1, 'retention', 'follow'], ['1-4-2', 1, 'retention', 'follow']].slice(0, got.length);
  if (!got.length || !eq(got, want)) bad.push(`${name}: جولات الاحتفاظ ${dump(got)}`);
}
if (a.e.s.retention.length !== 2) bad.push(`بالإضافية: المتوقع جولتان حتى اليوم 12، والناتج ${a.e.s.retention.length}`);
check('جولات الاحتفاظ في جلسات عادية في المسارين، ووصف نتائجها «احتفاظ» (لم تُدرَّب مهارة مستوفاة في إضافية)', bad);

// 4) حد اليوم يقطع الدرس: يُحفظ لجلسة الغد
const c = new Run('young', true, { day_cap: cut * 30 + 30 }).days(0, 3);
bad = same('young_daycap_lesson', c);
if (!eq(ids(c.of({ kind: 'extra', day: 1 })), rest.slice(0, 1))) bad.push('المتوقع بند واحد في الإضافية');
if (!eq(ids(c.of({ day: 2 }).filter((t) => TEACHING.includes(t[4]))).slice(0, rest.length - 1), rest.slice(1))) bad.push('جلسة الغد لم تكمل الدرس من موضعه');
check('حد اليوم يتسع لبند واحد: الإضافية تعرضه ثم تُختم، ولا إضافية ثانية، والدرس محفوظ فتكمله جلسة الغد من موضعه', bad);

// 5) حد اليوم يقطع التدريب الحر: لا يُحفظ
const dcap = (cut + rest.length + 2) * 30;
const d = new Run('young', true, { day_cap: dcap }).days(0, 2);
bad = same('young_daycap_practice', d);
if (!eq(ids(d.of({ kind: 'extra', day: 1 })), [...rest, ...PRACTICE('1-4-1').slice(0, 2)])) bad.push('الإضافية: المتوقع باقي الدرس وبندا تدريب');
const rec1 = new Run('young', true, { day_cap: dcap }).days(0, 1);
if (rec1.sc.saved.some((s) => s.kind === 'show') || !eq((rec1.sc.free || {}).skills, ['1-4-1'])) bad.push('بعد القطع: المحفوظ أو ما دُرّب');
if ((d.of({ day: 2 })[0] || [])[4] !== 'check') bad.push('جلسة الغد: المتوقع أن تبدأ بفحص الاستقلال');
check('حد اليوم يقطع التدريب الحر بعد بندين: لا يُحفظ، فلا يأخذ حصة الغد، وجلسة الغد تبدأ بفحص الاستقلال', bad);

// 6) الإغلاق داخل الإضافية
const ref = new Run('young').days(0, 4);
const base = dump(final(ref.e, ref.sc)), total = ref.n;
let diff = [];
for (let k = 0; k < total; k++) {                 // الإغلاق قبل عرض البند: لا أثر له
  r = new Run('young');
  for (let dd = 0; dd < 5; dd++) r.day(dd, k);
  if (dump(final(r.e, r.sc)) !== base || !eq(r.trace, ref.trace)) diff.push(k);
}
const ex = ref.trace.map((t, i) => (t[1] === 'extra' ? i : -1)).filter((i) => i >= 0);
bad = diff.length ? [`${diff.length} من ${total} موضع إغلاق تخالف المسار المتصل. أولها ${diff.slice(0, 5)}`] : [];
if (!ex.length) bad.push('لا بند إضافية في المسار المرجعي');
check(`الإغلاق قبل عرض البند، عند كل طلب في الأيام 0 إلى 4 (${total} موضعًا، منها ${ex.length} في إضافيات)، ثم العودة في اليوم نفسه: `
  + 'الحالة الدائمة كاملة وما عُرض كما في المسار المتصل', bad);

diff = [];
const ses = (e) => e.s.order.map((x) => [x, e.s.sessions[x].kind, e.s.sessions[x].day, e.s.sessions[x].ended]);
for (const k of ex) {                             // الإغلاق والبند معروض لم يُجب
  r = new Run('young');
  r.shown = true;
  for (let dd = 0; dd < 5; dd++) r.day(dd, k);
  const ok = eq(r.e.derive(), ref.e.derive()) && eq(ses(r.e), ses(ref.e)) && eq(r.sc.used, ref.sc.used) && eq(r.sc.free, ref.sc.free);
  if (!eq(r.trace, ref.trace) || !ok) diff.push([k, ref.trace[k][3]]);
}
check(`الإغلاق والبند معروض، عند كل بند في الإضافيات (${ex.length}): تُكمَل الإضافية نفسها بالبند نفسه، وما عُرض والجلسات وحالة `
  + 'المهارات ووقت اليوم كما في المسار المتصل', diff.length ? [`${diff.length} من ${ex.length}: ${dump(diff.slice(0, 6))}`] : []);

const pk = ref.trace.findIndex((t) => t[1] === 'extra' && t[4] === 'practice') + 2;   // ثالث بنود التدريب الحر
r = new Run('young');
r.shown = true;
r.day(0);
r.day(1, pk, 2);
bad = [];
const has = (n) => r.notes.some((x) => eq(x, n));
if (!has(['session_closed', 'S3']) || !has(['free_practice_dropped', '1-4-1'])) bad.push('ملاحظات الاستعادة: ' + dump(r.notes));
if (r.sc.saved.some((s) => s.kind === 'show') || r.sc.cur !== null) bad.push('بعد الاستعادة في يوم جديد: المحفوظ أو الجلسة');
r.day(2);
if ((r.of({ day: 2 })[0] || [])[4] !== 'check') bad.push('جلسة اليوم التالي: المتوقع أن تبدأ بفحص الاستقلال');
bad.push(...same('young_closed_overnight', r));
check('الإغلاق في التدريب الحر والعودة في اليوم التالي: الإضافية تُختم، والتدريب لا يُحفظ، وجلسة اليوم تبدأ بفحص الاستقلال', bad);

// 7) الكبيران: درس جديد في الإضافية، وواحد في اليوم
const o = new Run('older').days(0, 13), oc = new Run('older', false).days(0, 13);
bad = [...same('older', o), ...same('older_control', oc)];
for (const [run, name] of [[o, 'بالإضافية'], [oc, 'بدونها']]) {
  const per = {};
  for (const op of Object.values(run.e.s.opened)) per[run.e.s.sessions[op.session].day] = (per[run.e.s.sessions[op.session].day] || 0) + 1;
  if (Object.values(per).some((v) => v > 1)) bad.push(`${name}: أكثر من درس جديد في يوم`);
}
const fresh = Object.entries(o.e.s.opened).filter(([, op]) => o.e.s.sessions[op.session].kind === 'extra').map(([s]) => s);
if (!eq(fresh, ['3-5-2'])) bad.push('الدروس التي فُتحت في إضافية: ' + dump(fresh));
if (o.of({ kind: 'extra' }).some((t) => !TEACHING.includes(t[4]))) bad.push('في إضافيات الكبيرين نشاط غير تعليمي');
const cd = (run) => ['3-5-1', '3-5-2', '3-5-3'].map((s) => run.firstDay(s, 'check'));
if (!eq(cd(o), [2, 3, 5]) || !eq(cd(oc), [3, 6, 8])) bad.push(`أيام فحوص الاستقلال: ${cd(o)} و${cd(oc)}`);
if (!eq(o.e.derive(), oc.e.derive())) bad.push('حالة المهارات تختلف في النهاية');
check('الكبيران: بوابة 3-5-2 تخفق في يوم ذهبت حصته لفحص 3-5-1، فيُفتح درسها في إضافية اليوم نفسه. درس جديد واحد في كل يوم '
  + 'أسرة. وفحوص الاستقلال في الأيام 2 و3 و5 بدل 3 و6 و8، والحالة النهائية واحدة. ويطابق شريط المرجع', bad);

const okAll = results.every(Boolean);
console.log(okAll ? `نجحت الاختبارات كلها: ${results.length}` : `أخفق ${results.filter((x) => !x).length} من ${results.length}`);
process.exit(okAll ? 0 : 1);
