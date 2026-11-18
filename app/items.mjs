// طبقة البنود في التطبيق: نقل item_layer.py و content_source.py إلى JavaScript، بالأسماء نفسها.
//
// المرجع هو طبقة البنود بلغة بايثون والقسم 7 من state-transition-spec.md. هذا الملف لا يضيف قاعدة ولا تفسيرًا.
// يُتحقق منه بمتجهات المطابقة: node app/test_items_conformance.mjs
//
// ثلاثة أجزاء:
// 1. foldItem: أحداث البند الخام (تأكيد، دعم، انقطاع، نهاية) إلى الحقول الخمسة في 3.1. و classify: الحقول الخمسة
//    إلى نتيجة واحدة يحتاجها النشاط.
// 2. indicators: المؤشرات الأربعة في 3.2.
// 3. ستة أنشطة تنتهي بحدث للمحرك: البوابة (وإعادة التحقق)، التحقق القصير، افتتاح الدرس، دليل الفهم، فحص
//    الاستقلال، فحص الاحتفاظ.
//
// كل نشاط آلة حالات لا تعرف بنك البنود ولا المحرك. want() تصف ما يُعرض، ومصدر البنود يعطيه أو يقول إنه غير
// موجود فتُستدعى unavailable(). feed() تستقبل نتيجة البند. events() تعيد أحداث المحرك، ويرسلها المشغّل عبر
// Engine.apply بعد أن يسأل Engine.preflight قبل عرض أول بند. حالة كل نشاط كائن بسيط يُحفظ نصًّا ويُستأنف
// (toDict و Activity.fromDict)، وأسماء حقوله هي أسماء المرجع، فالنص المحفوظ يُقرأ بالطبقتين.

export const CALC = ['ف3', 'ف4'];                 // بنود حساب. ما عداها بنود فهم (6.1)
export const SUPPORT = ['hint', 'extra_model', 'someone', 'requested'];
// requested: ضغط الطفل «أحتاج مساعدة» في بوابة أو فحص، ولا يُعطى فيهما دعم

const clone = (x) => JSON.parse(JSON.stringify(x));
const get = (o, k, d) => (Object.prototype.hasOwnProperty.call(o, k) ? o[k] : d);

// ---------------------------------------------------------------- 3.1 الحقول الخمسة
// raw: أحداث البند بترتيبها: ['confirm', قيمة]، ['support', نوع]، ['interrupt']، ['end'].
// assess: بند بوابة أو فحص أو تحقق، ينتهي بأول تأكيد ولا محاولات بعده.
// يعيد الحقول الخمسة ومعها support_unanswered: الدعم الذي جاء بعد آخر إجابة مؤكَّدة ولم تتبعه إجابة. يُحفظ كل دعم
// فور حدوثه، ولو انقطع البند قبل الإجابة التالية (3.1).
export function foldItem(raw, answer, assess) {
  let first = null, before = [], pending = [], last = null, interrupted = false, ended = false;
  const later = [];
  for (const ev of raw) {
    const kind = ev[0];
    if (ended || interrupted) throw new Error('حدث بعد نهاية البند: ' + JSON.stringify(ev));
    if (kind === 'support') {
      if (!SUPPORT.includes(ev[1])) throw new Error('نوع دعم غير معروف: ' + JSON.stringify(ev[1]));
      pending.push(ev[1]);
    } else if (kind === 'confirm') {
      const ok = ev[1] === answer;
      if (first === null) {
        first = ok;
        before = pending;
        if (assess) ended = true;                 // بند التقييم ينتهي بأول تأكيد
      } else {
        later.push({ correct: ok, support: pending });
      }
      pending = [];
      last = ok;
    } else if (kind === 'interrupt') {
      interrupted = true;
    } else if (kind === 'end') {
      if (first === null) throw new Error('نهاية بلا إجابة مؤكَّدة: هذا انقطاع أو طلب دعم');
      ended = true;
    } else {
      throw new Error('حدث بند غير معروف: ' + JSON.stringify(ev));
    }
  }
  if (!(ended || interrupted)) throw new Error('البند لم ينتهِ بعد');
  let unanswered = [];
  if (first === null) before = pending;           // «بند طُلب فيه دعم ثم انقطع يُسجَّل منقطعًا ومعه الدعم»
  else unanswered = pending;                      // دعم بعد آخر إجابة، لم تتبعه إجابة: لا يُنقل إلى ما قبل الأولى
  const status = first !== null ? 'complete' : 'interrupted';
  const final = first === null || interrupted ? 'incomplete' : (last ? 'correct' : 'wrong');
  return { status, first, support_before: before, later, final, support_unanswered: unanswered };
}

// «صحيحة مستقلة»: مكتمل، أول إجابة مؤكَّدة صحيحة، ولا دعم قبلها (3.1)
export function correctIndependent(rec) {
  return rec.status === 'complete' && rec.first === true && rec.support_before.length === 0;
}

// النتيجة التي يحتاجها النشاط: correct، wrong، supported، help، interrupted
export function classify(rec) {
  if (rec.status === 'interrupted') return rec.support_before.length ? 'help' : 'interrupted';
  if (rec.first === false) return 'wrong';
  return rec.support_before.length ? 'supported' : 'correct';
}

// ---------------------------------------------------------------- 3.2 المؤشرات
// النجاح بمساعدة: البنود التي سبق دعمٌ إحدى إجاباتها وبلغت نتيجة نهائية. والمدعومة غير المكتملة: كل بند فيه دعم،
// في أي موضع، ونتيجته النهائية غير مكتملة، ويُعدّ مرة واحدة. الدعم بعد آخر إجابة في بند انتهى بنتيجة يُحفظ ولا
// يدخل المؤشرين، لأن الإجابة لم تأتِ بعده
// والسجل المستبعد (void: بند توقف نشاطه لتغيّر صلاحيته، R17-01) تاريخ محفوظ لا يدخل أي مؤشر
export function indicators(all) {
  const records = all.filter((r) => !r.void);
  const complete = records.filter((r) => r.status === 'complete');
  const used = records.filter((r) => r.support_before.length || r.later.some((a) => a.support.length));
  const reached = used.filter((r) => r.final === 'correct' || r.final === 'wrong');
  const unfinished = records.filter((r) => r.final === 'incomplete' && (r.support_before.length
    || (r.support_unanswered || []).length || r.later.some((a) => a.support.length)));
  const cut = records.filter((r) => r.status === 'interrupted');
  const rate = (a, b) => ({ num: a, den: b, value: b === 0 ? null : a / b });
  const count = (list, f) => list.filter(f).length;
  return {
    first_answer: { ...rate(count(complete, (r) => r.first), complete.length),
      after_support: count(complete, (r) => r.support_before.length) },
    independent: rate(count(complete, correctIndependent), complete.length),
    assisted: { ...rate(count(reached, (r) => r.final === 'correct'), reached.length),
      supported_unfinished: unfinished.length },
    interrupted: { count: cut.length, with_support: count(cut, (r) => r.support_before.length) },
  };
}

// ---------------------------------------------------------------- القوالب
// قالب 6.1: بندان لكل نوع و5 لـ ف3، لا أقل من 6، بنود الحساب أولًا
export function gatePlan(types) {
  const items = [];
  for (const t of types) for (let k = 0; k < (t === 'ف3' ? 5 : 2); k += 1) items.push(t);
  for (let k = 0; items.length < 6; k += 1) items.push(types[k % types.length]);
  return [...items.filter((t) => CALC.includes(t)), ...items.filter((t) => !CALC.includes(t))];   // ترتيب ثابت
}

// التحقق القصير: بند طريقة (فهم) أولًا، ثم بندا حساب
export function shortTypes(types) {
  const calc = types.find((t) => CALC.includes(t)) ?? types[0];
  const und = types.find((t) => !CALC.includes(t)) ?? calc;
  return [und, calc, calc];
}

// «جرّب أولًا» الثابتان: بند حساب وبند من أول أنواع المهارة. والموجَّهة: ثلاثة من أول أنواعها
export function openingTypes(types) {
  const calc = types.find((t) => CALC.includes(t)) ?? types[0];
  return [[calc, types[0]], [types[0], types[0], types[0]]];
}

// ---------------------------------------------------------------- الأنشطة
export class Activity {
  constructor(skill) {
    this.skill = skill;
    this.done = false;
    this.result = null;
    this.shown = {};                              // البنود المعروضة بفئاتها، للعبء
  }

  _count(k) {
    this.shown[k] = (this.shown[k] || 0) + 1;
  }

  _finish(result) {
    this.result = result;
    this.done = true;
  }

  unavailable() {
    throw new Error(this.name + ': لا يُطلب بديل في هذا النشاط');
  }

  // البند المعروض استُبعد لتغيّر صلاحية النشاط (R17-01). exposed: هل أُجيب عنه أو طُلب فيه دعم قبل التغيّر؟ الاستبعاد من
  // التقييم لا يمحو التعرّض (R18-01). الأنشطة التي يغيّر التعرّض بندها التالي تعيد تعريفها. تعيد صحيحًا إن كان البند لا
  // يُعرض ثانية (يُطلب غيره)، وغير ذلك إن جاز عرضه
  voided(_itemId, _exposed) { return false; }

  // أول بند يُطلب للنشاط حقيقته حقيقة آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر (R22-01). تعيد صحيحًا إن
  // غيّر النشاط ما يطلبه (فيُطلب من جديد)، وغير ذلك إن عُرض البند كما هو، فيوسَم بأن حقيقته عُرضت للتو
  // factAt(want): حقيقة البند الذي يُعرض لطلب، دون عرضه
  repeated(_itemId, _factAt = null) { return false; }

  // علاج أنشطة التقييم (قرار الأب، 18 نوفمبر): البند الذي يكرر حقيقة ما عُرض قبله يُؤخَّر، ولا يُستبدل. تُعرض البنود
  // التي تليه في مرحلته، ثم يُعرض هو عند أقرب موضع لا تجاور فيه حقيقتُه حقيقةَ بند الموضع الذي قبله ولا ما بعده:
  // تبقى هوية البنود وخاناتها، ويتغير ترتيب عرضها. قاعدة التوقف تُطبَّق على ترتيب العرض الفعلي، فقد يغيّر التأخير
  // البنود التي يصل إليها الطفل وسبب انتهاء النشاط (ت1 في مراجعة 04e0168). pos موضع الترتيب الجاري و last آخر موضع في مرحلته، و key(q) مفتاح الموضع،
  // و plain(q) ما يُطلب لبند موضع بلا بديل، و after(q) ما قد يُعرض بعد موضع q. alts(q): بدائل بند موضع عند الانقطاع:
  // بديل المؤجَّل، إن انقطع في موضعه الجديد، لا تجاور حقيقتُه ما بعده. والبند المؤجَّل قد يُؤخَّر ثانية، فالفحص يجري
  // قبل كل بند تقييم (driveSteps). تعيد غير صحيح إن لم يوجد موضع، أو كان موضع لاحق طرفًا في تأخير سابق: يُعرض البند
  // موسومًا. الحقل defer لا يُنشأ إلا عند التأخير: مفاتيحه مواضع الترتيب، وقيمه مواضع البنود التي تُعرض فيها
  _defer(pos, last, key, plain, after, factAt, alts = null) {
    if (!factAt || pos >= last) return false;
    const d = this.defer ?? {};
    const cur = get(d, key(pos), pos);            // موضع البند المعروض الآن: قد يكون مؤجَّلًا من قبل
    const same = (f, g) => f !== null && g !== null && JSON.stringify(f) === JSON.stringify(g);
    const fact = factAt(plain(cur));
    if (fact === null) return false;
    for (let q = pos + 1; q <= last; q += 1) if (key(q) in d) return false;
    if (same(factAt(plain(pos + 1)), fact)) return false;
    const mine = [fact, ...(alts ? alts(cur).map((w) => factAt(w)).filter((f) => f !== null) : [])];
    for (let j = 1; j <= last - pos; j += 1) {
      if (same(factAt(plain(pos + j)), fact)) continue;
      if (after(pos + j).some((w) => { const f = factAt(w); return mine.some((m) => same(m, f)); })) continue;
      if (this.defer === undefined) this.defer = {};
      for (let i = 0; i < j; i += 1) this.defer[key(pos + i)] = pos + i + 1;
      this.defer[key(pos + j)] = cur;
      return true;
    }
    return false;
  }

  _at(key, pos) { return get(this.defer ?? {}, key, pos); }

  toDict() {
    return clone({ ...this, _class: this.constructor.pyName });
  }

  static fromDict(d) {
    const { _class, ...fields } = clone(d);
    const obj = Object.create(CLASSES[_class].prototype);
    return Object.assign(obj, fields);
  }
}

// بوابة الإعفاء (6.1). event='recheck_result' يجعلها إعادة تحقق (3.4)
export class GateRun extends Activity {
  static pyName = 'GateRun';
  get name() { return 'gate'; }

  constructor({ skill, types, tolerant = true, event = 'gate_result', attempt = 1 }) {
    super(skill);
    this.plan = gatePlan(types);
    this.has_calc = types.some((t) => CALC.includes(t));
    this.tolerant = tolerant;
    this.event = event;
    this.attempt = attempt;                       // attempt 2: الإعادة ببنود جديدة
    this.stage = 'main';
    this.pos = 0;
    this.errors = [];
    this.alt = {};
    this.cuts = {};
    this.total_cuts = 0;
    this.alt_used = {};                           // بدائل كل نوع المستعملة
    this.alt_index = {};                          // وبديل كل موضع من بدائل نوعه
  }

  // موضع البند المعروض الآن: موضع الترتيب، إلا إن أُخّر بند (defer)
  _p() { return this._at(this.stage + this.pos, this.pos); }

  _key() { return this.stage + this._p(); }

  _type() { return this.stage === 'main' ? this.plan[this._p()] : this.errors[0]; }

  // ما يُطلب لموضع في المرحلة الجارية بلا بديل
  _plain(q) {
    return {
      activity: this.name, role: this.stage === 'main' ? 'gate' : 'gate.compensation',
      type: this.stage === 'main' ? this.plan[q] : this.errors[0], pos: q, alternate: 0, alt_index: null,
      attempt: this.attempt,
    };
  }

  repeated(_itemId, factAt = null) {
    if (get(this.alt, this._key(), 0)) return false;   // بديل بند منقطع: ليس بند موضعه، فلا يُؤخَّر
    const last = this.stage === 'main' ? this.plan.length - 1 : 1;
    // ما بعد آخر المرحلة (أول التعويضية) يُفحص عند عرضه، لا هنا
    const after = (q) => (q < last ? [this._plain(q + 1)] : []);
    const alts = (q) => Array.from({ length: ALT_PEEK }, (_, k) => (
      { ...this._plain(q), role: 'gate.alternate', alternate: 1, alt_index: k }));
    return this._defer(this.pos, last, (q) => this.stage + q, (q) => this._plain(q), after, factAt, alts);
  }

  want() {
    if (this.done) return null;
    const k = this._key();
    return {
      activity: this.name, role: this.stage === 'main' ? 'gate' : 'gate.compensation', type: this._type(),
      pos: this._p(), alternate: get(this.alt, k, 0), alt_index: get(this.alt_index, k, null), attempt: this.attempt,
    };
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    const k = this._key();
    this._count(this.stage === 'main' ? 'gate' : 'comp');
    if (outcome === 'interrupted') {              // يُستبدل ببديل من نوعه
      this.cuts[k] = get(this.cuts, k, 0) + 1;
      this.total_cuts += 1;
      if (this.cuts[k] >= 2 || this.total_cuts >= 3) return this._finish('interrupted');   // تُعلَّق بلا نتيجة
      const t = this._type();
      this.alt[k] = get(this.alt, k, 0) + 1;
      this.alt_index[k] = get(this.alt_used, t, 0);
      this.alt_used[t] = this.alt_index[k] + 1;
      return undefined;
    }
    if (outcome === 'help' || outcome === 'supported') return this._finish('help');
    if (outcome === 'wrong') {
      this.errors.push(this._type());
      if (this.stage === 'comp' || this.errors.length >= 2 || !this.tolerant) return this._finish('fail');
    }
    this.pos += 1;
    if (this.stage === 'main' && this.pos === this.plan.length) {
      if (!this.errors.length) return this._finish('pass');
      this.stage = 'comp';                        // بندان جديدان من نوع الخطأ في آخر البوابة
      this.pos = 0;
    } else if (this.stage === 'comp' && this.pos === 2) {
      this._finish('pass');
    }
    return undefined;
  }

  unavailable() {
    this._finish('interrupted');                  // نفدت البدائل: كالانقطاع، بلا نتيجة
  }

  events() {
    if (this.event === 'recheck_result') {
      return this.result === 'interrupted' ? []
        : [{ type: 'recheck_result', skill: this.skill, ok: this.result === 'pass' }];
    }
    return [{ type: 'gate_result', skill: this.skill, result: this.result, errors: [...this.errors],
      has_calc: this.has_calc }];
  }
}

// التحقق القصير (6.2): 3 بنود. يتوقف عند أول بند غير صحيح مستقل. الانقطاع ينهيه بلا نتيجة ولا حدث
export class ShortCheckRun extends Activity {
  static pyName = 'ShortCheckRun';
  get name() { return 'short'; }

  constructor({ skill, types, stop_early = true }) {
    super(skill);
    this.types = shortTypes(types);
    this.stop_early = stop_early;
    this.pos = 0;
    this.failed = false;
  }

  want() {
    if (this.done) return null;
    return this._w(this._at(String(this.pos), this.pos));
  }

  _w(q) { return { activity: this.name, role: 'short_check', type: this.types[q], pos: q, alternate: 0 }; }

  repeated(_itemId, factAt = null) {
    return this._defer(this.pos, 2, String, (q) => this._w(q), (q) => (q < 2 ? [this._w(q + 1)] : []), factAt);
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    this._count('short');
    if (outcome === 'interrupted') return this._finish(null);
    if (outcome !== 'correct') {
      this.failed = true;
      if (this.stop_early) return this._finish(false);
    }
    this.pos += 1;
    if (this.pos === 3) this._finish(!this.failed);
    return undefined;
  }

  events() {
    return this.result === null ? [] : [{ type: 'short_check_result', skill: this.skill, ok: this.result }];
  }
}

// افتتاح الدرس (6.2): بندا «جرّب أولًا»، ثم مثال الدرس و3 بنود موجَّهة إن لم يصحّا.
// بندا «جرّب أولًا» من نوعي الخطأ في بوابة المهارة إن أخفقت لها بوابة (try_types مع typed)، وإلا الثابتان.
// خطأ في البنود الموجَّهة دليل تعثّر، وطلب الدعم فيها ليس دليلًا. البند المنقطع يُعاد عرضه.
export class OpeningRun extends Activity {
  static pyName = 'OpeningRun';
  get name() { return 'opening'; }

  constructor({ skill, types, try_types = null, try_errors_count = false, typed = false }) {
    super(skill);
    [this.try_types, this.guided] = openingTypes(types);
    const given = Boolean(try_types && try_types.length);
    if (given) this.try_types = [...try_types];
    this.typed = Boolean(typed && given);
    this.try_errors_count = try_errors_count;     // للمقارنة بالمحاكاة القديمة وحدها
    this.stage = 'try';
    this.pos = 0;
    this.try_out = [];
    this.reshown = 0;
  }

  want() {
    if (this.done) return null;
    const t = this.stage === 'try' ? this.try_types[this.pos] : this.guided[this.pos];
    const w = { activity: this.name, role: this.stage === 'try' ? 'opening.try' : 'opening.guided', type: t,
      pos: this.pos, alternate: 0, reshown: this.reshown };
    if (this.stage === 'try' && this.typed) {
      w.typed = true;
      let k = this.try_types.slice(0, this.pos).filter((x) => x === t).length;
      if ((this.flip ?? {})[t]) k = 1 - k;        // لكل نوع بندان: بدأ بالثاني لأن الأول يكرر حقيقة ما عُرض للتو
      w.type_index = k;
    }
    return w;
  }

  // البند المستهلك (أُجيب عنه أو طُلب فيه دعم ثم استُبعد لتغيّر الصلاحية، R18-01): إعادته للتعليم غير استعماله دليلًا
  // لقرار. بند «جرّب أولًا» المستهلك لا بديل له، فلا يُعرض ثانية ونتيجته void: لا يتخطى الشرح ولا يُعدّ خطأ. والبند
  // الموجَّه المستهلك يُعاد عرضه للتعليم موسومًا بأنه مكرر، ونتيجته أيًّا كانت لا تُستعمل: لا ينهي الدرس مبكرًا ولا
  // يُسجَّل تعثّرًا، فيمضي الدرس كاملًا (full_help). الحقلان spent و taint لا يُنشآن إلا عند الاستبعاد
  voided(itemId, exposed) {
    if (!exposed) {
      this.reshown += 1;
      return false;
    }
    if (this.stage === 'guided') {
      this.taint = itemId;
      return false;
    }
    if (this.spent === undefined) this.spent = [];
    if (!this.spent.includes(itemId)) {
      this.spent.push(itemId);
      this.try_out.push('void');
      this.reshown = 0;
      this._afterTry();
    }
    return true;
  }

  // R22-01: بند الافتتاح الأول يكرر حقيقة آخر بند عُرض (آخر بند في البوابة مثلًا). في «جرّب أولًا» بنوعي الخطأ يُبدأ
  // بالبند الآخر من نوعه. وإن لم يكن له آخر، أو كرر الآخر الحقيقة أيضًا، لا يُعرض ونتيجته void: لا يُتخذ منه قرار
  // اختصار ولا يُعدّ خطأ. والبند الموجَّه يُعرض للتعليم ولا تُستعمل نتيجته
  repeated(itemId, _factAt = null) {
    if (this.stage === 'guided') {
      this.taint = itemId;
      return false;
    }
    const t = this.try_types[this.pos];
    if (this.typed && !(this.flip ?? {})[t] && this.try_types.slice(0, this.pos).filter((x) => x === t).length === 0) {
      if (this.flip === undefined) this.flip = {};
      this.flip[t] = true;
      return true;
    }
    this.try_out.push('void');
    this.reshown = 0;
    this._afterTry();
    return true;
  }

  _afterTry() {
    this.pos += 1;
    if (this.pos === 2) {
      if (this.try_out.every((o) => o === 'correct')) return this._finish('skip');
      this.stage = 'guided';
      this.pos = 0;
    }
    return undefined;
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    this._count(this.stage === 'try' ? 'try' : 'lesson');
    if (outcome === 'interrupted') {
      this.reshown += 1;
      return undefined;
    }
    this.reshown = 0;
    if (this.stage === 'guided' && this.taint !== undefined) {
      delete this.taint;
      return this._finish('full_help');          // بند مكرر عُرض للتعليم: نتيجته ليست دليلًا لقرار
    }
    if (this.stage === 'try') {
      this.try_out.push(outcome);
      return this._afterTry();
    }
    if (outcome === 'correct') {
      this.pos += 1;
      if (this.pos === 3) this._finish('skip');   // انتهى الدرس مبكرًا
      return undefined;
    }
    if (outcome === 'wrong' || (this.try_errors_count && this.try_out.includes('wrong'))) {
      return this._finish('full_error');
    }
    return this._finish('full_help');
  }

  events() {
    return [{ type: 'lesson_opening_result', skill: this.skill, outcome: this.result }];
  }
}

// دليل الفهم (3.5): لكل نوع بندان جديدان «صحيحان مستقلان». الإخفاق في بند يستدعي درسًا قصيرًا ثم بندين
// جديدين من نوعه. لكل جولة بنودها. النوع الذي ثبت يبقى ثابتًا في الدرس نفسه. البند المنقطع يُعاد عرضه.
export class EvidenceRun extends Activity {
  static pyName = 'EvidenceRun';
  get name() { return 'evidence'; }

  constructor({ skill, types, proven = [], round = 1 }) {
    super(skill);
    this.types = [...types];
    this.proven = types.filter((t) => proven.includes(t));
    this.round = round;
    this.stage = 'first';
    this.pos = 0;
    this.failed = null;
    this.short_lessons = 0;
    this.reshown = 0;
    if (this._current() === null) this._finish('proven');
  }

  _current() {
    return this.types.find((t) => !this.proven.includes(t)) ?? null;
  }

  want() {
    if (this.done) return null;
    const w = {
      activity: this.name, role: this.stage === 'first' ? 'evidence' : 'evidence.reserve', type: this._current(),
      pos: this.pos, alternate: 0, reshown: this.reshown, round: this.round,
      short_lesson_before: this.stage === 'reserve' && this.pos === 0,
    };
    const swap = (this.swap ?? {})[this._key()];
    if (swap) {                                   // موضع استُهلك بنده: بديل النوع، ومعه البند الذي يحل محله
      w.role = 'evidence.alternate';
      w.alternate = swap.n;
      w.replaces = swap.item;
    }
    return w;
  }

  _key() {
    return `${this._current()}/${this.stage}/${this.pos}`;
  }

  // R22-01: أول بند يُطلب عند دخول دليل الفهم يكرر حقيقة آخر بند عُرض من نشاط آخر: لا يُعرض الآن، ويُطلب لموضعه بديل
  // نوعه في الجولة. وإن لم يوجد بديل، أو كرر الحقيقة هو أيضًا، انتهت الجولة no_alternate بلا حكم
  repeated(itemId, _factAt = null) {
    if (this.swap === undefined) this.swap = {};
    const t = this._current();
    this.swap[this._key()] = { n: 1 + Object.keys(this.swap).filter((k) => k.split('/')[0] === t).length, item: itemId };
    return true;
  }

  // البند المستبعد لتغيّر الصلاحية (R18-01): إن لم يقع فيه إلا العرض أُعيد عرضه كالمنقطع، فلم تُقبل فيه إجابة في محاولة صالحة. وإن أُجيب عنه
  // أو طُلب فيه دعم فقد استُهلك: لا يُحتسب إخفاقًا ولا يُعرض ثانية، ويُطلب لموضعه بديل نوعه في الجولة. swap و spent لا
  // يُنشآن إلا عند أول استبعاد، فلا تتغير صورة النشاط المحفوظ في غير ذلك
  voided(itemId, exposed) {
    if (!exposed) {
      this.reshown += 1;
      return false;
    }
    if (this.swap === undefined) this.swap = {};
    if (this.spent === undefined) this.spent = [];
    if (this.spent.includes(itemId)) return true; // سُجّل عند التوقف، ثم وجده تاريخ السجلات عند الاستئناف: مرة واحدة
    this.spent.push(itemId);
    const t = this._current();
    this.swap[this._key()] = { n: 1 + Object.keys(this.swap).filter((k) => k.split('/')[0] === t).length, item: itemId };
    this.reshown = 0;
    return true;
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    this._count('evidence');
    if (outcome === 'interrupted') {
      this.reshown += 1;
      return undefined;
    }
    this.reshown = 0;
    const t = this._current();
    if (outcome === 'correct') {
      this.pos += 1;
      if (this.pos === 2) {
        this.proven.push(t);
        this.stage = 'first';
        this.pos = 0;
        if (this._current() === null) this._finish('proven');
      }
      return undefined;
    }
    if (this.stage === 'first') {
      this.stage = 'reserve';
      this.pos = 0;
      this.short_lessons += 1;
      return undefined;
    }
    this.failed = t;
    return this._finish('not_proven');
  }

  unavailable() {
    if ((this.swap ?? {})[this._key()]) {
      this._finish('no_alternate');               // لا بديل لبند استُهلك: بلا حكم، ويظهر للبالغ. لا يُعاد البند سرًا
      return;
    }
    this.failed = this._current();
    this._finish('no_items');                     // لا بنود جديدة في البنك: يحتاج مراجعة المعلم
  }

  events() {
    return this.result === 'proven' ? [{ type: 'understanding_proved', skill: this.skill }] : [];
  }
}

// فحص الاستقلال (3.6): 10 خانات، يُجتاز بـ 9 «صحيحة مستقلة»، بلا تغذية راجعة. طلب الدعم يغلق المحاولة.
// البند المنقطع يُستبدل ببديل خانته. انقطاعان في خانة، أو 3 في الفحص، أو نفاد البدائل، أو لا بنود للمحاولة:
// يُعلَّق «للمراجعة» بحدث check_held وسببه، بلا نتيجة. يكمل خاناته العشر بعد أن تتعذر 9 صحيحة.
export class CheckRun extends Activity {
  static pyName = 'CheckRun';
  get name() { return 'check'; }

  constructor({ skill, check_id, content_version, attempt = 'A', slots = 10, need = 9 }) {
    super(skill);
    this.check_id = check_id;
    this.content_version = content_version;
    this.attempt = attempt;
    this.slots = slots;
    this.need = need;
    this.slot = 1;
    this.correct = 0;
    this.answers = {};
    this.alt = {};
    this.cuts = {};
    this.total_cuts = 0;
    this.hold = null;
  }

  want() {
    if (this.done) return null;
    const a = get(this.alt, this._k(), 0);
    return { activity: this.name, role: a === 0 ? 'check' : 'check.alternate', slot: Number(this._k()), alternate: a,
      attempt: this.attempt };
  }

  // خانة البند المعروض الآن: خانة الترتيب، إلا إن أُخّر بند (defer)
  _k() { return String(this._at(String(this.slot), this.slot)); }

  repeated(_itemId, factAt = null) {
    if (get(this.alt, this._k(), 0)) return false;   // بديل بند منقطع: ليس بند خانته، فلا يُؤخَّر
    const w = (q) => ({ activity: this.name, role: 'check', slot: q, alternate: 0, attempt: this.attempt });
    return this._defer(this.slot, this.slots, String, w, (q) => (q < this.slots ? [w(q + 1)] : []), factAt,
      (q) => [{ ...w(q), role: 'check.alternate', alternate: 1 }]);
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    this._count('check');
    const k = this._k();
    if (outcome === 'interrupted') {
      this.cuts[k] = get(this.cuts, k, 0) + 1;
      this.total_cuts += 1;
      if (this.cuts[k] >= 2 || this.total_cuts >= 3) return this._hold('interruptions');
      this.alt[k] = get(this.alt, k, 0) + 1;
      return undefined;
    }
    if (outcome === 'help' || outcome === 'supported') {
      this.answers[k] = 'help';
      return this._finish('help');
    }
    this.answers[k] = outcome;
    if (outcome === 'correct') this.correct += 1;
    this.slot += 1;
    if (this.slot > this.slots) this._finish(this.correct >= this.need ? 'pass' : 'fail');
    return undefined;
  }

  _hold(why) {
    this.hold = why;
    this._finish('held');
  }

  unavailable() {
    this._hold(get(this.alt, this._k(), 0) ? 'no_alternate' : 'no_items');   // لا بنود لهذه المحاولة
  }

  startEvent() {
    return { type: 'check_started', skill: this.skill, check_id: this.check_id,
      content_version: this.content_version };
  }

  events() {
    if (this.result === 'held') {
      return [{ type: 'check_held', skill: this.skill, check_id: this.check_id, reason: this.hold }];
    }
    return [{ type: 'independence_result', skill: this.skill, check_id: this.check_id, result: this.result }];
  }
}

// فحص الاحتفاظ (3.7): 5 بنود جديدة بلا تمهيد وبلا تغذية راجعة، ويُعدّ منها «الصحيح المستقل».
// البند المدعوم لا يُحسب صحيحًا ويمضي الفحص. الانقطاع ينهيه بلا نتيجة ولا حدث، فيُعاد في جلسة لاحقة.
export class RetentionRun extends Activity {
  static pyName = 'RetentionRun';
  get name() { return 'retention'; }

  constructor({ skill, round, size = 5 }) {
    super(skill);
    this.round = round;
    this.size = size;
    this.pos = 0;
    this.correct = 0;
  }

  want() {
    if (this.done) return null;
    return this._w(this._at(String(this.pos), this.pos));
  }

  _w(q) { return { activity: this.name, role: 'deferred_check', round: this.round, pos: q, alternate: 0 }; }

  repeated(_itemId, factAt = null) {
    const last = this.size - 1;
    return this._defer(this.pos, last, String, (q) => this._w(q), (q) => (q < last ? [this._w(q + 1)] : []), factAt);
  }

  feed(outcome) {
    if (this.done) throw new Error('النشاط انتهى');
    this._count('retention');
    if (outcome === 'interrupted') return this._finish(null);
    if (outcome === 'correct') this.correct += 1;
    this.pos += 1;
    if (this.pos === this.size) this._finish('done');
    return undefined;
  }

  events() {
    return this.result === null ? [] : [{ type: 'retention_result', skill: this.skill, correct: this.correct }];
  }
}

export const CLASSES = { GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun, RetentionRun };
export const ASSESSING = ['gate', 'short', 'check', 'retention'];   // أنشطة التقييم: علاج تكرار الحقيقة فيها تأخير البند
export const ALT_PEEK = 8;                        // أقصى عدد بدائل يُسأل عنها لنوع عند تأخير بند

// ---------------------------------------------------------------- التشغيل
// مولّد يعرض بنود النشاط حتى ينتهي. source(skill, want) يعيد البند أو null. يعطي [البند، المطلوب] ويستقبل
// [أحداث البند الخام، جوابه الصحيح، هل هو بند تقييم]، أو نتيجة جاهزة نصًّا.
// pause(want) تُسأل بعد كل بند اكتمل: إن أعادت صحيحًا توقف العرض والنشاط غير منتهٍ، ليُحفظ ويُستأنف في جلسة
// لاحقة. بها يُنفَّذ سقف الوقت الذي لا يقطع بندًا جاريًا (7.1).
// تاريخ التعرّض لبنود نشاط مهارة من السجلات المستبعدة (void) وحدها: لكل بند هل أُجيب عنه أو طُلب فيه دعم قبل استبعاده
// (exposed)، وكم مرة استُبعد (n). السجلات باقية بعد إسقاط النشاط وإنشاء غيره وبعد الحفظ والاستعادة، فهي المرجع، لا حالة
// كائن النشاط (R19-01)
export function exposure(records, skill, activity) {
  const out = {};
  for (const r of records || []) {
    if (r.void && r.item && r.skill === skill && r.activity === activity) {
      const h = out[r.item] ?? (out[r.item] = { exposed: false, n: 0 });
      h.n += 1;
      if (r.first !== null || (r.support_before || []).length || (r.support_unanswered || []).length) h.exposed = true;
    }
  }
  return out;
}

// حقيقة البند الذي يعرضه المصدر لطلب، دون عرضه: الطلب يحمل peek فلا يُعدّ البند معروضًا
export function peekFact(source, skill, want) {
  const it = source(skill, { ...want, peek: true });
  const ok = it !== null && it !== undefined && typeof it === 'object' && !Array.isArray(it);
  return ok && it.fact !== undefined && it.fact !== null ? [...it.fact] : null;
}

export function* driveSteps(act, source, records = null, pause = null, history = null, prev = null) {
  let entry = true;                               // أول بند يُعرض في هذا الدخول إلى النشاط
  let inner = null;                               // آخر بند عُرض من هذا النشاط في هذا الدخول، إن احتُسب تعرّضًا
  let moved = [];                                 // بنود تقييم أُخّرت قبل البند الذي سيُعرض الآن
  for (;;) {
    let w = act.want();
    if (w === null) return act;
    const item = source(act.skill, w);
    if (item === null || item === undefined) {
      act.unavailable();
      continue;
    }
    // history(act): تاريخ التعرّض لبنود هذا النشاط (exposure). بند استُهلك من قبل لا يُعرض ثانية ولو أُنشئ النشاط من
    // جديد: يُطلب بديله. وبند عُرض ولم تُقبل فيه إجابة في محاولة صالحة يُعاد عرضه موسومًا بالإعادة (R19-01)
    const known = history && typeof item === 'object' && !Array.isArray(item) ? history(act)[item.id] : undefined;
    if (known && known.exposed && act.voided(item.id, true)) continue;
    if (known) {                                  // يُعرض ثانية: موسوم بالإعادة، وبأنه مكرر إن كان مستهلكًا
      w = { ...w, reshown: Math.max(w.reshown ?? 0, known.n) };
      if (known.exposed) w.repeated = true;
    }
    // prev(): آخر بند عُرض للمهارة نفسها في الجلسة نفسها من نشاط آخر، [معرّفه، حقيقته]، إن كان يُحتسب تعرّضًا. الحقيقة
    // نفسها لا تُعرض في بندين متتاليين (3.5) ولو كانا من نشاطين (R22-01): النشاط يغيّر ما يطلبه إن كان له علاج، وإلا
    // عُرض البند موسومًا بأن حقيقته عُرضت للتو. داخل النشاط الواحد يضمن المحتوى ذلك (content_sequence)
    const isItem = item !== null && typeof item === 'object' && !Array.isArray(item);
    // وفي أنشطة التقييم العلاج تأخير البند، والتأخير يغيّر الترتيب الذي ضمنه المحتوى، فيُفحص كل بند فيها مع البند
    // الذي عُرض قبله من النشاط نفسه أيضًا (بديل بند انقطع قد يجاور بندًا مؤجَّلًا)
    const facted = isItem && item.fact !== undefined && item.fact !== null;
    const p = entry && prev && facted ? prev() : (facted && ASSESSING.includes(act.name) ? inner : null);
    if (p && p[0] !== item.id && JSON.stringify(p[1]) === JSON.stringify(item.fact)) {
      if (act.repeated(item.id, (q) => peekFact(source, act.skill, q))) {
        if (ASSESSING.includes(act.name)) moved.push(item.id);
        continue;
      }
      w = { ...w, fact_just_seen: p[0] };
    }
    if (moved.length) {                           // يُحفظ أن الترتيب تغيّر ولماذا: هذا البند عُرض قبل ما أُخّر
      w = { ...w, ahead_of: moved };
      moved = [];
    }
    entry = false;
    const got = yield [item, w];
    if (facted) {                                 // قاعدة Scheduler.seen نفسها: المنقطع بلا إجابة ولا دعم لا يُحتسب
      const raw = typeof got === 'string' ? null : got[0];
      const counts = raw === null ? got !== 'interrupted'
        : raw.some((ev) => ev[0] === 'confirm' || ev[0] === 'support')
          || !(raw.length && raw[raw.length - 1][0] === 'interrupt');
      inner = counts ? [item.id, item.fact] : null;
    } else {
      inner = null;
    }
    if (typeof got === 'string') {
      act.feed(got);
    } else {
      const [raw, correct, assess] = got;
      const rec = foldItem(raw, correct, assess);
      if (records !== null) {
        const isObj = item !== null && typeof item === 'object' && !Array.isArray(item);
        const r = { ...rec, skill: act.skill, activity: act.name, role: w.role, item: isObj ? (item.id ?? null) : null };
        if (isObj && item.reshown_same_fact) r.reshown_after_interrupt = true;   // 3.6: «أُعيد عرضه بعد انقطاع»
        if (w.fact_just_seen) r.fact_just_seen = w.fact_just_seen;   // حقيقته حقيقة آخر بند عُرض من نشاط آخر، ولا علاج له
        if (w.ahead_of) r.ahead_of = [...w.ahead_of];   // عُرض قبل بنود أُخّرت لأنها تكرر حقيقة ما سبقها
        if (w.repeated) r.repeated_after_void = true;   // بند مستهلك أُعيد للتعليم، لا دليلًا لقرار
        if (w.replaces) {                         // R18-01: بديل بند استُهلك، ووصف التعرّض السابق لحقيقته (3.5)
          r.replaces = w.replaces;
          r.fact_seen_before = Boolean(isObj && item.fact_seen_before);
        }
        records.push(r);
      }
      act.feed(classify(rec));
    }
    if (pause && pause(w) && !act.done) return act;
  }
}

// يشغّل مولّد خطوات حتى نهايته، ويجيب عن كل بند بـ answer(item, want). يعيد قيمة المولّد.
export function runSync(gen, answer) {
  let r = gen.next();
  while (!r.done) r = gen.next(answer(...r.value));
  return r.value;
}

// الغلاف المتزامن لـ driveSteps
export function drive(act, source, answer, records = null, pause = null) {
  return runSync(driveSteps(act, source, records, pause), answer);
}

// ---------------------------------------------------------------- مصدر البنود من محتوى الشريحة
// يحوّل ما تطلبه want() إلى بند بعينه من slice-content.json. يتحقق أن نوع دليل البند هو النوع المطلوب.
// allowSameFact لبدائل المجال الصغير التي لا عدد آخر يحقق شرط خانتها: بقرار الأب (3.6) تُعاد الحقيقة نفسها بعد
// الانقطاع، ويُعلَّم البند reshown_same_fact.
const LESSON_ROLES = ['lesson.watch', 'lesson.model', 'lesson.fade', 'lesson.nomodel'];

export class ContentSource {
  constructor(items, allowSameFact = true, content = null) {
    this.content = content;                       // هوية الحزمة التي منها البنود: {version, digest}، إن عُرفت
    this.by = new Map();
    for (const it of items) {
      const k = it.skill + '|' + it.group + '|' + it.role;
      if (!this.by.has(k)) this.by.set(k, []);
      this.by.get(k).push(it);
    }
    this.allowSameFact = allowSameFact;
    this.served = [];                             // معرّفات البنود المعروضة بترتيبها
  }

  _list(skill, group, role) {
    return this.by.get(skill + '|' + group + '|' + role) || [];
  }

  _typed(skill, group, role, t) {
    return this._list(skill, group, role).filter((i) => i.evidence === t);
  }

  static _at(list, k) {
    return Number.isInteger(k) && k >= 0 && k < list.length ? list[k] : null;
  }

  pick(skill, w) {
    const a = w.activity, at = ContentSource._at;
    let it;
    if (a === 'lesson') {
      it = at(LESSON_ROLES.flatMap((r) => this._list(skill, 'lesson', r)), w.pos);
    } else if (a === 'practice') {
      it = at(this._list(skill, 'practice', 'practice'), w.pos);
    } else if (a === 'gate') {
      const g = (w.attempt ?? 1) === 1 ? 'gate' : 'regate';       // الإعادة وإعادة التحقق ببنود جديدة
      if (w.alternate) it = at(this._typed(skill, g, 'gate.alternate', w.type), w.alt_index);
      else if (w.role === 'gate') it = at(this._list(skill, g, 'gate'), w.pos);
      else it = at(this._typed(skill, g, 'gate.compensation', w.type), w.pos);
    } else if (a === 'short') {
      it = at(this._list(skill, 'short', 'short_check'), w.pos);
    } else if (a === 'opening') {
      if (w.typed) it = at(this._typed(skill, 'tryfirst', 'opening.try', w.type), w.type_index);   // 6.2
      else it = at(this._list(skill, 'opening', w.role), w.pos);
    } else if (a === 'evidence') {                // كل جولة ببنودها الجديدة (3.5)
      // البديل (R18-01) برقمه بين بدائل النوع في الجولة، لا بموضع البند الذي يحل محله
      it = at(this._typed(skill, 'evidence', w.role, w.type).filter((i) => (i.round ?? 1) === (w.round ?? 1)),
        w.alternate ? w.alternate - 1 : w.pos);
    } else if (a === 'check') {
      it = this._list(skill, 'check' + w.attempt, w.role).find((i) => i.slot === w.slot) ?? null;
      if (it && (it.note || '').startsWith('لا قيمة أخرى')) {
        it = this.allowSameFact ? { ...it, reshown_same_fact: true } : null;
      }
    } else if (a === 'retention') {               // 3.7: خمسة بنود جديدة لكل جولة
      it = at(this._list(skill, 'deferred', 'deferred_check').filter((i) => i.slot === w.round), w.pos);
    } else {
      throw new Error('نشاط غير معروف: ' + a);
    }
    if (it !== null) {
      if ('type' in w && it.evidence !== w.type && a !== 'lesson' && a !== 'practice') {
        throw new Error(`المحتوى يخالف الطبقة: ${it.id} يُطلب ${w.type} والبند ${it.evidence}`);
      }
      if (!w.peek) this.served.push(it.id);         // سؤال عن بند دون عرضه (تأخير بند التقييم)
    }
    return it;
  }
}
