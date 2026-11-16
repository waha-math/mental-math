// حالات المراجعة الحادية عشرة على محرك التطبيق بلغة JavaScript: ترحيل الحالة القديمة.
//
//     node tests/test_r11.mjs [مجلد app]
//
// الحالات ونتائجها المتوقعة في tests/r11_cases.json، والحالات المحفوظة القديمة في tests/r11_fixtures.json (صنعها
// محرك الالتزام 2509126 المرجعي، وصيغة الحفظ واحدة في النسختين). حالتا المجدول في المشغّل الآخر وحده: لا مجدول في
// التطبيق بعد. المجلد الاختياري يشغّل الحالات على نسخة أخرى من التطبيق.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const here = new URL('.', import.meta.url);
const appDir = resolve(process.argv[2] || new URL('../app', here).pathname);
const { Engine, canonical } = await import(pathToFileURL(resolve(appDir, 'engine.mjs')).href);
const CASES = JSON.parse(readFileSync(new URL('r11_cases.json', here), 'utf8'));
const OLD = JSON.parse(readFileSync(new URL('r11_fixtures.json', here), 'utf8')).states;
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

function engineCase(c) {
  const text = OLD[c.id];
  const paths = [['بعد الاستعادة', Engine.restore(undefined, text)]];
  if (!c.no_log) paths.push(['بعد إعادة تشغيل السجل', Engine.replay(undefined, JSON.parse(text).log)]);
  let bad = [];
  for (const [label, e] of paths) bad.push(...compare(e, c.expect, label));
  const agree = () => paths.length < 2 || same(verdict(paths[0][1]), verdict(paths[1][1]));
  if (!agree()) bad.push('الحكم بعد الاستعادة يخالف الحكم بعد إعادة تشغيل السجل');
  if (bad.length || !c.then) return bad;
  for (const [label, e] of paths) {
    const b = runSteps(e, c.then, 't');
    bad.push(...(b.length ? b.map((x) => label + '، المتابعة: ' + x) : compare(e, c.expect_then, label + ' ثم المتابعة')));
  }
  if (!bad.length && !agree()) bad.push('بعد المتابعة: الحكم بعد الاستعادة يخالف الحكم بعد إعادة تشغيل السجل');
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
