// حالات المراجعة الحادية عشرة على محرك التطبيق بلغة JavaScript: ترحيل الحالة القديمة.
//
//     node tests/test_r11.mjs [مجلد app]
//
// الحالات ونتائجها المتوقعة في tests/r11_cases.json، والحالات المحفوظة القديمة في tests/r11_fixtures.json (صنعها
// محرك الالتزام 2509126 المرجعي، ومعها النص نفسه بعد قراءته وحفظه بمحرك 16b124a. وصيغة الحفظ واحدة في النسختين).
// كل حالة تُفحص بالاستعادة المباشرة، وبعد المرور بـ 16b124a، وبإعادة تشغيل السجل، والحالة المصححة ثابتة.
// حالتا المجدول في المشغّل الآخر وحده: لا مجدول في التطبيق بعد. المجلد الاختياري يشغّل الحالات على نسخة أخرى من التطبيق.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const here = new URL('.', import.meta.url);
const appDir = resolve(process.argv[2] || new URL('../app', here).pathname);
const { Engine, canonical } = await import(pathToFileURL(resolve(appDir, 'engine.mjs')).href);
const CASES = JSON.parse(readFileSync(new URL('r11_cases.json', here), 'utf8'));
const FIX = JSON.parse(readFileSync(new URL('r11_fixtures.json', here), 'utf8'));
const OLD = FIX.states, VIA = FIX.via_16b124a;
const same = (a, b) => canonical(a) === canonical(b);
const results = [];

function query(e, key) {
  const k = key.indexOf(':');
  const kind = key.slice(0, k), arg = key.slice(k + 1);
  if (kind === 'state') return e.derive()[arg];
  if (kind === 'check') return e.s.checks[arg].state;
  if (kind === 'restart_reason') return e.s.checks[arg].restart_reason ?? null;
  if (kind === 'check_invalid') return Boolean(e.s.checks[arg].invalid);
  if (kind === 'valid_independent') return e.validEvidence(arg, 'independent').length;
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

function runSteps(e, steps, tag) {
  for (const [n, st] of steps.entries()) {
    const ev = { ...st.ev, id: `${tag}${n + 1}` };
    const res = e.apply(ev);
    if ('ok' in st && !res.ok) return [`${ev.type} رُفض (${res.code})، والمتوقع قبوله`];
    if ('code' in st && (res.ok || res.code !== st.code)) {
      return [`${ev.type}: ${res.ok ? 'قُبل' : res.code}، والمتوقع الرفض بـ ${st.code}`];
    }
    if (st.refused && res.ok) return [`${ev.type} قُبل، والمتوقع رفضه`];
  }
  return [];
}

// الحكم الذي يُقارن بين طريقي الاسترجاع: حالات المهارات كلها، والأدلة الصالحة، وحالات المحاولات
const verdict = (e) => [e.derive(),
  e.s.evidence.filter((x) => x.valid).map((x) => [x.skill, x.kind, x.session]).sort(),
  Object.fromEntries(Object.entries(e.s.checks).map(([k, c]) => [k, c.state]))];

// ثبات الترحيل (المراجعة 12): الحالة المصححة تُحفظ وتُستعاد مرتين، فلا يتغير نصها ولا حكمها ولا يُضاف حدث
function stable(e, label) {
  const t1 = e.dump();
  const t2 = Engine.restore(undefined, t1).dump();
  const t3 = Engine.restore(undefined, t2).dump();
  return t1 === t2 && t2 === t3 ? [] : [label + ': الحفظ ثم الاستعادة غيّر الحالة المصححة'];
}

function engineCase(c) {
  const text = OLD[c.id];
  const paths = [['بعد الاستعادة', Engine.restore(undefined, text)],
    ['بعد قراءتها وحفظها بمحرك 16b124a ثم الاستعادة', Engine.restore(undefined, VIA[c.id])]];
  if (!c.no_log) paths.push(['بعد إعادة تشغيل السجل', Engine.replay(undefined, JSON.parse(text).log)]);
  const bad = [];
  for (const [label, e] of paths) bad.push(...compare(e, c.expect, label));
  const disagree = (when) => paths.slice(1).filter(([, e]) => !same(verdict(e), verdict(paths[0][1])))
    .map(([label]) => `${when}الحكم ${label} يخالف حكم الاستعادة المباشرة`);
  bad.push(...disagree(''));
  for (const [label, e] of paths.slice(0, 2)) bad.push(...stable(e, label));
  if (bad.length || !c.then) return bad;
  for (const [label, e] of paths) {
    const b = runSteps(e, c.then, 't');
    bad.push(...(b.length ? b.map((x) => label + '، المتابعة: ' + x) : compare(e, c.expect_then, label + ' ثم المتابعة')));
  }
  if (!bad.length) bad.push(...disagree('بعد المتابعة: '));
  return bad;
}

console.log(`=== حالات المراجعة الحادية عشرة، بلغة JavaScript، على التطبيق في ${appDir}`);
console.log('ترحيل الحالة القديمة في المحرك:');
for (const c of CASES.engine) {
  let bad;
  try { bad = engineCase(c); } catch (x) { bad = ['استثناء: ' + x]; }
  results.push(!bad.length);
  console.log(`  ${bad.length ? 'أخفق' : 'نجح'}  ${c.id} ${c.title}${c.reproduced_by_reviewer ? ' [أعاد المراجع إنتاجه]' : ''}`);
  for (const b of bad.slice(0, 3)) console.log('        ' + b);
}
console.log(`النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
