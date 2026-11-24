// قرار البداية كما يقرؤه البالغ: «يبدأ من المهارة، متجاوزًا متطلباتها» (17.28). بإعداد التطبيق نفسه (PROFILES).
//
//     node tests/test_start_decision.mjs            (والمرجع: python3 tests/test_start_decision.py <الخريطة>)
//
// المتوقع مكتوب من القاعدة قبل التشغيل، لطفلين: يعرف ما قبل قرار البداية ويخطئ فيها، ويخطئ في كل شيء.
//  1. الجلسة الأولى: بوابة مهارة القرار وحدها.
//  2. الجلسة الثانية («تابع» في اليوم نفسه): افتتاح درس مهارة القرار ثم درسها، بلا تحقق قصير من متطلب تجاوزه القرار.
//  3. في الجلسات الثلاث (والثالثة في اليوم التالي): لا بوابة ولا تحقق قصير لمهارة تحت قرار البداية (أسلافها).
// وقبل الإصلاح (937c498) أخفق الصغير: تحقق قصير من 1-3-3 في الجلسة الثانية، وبإخفاقه نزل إلى درس 1-1-1، وبوابة 1-1-1
// في اليوم التالي.
import { readFileSync } from 'node:fs';
import { Engine, canonical } from '../app/engine.mjs';
import { Scheduler } from '../app/scheduler.mjs';
import { ContentSource } from '../app/items.mjs';
import { Stepper } from '../app/stepper.mjs';
import { PROFILES } from '../app/ui/config.mjs';

const PACK = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
const results = [];
export const DAY0 = 20600;

export function run(child, kid) {
  const P = PROFILES[child];
  const e = new Engine(undefined, { group: P.group });
  P.decisions.forEach((d, k) => e.apply({ id: 'd' + k, type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason: 'x' }));
  const src = new ContentSource(PACK.items, true, IDENT);
  const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
    cap: P.cap, item_seconds: () => 10, records: [], retention: true, content: IDENT, day_cap: P.day_cap });
  const out = [];
  for (const day of [DAY0, DAY0, DAY0 + 1]) {
    sc.today = day;
    const st = new Stepper(e, sc, () => day * 86400000);
    st.open(sc.g_session());
    const acts = [];
    while (st.pending !== null) {
      const [item, w] = st.pending;
      const key = `${w.activity} ${item.skill}`;
      if (acts[acts.length - 1] !== key) acts.push(key);
      st.show(st.seq);
      const a = w.activity;
      const right = kid === 'knows' && !P.decisions.some((d) => d.skill === item.skill);
      const evs = a === 'lesson' || a === 'practice' ? [['end']]
        : [['confirm', right ? item.answer : item.answer + 1], ...(['gate', 'short', 'check', 'retention', 'describe'].includes(a) ? [] : [['end']])];
      for (const ev of evs) st.event(st.seq, ev);
    }
    out.push(acts);
  }
  return { out, anc: new Set(P.decisions.flatMap((d) => [...e.anc[d.skill]])), first: P.decisions[0].skill };
}

function check(name, ok, info) {
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log('        ' + JSON.stringify(info));
}
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('=== قرار البداية، التطبيق');
  for (const child of ['young', 'older1']) {
    for (const kid of ['knows', 'none']) {
      const { out, anc, first } = run(child, kid);
      const label = `${child}، ${kid === 'knows' ? 'يعرف ما قبل القرار' : 'يخطئ في كل شيء'}`;
      check(`${label}: الجلسة الأولى بوابة ${first} وحدها`, canonical(out[0]) === canonical([`gate ${first}`]), out[0]);
      const dec = PROFILES[child].decisions.map((d) => d.skill);
      check(`${label}: الثانية تبدأ بافتتاح درس مهارة قرار ثم درسها، بلا تحقق قصير قبلها`,
        /^opening /.test(out[1][0]) && dec.includes(out[1][0].split(' ')[1]) && out[1][1] === `lesson ${out[1][0].split(' ')[1]}`, out[1]);
      const below = out.flat().filter((k) => /^(gate|short) /.test(k) && anc.has(k.split(' ')[1]));
      check(`${label}: لا بوابة ولا تحقق قصير لما تحت قرار البداية في الجلسات الثلاث`, below.length === 0, { below, out });
      console.log('        ' + out.map((s) => s.join(' ← ')).join('  ||  '));
    }
  }
  console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
  process.exit(results.every(Boolean) ? 0 : 1);
}
