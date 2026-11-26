// إدخال الجواب في اختبارات الشاشة بأنواعه (5.3): ما يُرسل مع التأكيد لجواب صحيح أو خاطئ، وكتابته بالنقر.
// القيمة المرسلة هي ما تبنيه الشاشة (app/ui/answers.mjs valueOf): عدد، أو نص عشري، أو زوج [عدد، عدد].

// القيمة الصحيحة كما يكتبها الطفل
export function rightOf(it) {
  const a = it.answer;
  if (a === null || typeof a !== 'object') return a;
  switch (a.t) {
    case 'dec': { const s = String(a.n).padStart(a.s + 1, '0'); return a.s ? `${s.slice(0, -a.s)}.${s.slice(-a.s)}` : s; }
    case 'frac': return [a.n, a.d];
    case 'qr': return [a.q, a.r];
    case 'dur': return [Math.floor(a.m / 60), a.m % 60];
    case 'money': return [Math.floor(a.p / 100), a.p % 100];
    case 'est': return a.ref;
    default: throw new Error('نوع جواب: ' + a.t);
  }
}

// قيمة خاطئة من النوع نفسه
export function wrongOf(it) {
  if (it.cards) return it.cards.find((c) => c !== it.answer);
  const a = it.answer;
  if (a === null || typeof a !== 'object') return a === 9 ? 8 : a + 1;
  switch (a.t) {
    case 'dec': return rightOf(it) + '1';                    // منزلة زائدة غير صفرية
    case 'frac': return [a.n + 1, a.d];
    case 'qr': return [a.q, a.r + 1];
    case 'dur': return [Math.floor(a.m / 60) + 1, a.m % 60];
    case 'money': return [Math.floor(a.p / 100) + 1, a.p % 100];
    case 'est': return a.hi + 1;
    default: throw new Error('نوع جواب: ' + a.t);
  }
}

// يكتب القيمة بالنقر: الزوج في خانتيه، والعشري بنقطته، والعدد أرقامًا
export async function type(page, v) {
  if (Array.isArray(v)) {
    for (const k of [0, 1]) {
      await page.click(`#answer [data-field="${k}"]`);
      for (const d of String(v[k])) await page.click(`[data-key="${d}"]`);
    }
    return;
  }
  for (const d of String(v)) await page.click(`[data-key="${d}"]`);
}

// خانة الجواب فارغة (بعد خطأ في بند تعليم تُمسح)
export const emptied = (page) => page.waitForFunction(() => {
  const v = document.getElementById('answer')?.dataset.value;
  return v === '""' || v === '["",""]';
});
