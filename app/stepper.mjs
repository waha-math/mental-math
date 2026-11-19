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
import { HOW } from './items.mjs';

export const ASSESS = ['gate', 'short', 'check', 'retention', 'describe'];   // بنود التقييم: تنتهي بأول تأكيد
export const SHOWN = ['lesson', 'practice'];                     // بنود العرض: لا سجل لها
export const TEACH_SUPPORT = ['hint', 'extra_model', 'someone']; // الدعم المسموح في بنود التعليم

export class Stepper {
  constructor(engine, sc, clock = null) {
    this.e = engine;
    this.sc = sc;
    this.clock = clock;                           // وقت الحدث كما تعرفه الواجهة: يُكتب في سجل البند (at) عند ختمه
    this.gen = null;
    this.pending = null;                // [البند، المطلوب] أو null
    this.seq = 0;
    this.raw = [];
    this.shown = false;
    this.finished = true;
    this.broken = false;
    this.result = null;
    this.reject = null;                 // سبب رفض آخر حدث خالف العقد
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
    const [item, w] = this.pending;
    // ما سُجّل قبل تغيّر الصلاحية يذهب مع التوقف، فلا يضيع (R17-01)
    const void_ = SHOWN.includes(w.activity) ? new Void(answered)
      : new Void(answered, { shown: this.shown, raw: this.raw, answer: item.answer, assess: this.assess() });
    this._advance(void_);
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

  // عقد الأحداث (R16-02): سبب رفض الحدث، أو null إن كان مسموحًا للبند الجاري. يُفحص قبل أي تغيير.
  // - بند عرض (درس، تدريب): ['end'] وحده.
  // - بند تقييم (بوابة، تحقق قصير، فحص استقلال، فحص احتفاظ): ['confirm', عدد]، و['support', 'requested'] وهو زر
  //   «أحتاج مساعدة»، ولا دعم آخر فيه (3.1).
  // - بند تعليم (افتتاح، دليل فهم): ['confirm', عدد]، و['support', hint أو extra_model أو someone]، و['end'] بعد
  //   إجابة مؤكَّدة.
  allowed(ev) {
    if (!Array.isArray(ev) || !ev.length || typeof ev[0] !== 'string') return 'حدث غير مفهوم';
    const kind = ev[0], a = this.pending[1].activity;
    if (SHOWN.includes(a)) return ev.length === 1 && kind === 'end' ? null : 'بند العرض يقبل الإنهاء وحده';
    if (kind === 'how') {                // بطاقة «كيف حسبتها؟»: لبند يحملها، مرة واحدة قبل التأكيد
      if (!(this.pending[0] && this.pending[0].how)) return 'بطاقة «كيف حسبتها؟» ليست لهذا البند';
      if (ev.length !== 2 || !HOW.includes(ev[1])) return 'بطاقة غير معروفة';
      return this.raw.some((x) => x[0] === 'how' || x[0] === 'confirm') ? 'البطاقة مرة واحدة قبل التأكيد' : null;
    }
    if (kind === 'confirm') {
      if (ev.length === 2 && typeof ev[1] === 'string') {   // بند بطاقة (ج8): التأكيد بمعرّف إحدى بطاقاته
        const cards = this.pending[0] && this.pending[0].cards;
        return cards && cards.includes(ev[1]) ? null : 'بطاقة ليست من بطاقات البند';
      }
      if (this.pending[0] && this.pending[0].cards) return 'بند البطاقة يُجاب ببطاقة';
      return ev.length === 2 && Number.isInteger(ev[1]) ? null : 'التأكيد يحمل عددًا صحيحًا واحدًا';
    }
    if (kind === 'support') {
      if (ev.length !== 2) return 'طلب الدعم يحمل نوعه';
      if (ASSESS.includes(a)) {
        return ev[1] === 'requested' ? null : 'بند التقييم يقبل طلب «أحتاج مساعدة» (requested) وحده';
      }
      return TEACH_SUPPORT.includes(ev[1]) ? null : 'نوع دعم غير مسموح في بند تعليم';
    }
    if (kind === 'end' && ev.length === 1) {
      if (ASSESS.includes(a)) return 'بند التقييم ينتهي بالتأكيد أو بطلب المساعدة';
      return this.raw.some((x) => x[0] === 'confirm') ? null : 'لا إنهاء قبل إجابة مؤكَّدة';
    }
    return 'نوع حدث غير معروف';
  }

  // حدث خام من الواجهة. يعيد:
  // 'ignored' إن لم يكن للطلب الجاري (مكرر أو متأخر)،
  // 'void' إن لم يُحتسب لأن النشاط لم يعد صالحًا،
  // 'rejected' إن خالف عقد الأحداث، والسبب في this.reject، ولا يتغير شيء،
  // 'open' إن بقي البند مفتوحًا،
  // 'next' إن أنهى البند وتم الانتقال.
  // طلب «أحتاج مساعدة» في بند تقييم نهائي بنفسه (3.1): يُسجَّل الطلب ويُختم البند منقطعًا في الانتقال نفسه، بلا تأكيد
  // ولا حدث إنهاء من الواجهة. وأثره على النشاط بقاعدة النشاط (3.6 و6.1 و6.2)
  event(seq, ev) {
    if (!this._check(seq)) return 'ignored';
    if (this._void(true)) return 'void';
    this.reject = this.allowed(ev);
    if (this.reject !== null) return 'rejected';
    const [item, w] = this.pending;
    if (SHOWN.includes(w.activity)) {
      this._advance('correct');
      return 'next';
    }
    this.shown = true;
    const raw = [...this.raw, [...ev]];
    if (this.assess() && ev[0] === 'support') raw.push(['interrupt']);
    if (!itemEnds(raw, this.assess())) {
      this.raw = raw;
      return 'open';
    }
    this._advance([raw, item.answer, this.assess(), this.clock === null ? null : { at: this.clock() }]);
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
    // للاستعادة: تحدّث به آخر بند عُرض حين تختم هذا البند (R23-01)
    if (journal !== null && item.fact !== undefined && item.fact !== null) journal.fact = [...item.fact];
    if (journal !== null && item.v !== undefined && item.v !== null) journal.v = item.v;   // بصمة تعريف البند المعروض (ك1)
    return { kind: live.kind, skill: live.act.skill, act: live.act.toDict(), items, journal };
  }

  snapshot(child = '') {
    return snapshot(this.e, this.sc, this.current(), child);
  }
}
