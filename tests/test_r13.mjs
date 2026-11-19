// حالة المراجعة الثالثة عشرة على مجدول التطبيق بلغة JavaScript: نشاط محفوظ لا يستبدله نشاط آخر يبلغ السقف.
//
//     node tests/test_r13.mjs [مجلد app]
//
// الحالتان والنتائج المتوقعة نفسها في tests/test_r13.py و tests/r13_cases.json، مكتوبة يدويًا. المجلد الاختياري
// يشغّلهما على نسخة أخرى من التطبيق (مثلًا الالتزام 8b6f81d).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const here = new URL('.', import.meta.url);
const appDir = resolve(process.argv[2] || new URL('../app', here).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine, OPEN_CHECK, canonical } = await load('engine.mjs');
const { Scheduler, Capped } = await load('scheduler.mjs');
const { ContentSource, GateRun, ShortCheckRun, RetentionRun, OpeningRun, EvidenceRun, CheckRun } = await load('items.mjs');
const C = JSON.parse(readFileSync(new URL('r13_cases.json', here), 'utf8'));
const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', here), 'utf8')).items;
const same = (a, b) => canonical(a) === canonical(b);
const results = [];

// الأنشطة المحفوظة: saved في هذه النسخة، و carry الواحد قبلها
const saved = (sc) => ('saved' in sc ? [...sc.saved] : sc.carry ? [sc.carry] : []);
const brief = (sc) => saved(sc).map((c) => [c.kind, c.skill, c.items.length]);

class Child {
  constructor() { this.known = new Set(); }

  call(item, want) {
    const a = want.activity;
    if (a === 'lesson' || a === 'practice') {
      if (a === 'lesson') this.known.add(item.skill);
      return 'correct';
    }
    const assess = ['gate', 'short', 'check', 'retention', 'describe'].includes(a);
    const ans = this.known.has(item.skill) ? item.answer : item.answer + 1;
    return [[['confirm', ans], ...(assess ? [] : [['end']])], item.answer, assess];
  }
}

function caseA() {
  const S = C.scenario;
  const e = new Engine(undefined, { group: S.group });
  S.decisions.forEach(([skill, bypass], k) => {
    e.apply({ id: `d${k}`, type: 'teacher_open', skill, bypass, reason: 'قرار الشريحة' });
  });
  const src = new ContentSource(ITEMS);
  const timed = [];
  const child = new Child();
  let sc;
  const seconds = (w) => {
    const s = S.seconds[w.activity] || 0;
    if (s) timed.push(sc.cur);
    return s;
  };
  sc = new Scheduler(e, S.types, (s, w) => src.pick(s, w), (i, w) => child.call(i, w), {
    group: S.group, scope: S.scope, learning: true, cap: S.cap, item_seconds: seconds, retention: true });
  sc.search();
  sc.start_session();
  for (let i = 0; i < S.follow_before; i++) sc.follow_learning();
  let X = C.expect_before_absence;
  const ind = e.validEvidence(X.met, 'independent');
  const nxt = e.retentionNext(X.met);
  let got = { day: sc.day, met: e.derive()[X.met], met_day: ind.length ? e.s.sessions[ind[ind.length - 1].session].day : null,
    due: nxt ? nxt[1] : null, check: (e.s.checks[X.check_id] || {}).state ?? null, saved: brief(sc) };
  let want = { day: X.day, met: 'met', met_day: X.met_day, due: X.retention_due_day, check: X.check_state, saved: X.saved };
  if (!same(got, want)) return [`قبل الغياب: ${canonical(got)}، والمتوقع ${canonical(want)}`];
  if (!same(saved(sc)[0].items, C.check_items.slice(0, 4))) return ['قبل الغياب: خانات الاستقلال المحفوظة ليست الأربع الأولى'];
  const kept = structuredClone(saved(sc)[0]);

  sc.day = S.absent_to_day - 1;                   // غياب: الجلسة التالية في يوم الاحتفاظ
  sc.follow_learning();
  const bad = [];
  X = C.expect_absence_session;
  const cur = e.s.order[e.s.order.length - 1];
  got = { day: e.s.sessions[cur].day, saved: brief(sc), teach: e.s.sessions[cur].teach,
    check: e.s.checks[C.expect_before_absence.check_id].state };
  want = { day: X.day, saved: X.saved, teach: X.teach, check: X.check_state };
  if (!same(got, want)) bad.push(`جلسة يوم الاحتفاظ: ${canonical(got)}، والمتوقع ${canonical(want)}`);
  const chk = saved(sc).filter((c) => c.kind === 'check');
  if (!chk.length || !same(chk[0], kept)) bad.push('فحص الاستقلال المحفوظ تغيّر أو اختفى: خاناته وإجاباته ومعرّفاته ليست كما كانت');
  const ret = saved(sc).filter((c) => c.kind === 'retention');
  if (!ret.length || !same(ret[0].items, C.retention_items.slice(0, 4))) bad.push('تقدّم الاحتفاظ لم يُحفظ ببنوده الأربعة');
  if (bad.length) return bad;

  for (let i = 0; i < S.follow_after_max; i++) {
    if (!saved(sc).length && !Object.keys(sc.parked).length && sc.satisfied()) break;
    sc.follow_learning();
  }
  const rr = e.s.retention.filter((x) => x.skill === '1-4-1');
  if (rr.length !== 1 || !same(rr[0].items, C.retention_items) || rr[0].correct !== 5) {
    bad.push('الاحتفاظ لم يكتمل ببنوده الخمسة');
  }
  const cid = C.expect_before_absence.check_id;
  const starts = e.s.log.filter((x) => x.type === 'check_started' && x.skill === '1-4-2');
  const res = e.s.log.filter((x) => x.type === 'independence_result' && x.skill === '1-4-2');
  if (starts.length !== 1 || res.length !== 1 || res[0].check_id !== cid || res[0].result !== 'pass'
    || !same(res[0].items, C.check_items)) {
    bad.push(`الاستقلال لم يكتمل بخاناته العشر في المحاولة الأصلية: بدء ${starts.length}، نتائج ${res.length}`);
  }
  if (Object.values(e.s.checks).some((c) => OPEN_CHECK.includes(c.state)) || saved(sc).length
    || Object.keys(sc.parked).length || sc.refused.length) {
    bad.push('بقيت محاولة معلّقة أو نشاط محفوظ أو اقتراح مرفوض');
  }
  if (src.served.length !== new Set(src.served).size) bad.push('عُرض بند مرتين');
  const per = {};
  for (const s of timed) per[s] = (per[s] || 0) + 1;
  if (Math.max(...Object.values(per)) > C.per_session_max_timed_items) bad.push(`تجاوزت جلسة السقف: ${canonical(per)}`);
  const follow = e.s.order.filter((x) => e.s.sessions[x].kind === 'follow');
  if (Math.max(...follow.map((x) => e.s.sessions[x].teach)) > C.per_session_max_teach) {
    bad.push('جلسة استهلكت أكثر من حصة تعليمية');
  }
  return bad;
}

// ستة أنشطة من ستة أنواع، لستّ مهارات، يقطعها السقف واحدًا بعد آخر في جلسة واحدة
function caseB() {
  const e = new Engine(undefined, { group: 'older' });
  const sc = new Scheduler(e, {}, () => null, () => 'correct', { cap: 1 });
  sc.elapsed = 1;
  const T = ['ف1', 'ف3'];
  const acts = [['gate', new GateRun({ skill: '2-1-1', types: T })], ['short', new ShortCheckRun({ skill: '2-1-2', types: T })],
    ['retention', new RetentionRun({ skill: '2-1-3', round: 1 })], ['opening', new OpeningRun({ skill: '2-2-1', types: T })],
    ['evidence', new EvidenceRun({ skill: '2-2-2', types: T })],
    ['check', new CheckRun({ skill: '2-2-3', check_id: '2-2-3/check/1', content_version: 1 })]];
  for (const [kind, act] of acts) {
    act.shown.x = 1;                              // عُرض منه بند
    try { sc.cut(act, kind, [`${act.skill}/item`]); } catch (err) { if (!(err instanceof Capped)) throw err; }
  }
  const want = acts.map(([k, a]) => [k, a.skill, 1]);
  const bad = same(brief(sc), want) ? [] : [`المحفوظ بعد ستة أنشطة: ${canonical(brief(sc))}، والمتوقع ${canonical(want)}`];
  const again = new GateRun({ skill: '2-1-1', types: T });
  again.shown.x = 1;
  try {
    sc.cut(again, 'gate', []);
    bad.push('حُفظ مفتاح محفوظ من قبل دون خطأ');
  } catch (err) {
    if (err instanceof Capped) bad.push('حفظ مفتاح محفوظ من قبل انتهى بالسقف بلا خطأ صريح');
  }
  if (!same(brief(sc), want)) bad.push(`تغيّر المحفوظ بعد محاولة حفظ المفتاح نفسه: ${canonical(brief(sc))}`);
  return bad;
}

const CASES = [['R13-01-a', true, 'سيناريو المراجع: استقلال 1-4-2 محفوظ بأربع خانات، وغياب حتى يوم احتفاظ 1-4-1، والاحتفاظ '
  + 'يبلغ السقف. يبقى الاستقلال كما هو، ويُحفظ الاحتفاظ ببنوده الأربعة، ثم يكتمل الاحتفاظ بخمسة والاستقلال بعشر في '
  + 'محاولته الأصلية، بلا تكرار ولا محاولة معلّقة، والسقف والحصة محترمان', caseA],
['R13-01-b', false, 'لكل نوع: ستة أنشطة من ستة أنواع يقطعها السقف واحدًا بعد آخر تُحفظ كلها، وحفظ مفتاح محفوظ من '
  + 'قبل خطأ صريح لا يغيّر المحفوظ', caseB]];

console.log(`=== حالة المراجعة الثالثة عشرة، بلغة JavaScript، على التطبيق في ${appDir}`);
for (const [id, rep, title, fn] of CASES) {
  let bad;
  try { bad = fn(); } catch (x) { bad = ['استثناء: ' + x]; }
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${id} ${title}${rep ? ' [أعاد المراجع إنتاجه]' : ''}`);
  for (const b of bad.slice(0, 3)) console.log('        ' + b);
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
