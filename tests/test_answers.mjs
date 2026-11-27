// أنواع الإجابة (5.3) في التطبيق، بحالات tests/answer_cases.json نفسها (المرجع: tests/test_answers.py).
import { readFileSync } from 'node:fs';
import { same } from '../app/items.mjs';

const cases = JSON.parse(readFileSync(new URL('./answer_cases.json', import.meta.url), 'utf8'));
// في JavaScript لا فرق بين 7 و7.0، والعدد العائم 3.7 عدد لا نص: الحالتان كما في المرجع
const bad = cases.filter(([v, a, want]) => same(v, a) !== want);
console.log('=== أنواع الإجابة، التطبيق');
for (const [v, a, want, why] of bad) console.log(`  أخفق  ${why}: ${JSON.stringify(v)} مع ${JSON.stringify(a)}، المتوقع ${want}`);
console.log(bad.length ? `النتيجة: نجح ${cases.length - bad.length} من ${cases.length}` : `نجحت الاختبارات كلها: ${cases.length}`);
process.exit(bad.length ? 1 : 0);
