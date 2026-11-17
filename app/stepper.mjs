// طبقة الخطوات: تشغّل مولّد المجدول خطوة خطوة للواجهة، وتحدّد حدود الانتقال واللقطة (المرحلة 0د). نقل stepper.py.
//
// القواعد (UI-PLAN.md، القسم 2):
// - الإجابة النهائية انتقال واحد: سجل البند، وتقدّم النشاط، وحدث المحرك المترتب عليه، وإزالة البند الجاري. كلها في
//   خطوة واحدة للمولّد، ولا تؤخذ لقطة بين أجزائها: snapshot لا تُتاح إلا والمولّد واقف عند طلب بند، أو منتهٍ.
// - حالة المولّد ليست مصدر الاستعادة. اللقطة تحمل الحالة المحفوظة والنشاط الجاري والبند الجاري، ومنها تُبنى متابعة
//   جديدة: restore ثم Stepper جديد على sc.g_continue() أو ما يليها.
// - البند الذي لم يُعرض بعد لا journal له، فيُطلب نفسه بعد الاستعادة. والبند الذي عُرض يُختم بانقطاع عندها.
// - كل طلب بند له رقم seq. الحدث الذي يحمل رقمًا غير رقم الطلب الجاري يُهمل: إجابة مكررة أو متأخرة لا تُحتسب مرتين.
// - استثناء داخل الانتقال يعطّل الطبقة (broken): لا لقطة ولا خطوة بعده، والحالة المحفوظة السابقة تبقى هي المرجع.
import { itemEnds, snapshot } from './persist.mjs';
import { Void } from './scheduler.mjs';

export const ASSESS = ['gate', 'short', 'check', 'retention'];   // بنود التقييم: تنتهي بأول تأكيد
export const SHOWN = ['lesson', 'practice'];                     // بنود العرض: لا سجل لها

export class Stepper {
  constructor(engine, sc) {
    this.e = engine;
    this.sc = sc;
    this.gen = null;
    this.pending = null;                // [البند، المطلوب] أو null
    this.seq = 0;
    this.raw = [];
    this.shown = false;
    this.finished = true;
    this.broken = false;
    this.result = null;
    this.halt = null;                   // آخر توقف لتغيّر الصلاحية: [الجلسة، السبب، المهارة، النوع]
  }

  // يبدأ مولّد خطوات (sc.g_continue() أو sc.g_follow_learning() ...) ويتقدم إلى أول طلب بند
  open(gen) {
    if (!this.finished) throw new Error('مولّد جارٍ لم ينتهِ');
    this.gen = gen;
    this.finished = false;
    return this._advance(undefined);
  }

  _advance(got) {
    let r;
    try {
      r = this.gen.next(got);
    } catch (err) {
      this.broken = true;               // انتقال لم يكتمل: الحالة في الذاكرة لا يُعتمد عليها
      throw err;
    }
    if (r.done) {
      this.pending = null;
      this.finished = true;
      this.result = r.value;
    } else {
      this.pending = r.value;
      this.seq += 1;
    }
    this.raw = [];
    this.shown = false;
    return this.pending;
  }

  _check(seq) {
    if (this.broken) throw new Error('الطبقة معطّلة بعد انتقال لم يكتمل: تُعاد القراءة من المحفوظ');
    return this.pending !== null && seq === this.seq;
  }

  assess() {
    return ASSESS.includes(this.pending[1].activity);
  }

  // النشاط الجاري لم يعد صالحًا (قرار وقع أثناءه): لا يُعرض البند ولا يُحتسب الحدث. المجدول يحفظ النشاط أو يركنه أو
  // يُسقطه بقاعدة السبب ويختم الجلسة، والسبب في this.halt للبالغ
  _void(answered) {
    if (this.sc.live_invalid() === null) return false;
    this._advance(new Void(answered));
    this.halt = this.sc.halts[this.sc.halts.length - 1];
    return true;
  }

  // عُرض البند على الطفل. من هنا إغلاق التطبيق انقطاعٌ في البند. يعيد false إن لم يُعرض: طلب آخر، أو نشاط لم يعد
  // صالحًا (R16-01)
  show(seq) {
    if (!this._check(seq) || this._void(false)) return false;
    this.shown = true;
    return true;
  }

  // حدث خام من الواجهة: ['support', نوع] أو ['confirm', قيمة] أو ['end']. يعيد 'ignored' إن لم يكن للطلب الجاري،
  // و'open' إن بقي البند مفتوحًا، و'next' إن أنهى البند وتم الانتقال، و'void' إن لم يُحتسب لأن النشاط لم يعد صالحًا
  event(seq, ev) {
    if (!this._check(seq)) return 'ignored';
    if (this._void(true)) return 'void';
    const [item, w] = this.pending;
    if (SHOWN.includes(w.activity)) {
      if (ev[0] !== 'end') return 'ignored';
      this._advance('correct');
      return 'next';
    }
    this.shown = true;
    const raw = [...this.raw, [...ev]];
    if (!itemEnds(raw, this.assess())) {
      this.raw = raw;
      return 'open';
    }
    this._advance([raw, item.answer, this.assess()]);
    return 'next';
  }

  current() {
    if (this.broken) throw new Error('الطبقة معطّلة: لا لقطة');
    if (this.pending === null) return null;
    const live = this.sc.live;
    if (live.kind === 'show') return { ...live, items: [] };
    const [item, w] = this.pending;
    const items = [...live.prior, ...live.recs.filter((r) => r.item).map((r) => r.item)];
    const journal = this.shown
      ? { item: item.id ?? null, want: w, answer: item.answer, assess: this.assess(), raw: this.raw.map((x) => [...x]) }
      : null;
    return { kind: live.kind, skill: live.act.skill, act: live.act.toDict(), items, journal };
  }

  snapshot(child = '') {
    return snapshot(this.e, this.sc, this.current(), child);
  }
}
