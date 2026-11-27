// بيانات طفل لاختبار التحديث على المحاكي: ملف older1 بإعداد التطبيق نفسه (PROFILES)، يمضي يومًا بعد يوم في Node حتى
// يُطلب أول بند من فحص الاستقلال، فيُحفظ وفيه فحص معلّق لم يُعرض بنده. الأيام قبل اليوم الحالي بثلاثين يومًا، فيفتحه
// التطبيق على المحاكي في يوم جديد.
//
//     node tests/android/fixture.mjs > fixture.json
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { Engine } from '../../app/engine.mjs';
import { Scheduler } from '../../app/scheduler.mjs';
import { ContentSource } from '../../app/items.mjs';
import { Stepper } from '../../app/stepper.mjs';
import { PROFILES, TZ } from '../../app/ui/config.mjs';
import { familyDay } from '../../app/ui/link.mjs';

const ROOT = resolve(new URL('../..', import.meta.url).pathname);
const PACK = JSON.parse(readFileSync(join(ROOT, 'slice-content.json'), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
const BY = new Map(PACK.items.map((i) => [i.id, i]));
const child = 'older1', P = PROFILES[child];
const start = Date.now() - 30 * 86400000;

const e = new Engine(undefined, { group: P.group });
P.decisions.forEach((d, k) => {
  const r = e.apply({ id: 'd' + k, type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason: 'تحديد نقطة البدء' });
  if (!r.ok) throw new Error(r.code);
});
let secs = 0;
const src = new ContentSource(PACK.items, true, IDENT);
const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
  cap: P.cap, item_seconds: () => { const x = secs; secs = 0; return x; }, records: [], retention: true, content: IDENT,
  day_cap: P.day_cap ?? null });
const known = new Set();
for (let d = 0; d < 29; d++) {
  const now = start + d * 86400000;
  sc.today = familyDay(now, TZ);
  const st = new Stepper(e, sc, () => now);
  st.open(sc.g_session());
  while (st.pending !== null) {
    const [item, w] = st.pending;
    if (w.activity === 'check') {
      process.stdout.write(JSON.stringify({ record: st.snapshot(child), check: item.id, day: d,
        role: BY.get(item.id).role }));
      process.exit(0);
    }
    st.show(st.seq);
    const a = w.activity;
    const evs = a === 'lesson' || a === 'practice' ? [['end']]
      : [['confirm', known.has(item.skill) || a !== 'gate' ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1)],
        ...(['gate', 'short', 'check', 'retention', 'describe'].includes(a) ? [] : [['end']])];
    if (a === 'lesson') known.add(item.skill);
    for (const ev of evs) { secs = 10; st.event(st.seq, ev); }
  }
}
console.error('لم يُطلب بند فحص استقلال في 29 يومًا');
process.exit(1);
