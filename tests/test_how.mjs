// بطاقة «كيف حسبتها؟» في فحص 3-5-3. القاعدة والتوقعات في tests/test_how.py، والمسار نفسه يُطابَق بشريط المرجع
// tests/how_tape.json: الحالة الدائمة كاملة مع البطاقة.
//
//     node tests/test_how.mjs [مجلد app]
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const appDir = resolve(process.argv[2] || new URL('../app', import.meta.url).pathname);
const load = (f) => import(pathToFileURL(resolve(appDir, f)).href);
const { Engine, canonical } = await load('engine.mjs');
const { Scheduler } = await load('scheduler.mjs');
const { ContentSource, foldItem, classify, evidence } = await load('items.mjs');
const { Stepper } = await load('stepper.mjs');
const persist = await load('persist.mjs');

const ITEMS = JSON.parse(readFileSync(new URL('../slice-content.json', import.meta.url), 'utf8')).items;
const BY = new Map(ITEMS.map((i) => [i.id, i]));
const TYPES = { '1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
  '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3'] };
const TAPE = JSON.parse(readFileSync(new URL('./how_tape.json', import.meta.url), 'utf8'));
const results = [];
const dump = (x) => canonical(x ?? null);
function check(title, got, want) {
  const ok = dump(got) === dump(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${title}`);
  if (!ok) console.log(`        المتوقع ${dump(want).slice(0, 500)}\n        الناتج  ${dump(got).slice(0, 500)}`);
}

console.log('=== بطاقة «كيف حسبتها؟»، التطبيق');
const W = { activity: 'check', role: 'check', slot: 8, alternate: 0, attempt: 'A' };
const st0 = new Stepper(null, null);
const allowed = (id, ev, raw = [], w = W) => { st0.pending = [BY.get(id), w]; st0.raw = raw; return st0.allowed(ev); };
const plain = ITEMS.find((i) => i.skill === '3-5-3' && i.role === 'check' && i.slot === 7).id;
check('عقد الحدث كما في المرجع',
  [allowed('3-5-3/checkA/15', ['how', 'back']), allowed('3-5-3/checkA/15', ['how', 'up']),
    allowed('3-5-3/checkA/15', ['how', 'other']), allowed(plain, ['how', 'up']),
    allowed('3-5-3/checkA/15', ['how', 'sideways']), allowed('3-5-3/checkA/15', ['how']),
    allowed('3-5-3/checkA/15', ['how', 'up'], [['how', 'back']]),
    allowed('3-5-3/checkA/15', ['how', 'up'], [], { activity: 'practice', pos: 0 })],
  [null, null, null, 'بطاقة «كيف حسبتها؟» ليست لهذا البند', 'بطاقة غير معروفة', 'بطاقة غير معروفة',
    'البطاقة مرة واحدة قبل التأكيد', 'بند العرض يقبل الإنهاء وحده']);

const it = BY.get('3-5-3/checkA/15');
check('السجل كما في المرجع', [[['confirm', it.answer]], [['confirm', it.answer + 1]], [['support', 'requested'], ['interrupt']]]
  .map((raw) => {
    const w = [['how', 'up'], ...raw];
    return [dump(foldItem(w, it.answer, true)) === dump(foldItem(raw, it.answer, true)), classify(foldItem(w, it.answer, true)),
      evidence(w, it.answer).how ?? null, 'how' in evidence(raw, it.answer)];
  }), [[true, 'correct', 'up', false], [true, 'wrong', 'up', false], [true, 'help', 'up', false]]);

class Kid {
  constructor() { this.known = new Set(); }
  events(item, w) {
    const a = w.activity;
    if (a === 'lesson' || a === 'practice') { if (a === 'lesson') this.known.add(item.skill); return [['end']]; }
    const assess = ['gate', 'short', 'check', 'retention', 'describe'].includes(a);
    const ans = this.known.has(item.skill) ? item.answer : (item.answer < 99 ? item.answer + 1 : item.answer - 1);
    return [['confirm', ans], ...(assess ? [] : [['end']])];
  }
}
function run(how) {
  const kid = new Kid(), hits = [];
  const e = new Engine(undefined, { group: 'older' });
  [['3-5-1', ['3-3-2', '3-2-3']], ['3-5-2', ['3-2-1', '3-3-1', '2-5-2']]].forEach(([skill, bypass], k) =>
    e.apply({ id: 'd' + k, type: 'teacher_open', skill, bypass, reason: 'قرار الشريحة في 10.2' }));
  const src = new ContentSource(ITEMS);
  const sc = new Scheduler(e, TYPES, (k, w) => src.pick(k, w), null, { group: 'older', scope: new Set(['3-5-1', '3-5-2', '3-5-3']),
    learning: true, cap: 600, item_seconds: () => 45, records: [], retention: true, day_cap: 3000 });
  for (let d = 0; d < 60; d++) {
    sc.today = d;
    const st = new Stepper(e, sc);
    st.open(sc.g_session());
    while (st.pending !== null) {
      const [item, w] = st.pending;
      let evs = kid.events(item, w);
      if (how && item.how) { hits.push(item.id); evs = [['how', how], ...evs]; }
      for (const ev of evs) if (st.event(st.seq, ev) === 'rejected') throw new Error(st.reject);
    }
    if (sc.log.some((x) => x[1] === 'check_pass' && x[2] === '3-5-3')) {
      return { hits, final: JSON.parse(dump({ ...persist.stateOf(sc), engine: e.dump(), records: sc.records })) };
    }
  }
  throw new Error('لم يُجتز فحص 3-5-3');
}
const a = run('up');
check('المسار حتى اجتياز فحص 3-5-3 يطابق شريط المرجع: ما عُرضت فيه البطاقة، والحالة الدائمة كاملة',
  [a.hits, dump(a.final) === dump(TAPE.final)], [TAPE.hits, true]);

const ok = results.filter(Boolean).length;
console.log(`النتيجة: نجح ${ok} من ${results.length}`);
process.exit(ok === results.length ? 0 : 1);
