// المتطلب الخارجي من الشاشة (5.1، قرار الأب في 26 نوفمبر: بوابة جاهزية من 3 بنود، وقرار المعلم أيضًا). بإعداد التطبيق
// (PROFILES) ومحتواه، عبر طبقة الخطوات كما تشغّلها الواجهة.
//
//     node tests/test_external.mjs            (والمرجع: python3 tests/test_external.py <الخريطة>)
//
// الطفل الكبير وقرار البداية عند 8-5-2 (جمع المدد)، ويخطئ في بنود 8-5-2 فيلزمه درسها. المتوقع مكتوب من القاعدة قبل التشغيل:
//  يقرأ الساعة:
//   1. الجلسة الأولى: بوابة 8-5-2 وحدها.
//   2. الثانية (اليوم نفسه): بوابة الجاهزية ببنودها الثلاثة من مجموعة ready بترتيبها، ثم افتتاح درس 8-5-2.
//   3. المحرك: المتطلب متحقق باجتياز البوابة، ولا بوابة جاهزية بعدها.
//  لا يقرأ الساعة:
//   4. الثانية: بوابة الجاهزية وحدها، تقف عند أول بند خاطئ، ولا درس لـ 8-5-2.
//   5. اليوم التالي: تُعاد بوابة الجاهزية مرة، وتُخفق، ولا درس.
//   6. بعده: لا بوابة جاهزية (أخفق مرتين) ولا درس لـ 8-5-2، واللوحة تقول إن الدرس مغلق حتى القرار.
//   7. بعد قرار المعلم «يعرف قراءة الساعة»: يُفتح درس 8-5-2 في الجلسة التالية بلا بوابة جاهزية، واللوحة تذكر القرار.
import { readFileSync } from 'node:fs';
import { Engine, canonical } from '../app/engine.mjs';
import { Scheduler } from '../app/scheduler.mjs';
import { ContentSource } from '../app/items.mjs';
import { Stepper } from '../app/stepper.mjs';
import { PROFILES } from '../app/ui/config.mjs';
import { externals, externalText } from '../app/ui/dashboard.mjs';
import { DATA } from '../app/engine_data.mjs';
import { rightOf, wrongOf } from './browser/answer_input.mjs';

const PACK = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8'));
const IDENT = { version: PACK.version, digest: PACK.digest };
export const DAY0 = 20600;
export const SKILL = '8-5-2';


// يعيد لكل يوم تسلسل الأنشطة (نشاط مهارة) وبنود بوابة الجاهزية المعروضة، ونص اللوحة بعد كل يوم
export function run(reads) {
  const P = PROFILES.older1;
  const e = new Engine(undefined, { group: P.group });
  e.apply({ id: 'd0', type: 'teacher_open', skill: SKILL, bypass: [...e.pre[SKILL]], reason: 'x' });
  const src = new ContentSource(PACK.items, true, IDENT);
  const sc = new Scheduler(e, P.types, (k, w) => src.pick(k, w), null, { group: P.group, scope: P.scope, learning: true,
    cap: P.cap, item_seconds: () => 10, records: [], retention: true, content: IDENT, day_cap: P.day_cap });
  const out = [], ready = [], board = [];
  const days = reads ? [DAY0, DAY0] : [DAY0, DAY0, DAY0 + 1, DAY0 + 2, DAY0 + 3];
  days.forEach((day, k) => {
    if (!reads && k === 4) e.apply({ id: 'r0', type: 'teacher_ready', ext: 'clock', reason: 'يقرأ الساعة في البيت' });
    sc.today = day;
    const st = new Stepper(e, sc, () => day * 86400000);
    st.open(sc.g_session());
    const acts = [], shown = [];
    while (st.pending !== null) {
      const [item, w] = st.pending;
      const key = `${w.activity} ${item.skill}`;
      if (acts[acts.length - 1] !== key) acts.push(key);
      if (w.activity === 'ready') shown.push(item.id);
      st.show(st.seq);
      const a = w.activity;
      const right = a === 'ready' ? reads : item.skill !== SKILL;
      const evs = a === 'lesson' || a === 'practice' ? [['end']]
        : [['confirm', right ? rightOf(item) : wrongOf(item)],
          ...(['gate', 'short', 'check', 'retention', 'describe', 'ready'].includes(a) ? [] : [['end']])];
      for (const ev of evs) st.event(st.seq, ev);
    }
    out.push(acts);
    ready.push(shown);
    board.push(externals(e, SKILL, DATA.external_names).map((x) => externalText(x, DATA.ready.fails)));
  });
  return { out, ready, board, ext: e.extReady('clock') };
}

const results = [];
function check(name, ok, info) {
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log('        ' + JSON.stringify(info));
}
const has = (acts, a) => acts.some((k) => k === `${a} ${SKILL}`);
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('=== المتطلب الخارجي، التطبيق');
  const groups = PACK.items.filter((i) => i.skill === SKILL && i.group === 'ready').map((i) => i.id);
  const A = run(true);
  check('يقرأ الساعة: الجلسة الأولى بوابة 8-5-2 وحدها', canonical(A.out[0]) === canonical([`gate ${SKILL}`]), A.out[0]);
  check('يقرأ الساعة: الثانية بوابة الجاهزية ببنودها الثلاثة بترتيبها، ثم افتتاح درس 8-5-2',
    A.out[1][0] === `ready ${SKILL}` && A.out[1][1] === `opening ${SKILL}` && canonical(A.ready[1]) === canonical(groups)
    && groups.length === 3, { out: A.out[1], ready: A.ready[1], groups });
  check('يقرأ الساعة: المتطلب متحقق باجتياز البوابة', A.ext === true && /اجتاز بوابة الجاهزية/.test(A.board[1][0]), A.board);
  const B = run(false);
  check('لا يقرأ: الثانية بوابة الجاهزية وحدها، تقف عند أول بند، ولا درس',
    canonical(B.out[1]) === canonical([`ready ${SKILL}`]) && B.ready[1].length === 1, { out: B.out[1], ready: B.ready[1] });
  check('لا يقرأ: اليوم التالي تُعاد بوابة الجاهزية مرة وتُخفق، ولا درس',
    B.out[2].filter((k) => k === `ready ${SKILL}`).length === 1 && B.ready[2].length === 1 && !has(B.out[2], 'opening')
    && !has(B.out[2], 'lesson'), { out: B.out[2], ready: B.ready[2] });
  check('لا يقرأ: بعده لا بوابة جاهزية ولا درس، واللوحة تقول إن الدرس مغلق حتى القرار',
    !has(B.out[3], 'ready') && !has(B.out[3], 'opening') && !has(B.out[3], 'lesson') && /مرتين، والدرس مغلق حتى قرارك/.test(B.board[3][0]),
    { out: B.out[3], board: B.board[3] });
  check('بعد قرار المعلم: يُفتح درس 8-5-2 بلا بوابة جاهزية، واللوحة تذكر القرار',
    has(B.out[4], 'opening') && !has(B.out[4], 'ready') && B.ext === true && /بقرار المعلم/.test(B.board[4][0]),
    { out: B.out[4], board: B.board[4] });
  for (const r of [A, B]) console.log('        ' + r.out.map((s) => s.join(' ← ') || '—').join('  ||  '));
  console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
  process.exit(results.every(Boolean) ? 0 : 1);
}
