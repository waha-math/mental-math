// أنواع الإجابة في الشاشة (5.3): خانات الإدخال لكل نوع، وقيمة ما كُتب، ونص الجواب للعرض والنطق.
// التحقق نفسه في items.mjs (same)، كما في المرجع.

// نوع جواب البند: int للعدد الصحيح وللتقدير (يُكتب عددًا)، و dec للعشري، والأزواج بخانتين
export function kindOf(answer) {
  if (answer === null || typeof answer !== 'object') return 'int';
  return answer.t === 'est' ? 'int' : answer.t;
}
export const PAIR = ['frac', 'qr', 'dur', 'money'];

// أسماء الخانتين لكل زوج
export const FIELDS = {
  ar: { frac: ['البسط', 'المقام'], qr: ['الخارج', 'الباقي'], dur: ['ساعة', 'دقيقة'], money: ['جنيه', 'قرش'] },
  en: { frac: ['numerator', 'denominator'], qr: ['quotient', 'remainder'], dur: ['hours', 'minutes'], money: ['pounds', 'piastres'] },
};

// ما كتبه الطفل قيمةً تُرسل مع التأكيد، أو null إن لم يكتمل: العدد عددًا، والعشري نصًّا كما كُتب (يُقارن بلا أعداد
// عائمة)، والزوج [عدد، عدد]
export function valueOf(kind, s) {
  if (PAIR.includes(kind)) return s.fields.every((f) => f !== '') ? s.fields.map(Number) : null;
  if (s.typed === '' || s.typed === '.') return null;
  return kind === 'dec' ? s.typed : Number(s.typed);
}

// المعدود في العربية: 1 واحد، 2 مثنى، 3 إلى 10 جمع، 11 إلى 99 مفرد منصوب، وما بعدها مفرد
function counted(n, [one, two, few, many]) {
  const r = n % 100;
  if (n === 1) return `${one} واحد`;
  if (n === 2) return two;
  if (r >= 3 && r <= 10) return `${n} ${few}`;
  if (r >= 11 && r <= 99) return `${n} ${many}`;
  return `${n} ${one}`;
}
const AR = { h: ['ساعة', 'ساعتان', 'ساعات', 'ساعة'], m: ['دقيقة', 'دقيقتان', 'دقائق', 'دقيقة'],
  L: ['جنيه', 'جنيهان', 'جنيهات', 'جنيهًا'], P: ['قرش', 'قرشان', 'قروش', 'قرشًا'] };

// نص الجواب للعرض في الدرس وللنطق
export function format(answer, lang = 'ar') {
  if (answer === null || typeof answer !== 'object') return String(answer);
  const en = lang === 'en';
  switch (answer.t) {
    case 'dec': {
      const s = String(answer.n).padStart(answer.s + 1, '0');
      return answer.s ? `${s.slice(0, -answer.s)}.${s.slice(-answer.s)}` : s;
    }
    case 'frac': return `${answer.n}/${answer.d}`;
    case 'qr': return en ? `quotient ${answer.q}, remainder ${answer.r}` : `الخارج ${answer.q} والباقي ${answer.r}`;
    case 'dur': {
      const h = Math.floor(answer.m / 60), m = answer.m % 60;
      if (en) return `${h} h ${m} min`;
      return [h && counted(h, AR.h), m && counted(m, AR.m)].filter(Boolean).join(' و') || '0';
    }
    case 'money': {
      const L = Math.floor(answer.p / 100), P = answer.p % 100;
      if (en) return `${L} pounds ${P} piastres`;
      return [L && counted(L, AR.L), P && counted(P, AR.P)].filter(Boolean).join(' و') || '0';
    }
    case 'est': return `≈ ${answer.ref}`;
    default: return JSON.stringify(answer);
  }
}

// مفتاح القيمة الحالية للاختبار والعرض (data-value)
export const shown = (kind, s) => JSON.stringify(PAIR.includes(kind) ? s.fields : s.typed);
