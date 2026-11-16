// حالات المراجعة العاشرة على محرك التطبيق وطبقة بنوده بلغة JavaScript.
//
//     node tests/test_r10.mjs [مجلد app]
//
// النتائج المتوقعة في tests/r10_cases.json، مكتوبة يدويًا من نص القاعدة. المجلد الاختياري يشغّل الحالات على نسخة
// أخرى من التطبيق (مثلًا الالتزام السابق للإصلاح).
import { readFileSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const here = new URL('.', import.meta.url);
const appDir = resolve(process.argv[2] || new URL('../app', here).pathname);
const { Engine, canonical } = await import(pathToFileURL(resolve(appDir, 'engine.mjs')).href);
const { foldItem, indicators } = await import(pathToFileURL(resolve(appDir, 'items.mjs')).href);
const CASES = JSON.parse(readFileSync(new URL('r10_cases.json', here), 'utf8'));
const same = (a, b) => canonical(a) === canonical(b);

function query(e, key) {
  const k = key.indexOf(':');
  const kind = key.slice(0, k), arg = key.slice(k + 1);
  if (kind === 'state') return e.derive()[arg];
  if (kind === 'check') return e.s.checks[arg].state;
  if (kind === 'teach') return e.s.sessions[arg].teach;
  if (kind === 'clock') return e.s.sessions[arg].clock;
  if (kind === 'valid_independent') return e.validEvidence(arg, 'independent').length;
  if (kind === 'independent_items') {
    return e.s.evidence.filter((x) => x.skill === arg && x.kind === 'independent').flatMap((x) => x.items || []);
  }
  if (kind === 'retention_due_day') {
    const nxt = e.retentionNext(arg);
    return nxt === null ? null : nxt[1];
  }
  throw new Error(key);
}

function compare(e, expect, where) {
  const out = [];
  for (const [k, want] of Object.entries(expect)) {
    let got;
    try { got = query(e, k); } catch (x) { got = 'خطأ: ' + x.constructor.name; }
    if (!same(got, want)) out.push(`${where}: ${k} = ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(want)}`);
  }
  return out;
}

function runSteps(e, steps, n) {
  const bad = [];
  for (const st of steps) {
    if (st.do) {
      e = st.do === 'restore' ? Engine.restore(undefined, e.dump()) : Engine.replay(undefined, e.s.log);
      continue;
    }
    n.i += 1;
    const ev = { ...st.ev, id: 'r' + n.i };
    const res = e.apply(ev);
    if ('ok' in st && !res.ok) bad.push(`${ev.type} رُفض (${res.code})، والمتوقع قبوله`);
    else if ('code' in st && (res.ok || res.code !== st.code)) {
      bad.push(`${ev.type}: ${res.ok ? 'قُبل' : res.code}، والمتوقع الرفض بـ ${st.code}`);
    } else if (st.refused && res.ok) bad.push(`${ev.type} قُبل، والمتوقع رفضه`);
    if (bad.length) break;
  }
  return [e, bad];
}

function checkAll(e, expect, label) {
  return [...compare(e, expect, label),
    ...compare(Engine.restore(undefined, e.dump()), expect, label + ' بعد الحفظ والاستعادة'),
    ...compare(Engine.replay(undefined, e.s.log), expect, label + ' بعد إعادة تشغيل السجل')];
}

function engineCase(c) {
  let e = new Engine(), bad;
  const n = { i: 0 };
  [e, bad] = runSteps(e, CASES.bases[c.base] || [], n);
  if (bad.length) return bad.map((b) => 'الأساس: ' + b);
  [e, bad] = runSteps(e, c.steps, n);
  if (!bad.length) bad = checkAll(e, c.expect, 'آخر الخطوات');
  if (!bad.length && c.then) {
    [e, bad] = runSteps(e, c.then, n);
    if (!bad.length) bad = checkAll(e, c.expect_then, 'بعد المتابعة');
  }
  return bad;
}

const dig = (d, path) => path.split('.').reduce((o, k) => o[k], d);
const MISSING = '«غير موجود»';

function foldCase(c) {
  let raw = c.raw;
  if ('split' in c) raw = [...JSON.parse(JSON.stringify(c.raw.slice(0, c.split))), ...c.raw.slice(c.split)];
  return foldItem(raw, c.answer, c.assess);
}

const results = [];
function report(c, bad) {
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${c.id} ${c.title}${c.reproduced_by_reviewer === false ? '' : ' [أعاد المراجع إنتاجه]'}`);
  for (const b of bad.slice(0, 3)) console.log('        ' + b);
}

console.log(`=== حالات المراجعة العاشرة، بلغة JavaScript، على التطبيق في ${relative(process.cwd(), appDir) || '.'}`);
for (const c of CASES.engine) {
  let bad;
  try { bad = engineCase(c); } catch (x) { bad = ['استثناء: ' + x.message]; }
  report(c, bad);
}
const recs = {};
for (const c of CASES.items) {
  let bad = [];
  try {
    const rec = foldCase(c);
    recs[c.id] = rec;
    for (const [k, v] of Object.entries(c.record || {})) {
      const got = k in rec ? rec[k] : MISSING;
      if (!same(got, v)) bad.push(`الحقل ${k} = ${JSON.stringify(got)}، والمتوقع ${JSON.stringify(v)}`);
    }
    const ind = indicators([rec]);
    for (const [k, v] of Object.entries(c.indicators)) {
      if (!same(dig(ind, k), v)) bad.push(`المؤشر ${k} = ${JSON.stringify(dig(ind, k))}، والمتوقع ${JSON.stringify(v)}`);
    }
  } catch (x) { bad = ['استثناء: ' + x.message]; }
  report(c, bad);
}
for (const c of CASES.item_sets) {
  const ind = indicators(c.of.map((k) => recs[k]));
  report(c, Object.entries(c.indicators).filter(([k, v]) => !same(dig(ind, k), v))
    .map(([k, v]) => `المؤشر ${k} = ${JSON.stringify(dig(ind, k))}، والمتوقع ${JSON.stringify(v)}`));
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
