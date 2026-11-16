// مطابقة الاستعادة في التطبيق (app/persist.mjs) بالمرجع (persist.py).
//
//     python3 export_persist.py <ملف الخريطة>     (يكتب app/persist_vectors.json)
//     node app/test_persist_conformance.mjs
//
// لكل سجل حفظ صنعه المرجع: الاستعادة في التطبيق تعطي ما أعطاه المرجع: بصمة المحرك، وحالة المجدول كلها،
// والملاحظات (البند غير المحسوم، والنشاط الجاري المحفوظ، والجلسة المختومة)، وسجلات البنود، أو الرفض نفسه.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { canonical } from './engine.mjs';
import { restore, stateOf, Inconsistent } from './persist.mjs';
import { ContentSource } from './items.mjs';

const V = JSON.parse(readFileSync(new URL('persist_vectors.json', import.meta.url), 'utf8'));
const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const digest = (e) => createHash('sha256').update(canonical({ s: e.s, d: e.derive() }), 'utf8').digest('hex');
const same = (a, b) => canonical(a) === canonical(b);
const results = [];

function check(name, cond, detail = '') {
  results.push(Boolean(cond));
  console.log(`  ${cond ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!cond && detail) console.log('        ' + String(detail).slice(0, 500));
}

console.log('=== مطابقة الاستعادة في التطبيق بالمرجع');
const bad = [];
const n = { refused: 0, journal: 0, current: 0, closed: 0 };
for (const [i, v] of V.vectors.entries()) {
  const src = new ContentSource(ITEMS);
  let got;
  try {
    const r = restore(structuredClone(v.record), { types: V.types, source: (s, w) => src.pick(s, w),
      answer: () => 'correct', item_seconds: () => 0, records: [] });
    got = { h: digest(r.engine), state: stateOf(r.scheduler), notes: r.notes, records: r.scheduler.records };
  } catch (err) {
    if (!(err instanceof Inconsistent)) { bad.push(`السجل ${i + 1}: ${err.stack}`); continue; }
    got = { refused: true };
  }
  if (got.refused) n.refused += 1;
  for (const x of got.notes || []) {
    if (x[0] === 'unsettled_item') n.journal += 1;
    if (x[0] === 'current_saved') n.current += 1;
    if (x[0] === 'session_closed') n.closed += 1;
  }
  for (const k of ['refused', 'h', 'state', 'notes', 'records']) {
    if (!same(got[k] ?? null, v.expect[k] ?? null)) {
      bad.push(`السجل ${i + 1}: ${k} يخالف المرجع: ${canonical(got[k] ?? null).slice(0, 200)}`);
      break;
    }
  }
}
check(`${V.vectors.length} سجل حفظ: الاستعادة تطابق المرجع في بصمة المحرك وحالة المجدول والملاحظات وسجلات البنود. `
  + `منها ${n.journal} ببند جارٍ خُتم «غير محسوم»، و${n.current} بنشاط جارٍ حُفظ، و${n.closed} بجلسة خُتمت، `
  + `و${n.refused} رُفضت لأن المجدول فيها يخالف المحرك`, !bad.length, bad.slice(0, 3).join('\n'));
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : 'أخفق اختبار');
process.exit(results.every(Boolean) ? 0 : 1);
