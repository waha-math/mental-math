// مطابقة محرك التطبيق بالمحرك المرجعي: node app/test_conformance.mjs
//
// يقرأ conformance_vectors.json (يولّده export_conformance.py من اختبارات المرجع)، ويعيد على محرك التطبيق كل
// حدث أُرسل إلى المرجع وكل سؤال قبل العرض، ويقارن بعد كل واحد: حكم المحرك كاملًا (القبول، رمز الرفض، سببه،
// المتطلب الناقص، الحقل، ما تغيّر من حالات)، وبصمة الحالة المحفوظة كلها مع الحالات المشتقة.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { Engine, canonical, checkEngine } from './engine.mjs';
import { DATA } from './engine_data.mjs';

const dir = new URL('.', import.meta.url);
const { nets, traces } = JSON.parse(readFileSync(new URL('conformance_vectors.json', dir), 'utf8'));
const digest = (e) => createHash('sha256').update(canonical({ s: e.s, d: e.derive() }), 'utf8').digest('hex');
const same = (a, b) => canonical(a) === canonical(b);
const results = [];
function check(name, cond) {
  results.push(Boolean(cond));
  console.log(`  ${cond ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
}

console.log('=== مطابقة محرك التطبيق بالمحرك المرجعي');
check(`لكل حدث في المخطط دالتا فحص وتنفيذ، ولا دالة لحدث خارجه: ${checkEngine()} حدثًا`, true);
check('الشبكة في بيانات المحرك هي شبكة المتجهات', same([DATA.network.ids, DATA.network.pre], nets[0]));

const n = { apply: 0, preflight: 0, restore: 0, state: 0, accepted: 0, refused: 0 };
const kinds = new Set(), codes = new Set();
const bad = [];
traces.forEach((t, ti) => {
  const net = { ids: nets[t.net][0], pre: nets[t.net][1] };
  let e = new Engine(net, { group: t.group, regate: t.regate });
  t.ops.forEach((o, oi) => {
    if (bad.length >= 5) return;
    const where = `المحرك ${ti}، العملية ${oi} (${o.op}${o.ev && o.ev.type ? ' ' + o.ev.type : ''})`;
    n[o.op] += 1;
    if (o.op === 'state') {
      e.s = JSON.parse(o.text);
    } else if (o.op === 'restore') {
      e = Engine.restore(net, o.text, o.versions);
    } else {
      e.versions = o.versions === null ? null : new Set(o.versions);
      const sent = JSON.stringify(o.ev);
      const res = o.op === 'apply' ? e.apply(o.ev) : e.preflight(o.ev);
      if (JSON.stringify(o.ev) !== sent) bad.push(`${where}: المحرك عدّل الحدث المرسل`);
      if (!same(res, o.res)) bad.push(`${where}: الحكم ${JSON.stringify(res)} والمرجع ${JSON.stringify(o.res)}`);
      if (o.op === 'apply') {
        n[res.ok ? 'accepted' : 'refused'] += 1;
        if (o.ev && typeof o.ev.type === 'string') kinds.add(o.ev.type + (res.ok ? '+' : '-'));
        if (!res.ok) codes.add(res.code);
      }
    }
    if (digest(e) !== o.h) bad.push(`${where}: بصمة الحالة تخالف المرجع`);
    if (o.op === 'restore' && e.dump() !== canonical(JSON.parse(e.dump()))) bad.push(`${where}: النص المحفوظ ليس قياسيًا`);
  });
});
for (const b of bad) console.log('    ' + b.slice(0, 600));
check(`${traces.length} محركًا من اختبارات المرجع: ${n.apply} حدثًا مرسلًا (${n.accepted} مقبولًا و${n.refused} مرفوضًا) `
  + `و${n.preflight} سؤالًا قبل العرض و${n.restore} استعادة من نص. الحكم وبصمة الحالة يطابقان المرجع بعد كل واحد`,
  bad.length === 0);
const events = Object.keys(DATA.schema);
const lacking = events.filter((k) => !kinds.has(k + '+') || !kinds.has(k + '-'));
const known = Object.keys(DATA.reasons).filter((c) => c !== 'internal_error');
const unseen = known.filter((c) => !codes.has(c));
check(`كل نوع حدث مرّ مقبولًا ومرفوضًا: ${events.length} نوعًا` + (lacking.length ? '. ينقص ' + lacking.join(' ') : ''),
  lacking.length === 0);
check(`رموز الرفض التي ظهرت: ${codes.size} من ${known.length}` + (unseen.length ? '. لم يظهر: ' + unseen.join(' ') : ''),
  unseen.length === 0);

// الحفظ والقراءة وإعادة تشغيل السجل في محرك التطبيق نفسه، على أطول سجل في المتجهات
let longest = null;
for (const t of traces) {
  if (t.ops.some((o) => o.op !== 'apply' && o.op !== 'preflight')) continue;
  if (!longest || t.ops.length > longest.ops.length) longest = t;
}
{
  const net = { ids: nets[longest.net][0], pre: nets[longest.net][1] };
  const e = new Engine(net, { group: longest.group, regate: longest.regate });
  for (const o of longest.ops) {
    e.versions = o.versions === null ? null : new Set(o.versions);
    if (o.op === 'apply') e.apply(o.ev);
  }
  const back = Engine.restore(net, e.dump(), e.versions === null ? null : [...e.versions]);
  const again = Engine.replay(net, e.s.log, { group: longest.group, regate: longest.regate });
  check(`سجل من ${e.s.log.length} حدثًا مقبولًا: النص المحفوظ يُقرأ فيعطي النص نفسه، وإعادة تشغيل السجل تعطي الحالات `
    + 'المشتقة نفسها والأدلة نفسها',
    back.dump() === e.dump() && digest(back) === digest(e) && same(again.derive(), e.derive())
    && same(again.s.evidence, e.s.evidence));
  const before = e.dump();
  const r = e.apply({ id: 'x1', type: 'session_end', session: 'لا جلسة' });
  const quiet = !r.ok && e.dump() === before;
  const last = net.ids[net.ids.length - 1];
  const evil = e.apply({ id: '__proto__', type: 'teacher_defer', skills: [last], reason: 'اختبار' });
  const twice = e.apply({ id: '__proto__', type: 'teacher_defer', skills: [last], reason: 'اختبار' });
  check('المرفوض لا يكتب شيئًا. ومعرّف حدث اسمه __proto__ يُحفظ معرّفًا عاديًا: يُعرف تكراره، ويبقى في النص المحفوظ، '
    + 'ولا يمسّ الكائن',
    quiet && (!evil.ok || (twice.duplicate === true && Object.keys(e.s.applied).includes('__proto__')
      && Object.getPrototypeOf(e.s.applied) === Object.prototype
      && Object.keys(JSON.parse(e.dump()).applied).includes('__proto__')
      && Engine.restore(net, e.dump()).dump() === e.dump())));
}

if (!results.every(Boolean)) {
  console.log('أخفق اختبار.');
  process.exit(1);
}
console.log(`نجحت الاختبارات كلها: ${results.length}`);
