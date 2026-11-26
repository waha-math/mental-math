// طبقة الوصل بين الشاشة والمجدول (UI-PLAN.md، القسم 6). بلا DOM. تحوّل النقرات إلى أحداث خام، وتطلب الحفظ، ولا تقرر
// شيئًا تربويًا: ما يُعرض وما يُحتسب قرار المجدول والمحرك.
//
// القواعد التي تنفذها (UI-PLAN.md، القسم 2):
// - حالة المولّد ليست مصدر الاستعادة (2.1): كل «ابدأ» يبني المحرك والمجدول من السجل المحفوظ.
// - لا يُعرض بند جديد قبل إقرار حفظ الحالة اللازمة للانتقال (2.5). فشل الحفظ يوقف، والحالة في الذاكرة تبقى.
// - البند يُحفظ معروضًا عند عرضه، وكل حدث فيه يُحفظ فور وقوعه (9.2).
// - الجلسة التعليمية غير فتح التطبيق (2.3): «ابدأ» بعد إغلاق يكمل الجلسة نفسها (Scheduler.g_session).
// - زمن السقف (2.4): وقت عرض البند والعمل عليه. يُستثنى انتظار الحفظ وإخفاء الصفحة.
// - النقر المتكرر أثناء انتظار الحفظ لا يُحتسب (2.4).
import { Engine } from '../engine.mjs';
import { Scheduler } from '../scheduler.mjs';
import { ContentSource } from '../items.mjs';
import { Stepper, ASSESS, SHOWN } from '../stepper.mjs';
import * as persist from '../persist.mjs';
import { load, commit, Saver, claimWriter } from '../store.mjs';

// يوم الأسرة (9.1): التاريخ المحلي في منطقة الأسرة، أيامًا منذ 1970-01-01
export function familyDay(ms, tz) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' })
    .formatToParts(new Date(ms));
  const g = (t) => Number(parts.find((x) => x.type === t).value);
  return Math.floor(Date.UTC(g('year'), g('month') - 1, g('day')) / 86400000);
}

export class Blocked extends Error {      // ما يحتاج بالغًا: السبب في reason
  constructor(reason, detail = null) {
    super(reason);
    this.reason = reason;
    this.detail = detail;
  }
}

const sum = (n) => Object.values(n ?? {}).reduce((a, b) => a + b, 0);

export class Link {
  constructor({ db, child, profile, pack, tz, now = () => Date.now(), mono = () => performance.now(),
    onStatus = () => {}, hooks = {} }) {
    Object.assign(this, { db, child, profile, pack, tz, now, mono, hooks });
    this.onStatus = onStatus;
    this.content = { version: pack.version, digest: pack.digest };
    this.e = null;
    this.sc = null;
    this.st = null;                     // طبقة الخطوات للجلسة المفتوحة في هذه النافذة
    this.saver = null;
    this.release = null;
    this.busy = false;
    this.notes = [];
    this.spent = 0;                     // ثواني العمل على البند المعروض
    this.since = null;                  // بدء القياس الجاري، أو null وهو متوقف
    this.sessionOf = null;              // الجلسة التي عُرض بندها الأخير، لشاشة الختام
  }

  _source() {
    const src = new ContentSource(this.pack.items, true, this.content);
    return (s, w) => src.pick(s, w);
  }

  _seconds() {                          // يُستهلك مرة واحدة لكل بند مختوم
    const s = this.spent;
    this.spent = 0;
    return s;
  }

  _snap() {
    if (this.st !== null && !this.st.broken) return this.st.snapshot(this.child);
    return persist.snapshot(this.e, this.sc, null, this.child);
  }

  // يقرأ السجل ويحجز الكتابة. يعيد 'setup' إن لم يكن للطفل سجل، و'ready' إن استُعيد
  async load() {
    this.release = await claimWriter(this.child);
    if (this.release === null) throw new Blocked('other_window');
    const record = await load(this.db, this.child);
    if (record === null) return 'setup';
    this._restore(record);
    return 'ready';
  }

  _restore(record) {
    let r;
    try {
      r = persist.restore(JSON.parse(JSON.stringify(record)), { types: this.profile.types, source: this._source(),
        answer: null, item_seconds: () => this._seconds(), records: [], today: familyDay(this.now(), this.tz),
        content: this.content });
    } catch (err) {
      throw new Blocked(err instanceof persist.ContentChanged ? 'content_changed' : 'restore_rejected', String(err));
    }
    this.e = r.engine;
    this.sc = r.scheduler;
    this.notes = r.notes;
    this.st = null;
    this.rev = record.rev;
    this.saver = new Saver(this.db, this.child, () => this._snap(), { rev: record.rev, hooks: this.hooks,
      onStatus: (s) => this.onStatus(s) });
  }

  // قرار البالغ عند إنشاء الملف (10.2): قرارات الفتح باسم مهارتها ومتطلباتها المتجاوزة وسببها. لا شيء منها ضمني
  async setup(decisions, reason) {
    if (this.e !== null) throw new Error('الملف قائم');
    const e = new Engine(undefined, { group: this.profile.group });
    decisions.forEach((d, k) => {
      const r = e.apply({ id: 'd' + k, type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason });
      if (!r.ok) throw new Error(`رُفض قرار فتح ${d.skill}: ${r.code}`);
    });
    this.e = e;
    this.sc = new Scheduler(e, this.profile.types, this._source(), null, { group: this.profile.group,
      scope: this.profile.scope, learning: true, cap: this.profile.cap, item_seconds: () => this._seconds(),
      records: [], retention: true, content: this.content, day_cap: this.profile.day_cap ?? null });
    this.saver = new Saver(this.db, this.child, () => this._snap(), { rev: 0, hooks: this.hooks,
      onStatus: (s) => this.onStatus(s) });
    await this.save();
  }

  async save() {
    try {
      await this.saver.request();
    } catch (err) {
      throw new Blocked(err.code === 'conflict' || err.code === 'read_only' ? 'conflict' : 'save', err.code);
    }
  }

  // «ابدأ»: يبني من المحفوظ، ثم يكمل الجلسة الجارية أو يعقد التالية. يعيد 'item' أو 'ended' أو 'done' (لا جلسة باقية).
  // more: جلسة إضافية لمن أراد أن يستمر بعد جلسة يومه. جلسة جارية، ولو إضافية، تُكمَل بالطريق العادي
  async start(more = false) {
    if (this.busy) return 'busy';
    this.busy = true;
    try {
      const record = await load(this.db, this.child);
      if (record.rev !== this.saver.rev) throw new Blocked('conflict', 'rev');
      this._restore(record);
      this.sc.today = familyDay(this.now(), this.tz);
      const st = new Stepper(this.e, this.sc, () => this.now());
      const extra = more && this.sc.cur === null && this.sc.can_extra(this.sc.today);
      const n0 = sum(this.sc.n);
      st.open(extra ? this.sc.g_extra() : this.sc.g_session());
      this.st = st;
      this.sessionOf = this.sc.cur ?? this.e.s.order[this.e.s.order.length - 1] ?? null;
      if (st.finished && st.result === false) {
        this.st = null;
        return 'done';
      }
      if (more && !extra && st.finished && sum(this.sc.n) === n0) this.sc.practiced(null, true);   // لم تعرض بندًا
      await this.save();
      return st.finished ? 'ended' : 'item';
    } finally {
      this.busy = false;
    }
  }

  // البند المطلوب الآن، أو null
  view() {
    const st = this.st;
    if (st === null || st.pending === null) return null;
    const [item, want] = st.pending;
    const kind = SHOWN.includes(want.activity) ? 'shown' : (ASSESS.includes(want.activity) ? 'assess' : 'teach');
    return { seq: st.seq, item, want, kind, raw: st.raw.map((x) => [...x]) };
  }

  // عُرض البند على الطفل: يُحفظ معروضًا، ثم يبدأ قياس وقته. يعيد false إن لم يُعرض (نشاط لم يعد صالحًا)
  async shown(seq) {
    const ok = this.st.show(seq);
    this.sessionOf = this.sc.cur ?? this.sessionOf;
    await this.save();
    if (ok) {
      this.spent = 0;
      this.resume();
    }
    return ok;
  }

  pause() {
    if (this.since !== null) {
      this.spent += (this.mono() - this.since) / 1000;
      this.since = null;
    }
  }

  resume() {
    if (this.since === null && this.st !== null && this.st.pending !== null && this.st.shown) this.since = this.mono();
  }

  // حدث خام من الشاشة للبند المعروض. يعيد نتيجة طبقة الخطوات: ignored، void، rejected، open، next، أو busy
  async press(seq, ev) {
    if (this.busy) return 'busy';
    this.busy = true;
    try {
      this.pause();                     // انتظار الحفظ ليس من زمن السقف
      const keep = this.spent;
      const r = this.st.event(seq, ev);
      if (r === 'rejected' || r === 'ignored') {
        this.spent = keep;
        this.resume();
        return r;
      }
      if (r === 'open') this.spent = keep;
      await this.save();
      if (r === 'open') this.resume();
      return r;
    } finally {
      this.busy = false;
    }
  }

  ended() {
    return this.st !== null && this.st.finished;
  }

  // ما تعرضه جلسة إضافية الآن، بترتيبه: [['resume'|'lesson'|'practice'|'open'، المهارة]، ...]. فارغة: لا تُعرض.
  // الحكم حكم المجدول (can_extra): بعد جلسة مختومة اليوم، وفي اليوم وقت، وعندنا ما يُعرض
  // «أريد المزيد» مفتوح (قرار الأب، 19 نوفمبر مساءً): جلسة إضافية إن كان عندها ما تعرضه، وإلا جلسة عادية أخرى في
  // اليوم نفسه، فيمضي الطفل في الدروس والتقييم بقواعدها (فحص الاستقلال يبقى في يوم بعد دليل الفهم: يرفضه المحرك
  // في يومه). جلسة عادية أخرى لم تعرض بندًا تُنهي المزيد لذلك اليوم (free.dry).
  more() {
    if (this.sc === null || (this.st !== null && !this.st.finished)) return [];
    const day = familyDay(this.now(), this.tz);
    if (this.sc.can_extra(day)) return this.sc.extra_plan(day);
    const dry = this.sc.free && this.sc.free.day === day && this.sc.free.dry;
    return !dry && this.sc.cur === null && (this.sc.start_at === null || this.sc.more()) ? [['session', null]] : [];
  }

  // ما أنجزه الطفل في الجلسة، لرسالة الختام (7.1): عدد البنود التي أكّد فيها إجابة
  summary() {
    const ses = this.sessionOf;
    return { session: ses, answered: this.sc.records.filter((r) => r.session === ses && r.status === 'complete').length };
  }

  // جلسات عُلّمت بتنبيه تاريخ ولم يؤكدها البالغ (9.1)
  flagged() {
    return this.e === null ? [] : this.e.s.order.filter((s) => this.e.s.sessions[s].clock)
      .map((s) => ({ session: s, day: this.e.s.sessions[s].day }));
  }

  // فحوص الاستقلال التي تنتظر المعلم (3.6): معلّقة للمراجعة أو تحتاج إعادة بدء. لا تُبدأ للمهارة محاولة أخرى حتى يتركها
  waiting() {
    if (this.e === null) return [];
    return Object.entries(this.e.s.checks).filter(([, c]) => c.state === 'held' || c.state === 'needs_restart')
      .map(([id, c]) => ({ id, skill: c.skill, state: c.state, reason: c.state === 'held' ? c.hold_reason : c.restart_reason,
        shown: (c.held_items ?? []).length }));
  }

  // ترك المحاولة بقرار المعلم (check_abandoned): لا تُعدّ في المحاولات، ويُسجَّل سببه. والجلسة مغلقة
  async abandonCheck(id, reason) {
    if (this.sc.cur !== null) throw new Error('جلسة مفتوحة: تُترك المحاولة بعد ختمها');
    const ev = { type: 'check_abandoned', check_id: id, reason };
    const v = this.e.preflight({ ...ev, id: 'ask' });
    if (!v.ok) throw new Error(`رُفض ترك ${id}: ${v.code}`);
    this.sc.send(ev);
    await this.save();
  }

  // قرار فتح يسجّله البالغ بعد إنشاء الملف (10.2)، باسم مهارته ومتطلباتها المتجاوزة وسببه. والجلسة مغلقة
  async decide(d, reason) {
    if (this.sc.cur !== null) throw new Error('جلسة مفتوحة: يُسجَّل القرار بعد ختمها');
    const ev = { type: 'teacher_open', skill: d.skill, bypass: d.bypass, reason };
    const v = this.e.preflight({ ...ev, id: 'ask' });
    if (!v.ok) throw new Error(`رُفض قرار فتح ${d.skill}: ${v.code}`);
    this.sc.send(ev);
    await this.save();
  }

  // المتطلب الخارجي (5.1): قرار المعلم أنه متحقق، بدل بوابة الجاهزية. والجلسة مغلقة
  async decideReady(ext, reason) {
    if (this.sc.cur !== null) throw new Error('جلسة مفتوحة: يُسجَّل القرار بعد ختمها');
    const ev = { type: 'teacher_ready', ext, reason };
    const v = this.e.preflight({ ...ev, id: 'ask' });
    if (!v.ok) throw new Error(`رُفض القرار في ${ext}: ${v.code}`);
    this.sc.send(ev);
    await this.save();
  }

  async revokeReady(ext) {
    if (this.sc.cur !== null) throw new Error('جلسة مفتوحة: يُلغى القرار بعد ختمها');
    const d = this.e.decisions('ready', ext)[0];
    if (!d) throw new Error(`لا قرار سارٍ في ${ext}`);
    const r = this.sc.send({ type: 'teacher_revoke', decision: d.id });
    if (!r.ok) throw new Error(`رُفض الإلغاء: ${r.code}`);
    await this.save();
  }

  // قرارات الفتح المسجّلة في الملف: قرارات معلم، لا أدلة إتقان
  decisions() {
    return this.e === null ? [] : this.e.s.decisions.filter((x) => x.kind === 'open')
      .map((x) => ({ skill: x.skills[0], bypass: x.bypass, reason: x.reason, standing: x.standing }));
  }

  async confirmDate(session) {
    const r = this.sc.send({ type: 'date_confirmed', target: session });
    if (!r.ok) throw new Error(`رُفض تأكيد التاريخ: ${r.code}`);
    await this.save();
  }

  close() {
    if (this.release) this.release();
    this.release = null;
  }
}

// يفحص سجل طفل كما يُفحص عند الفتح، بلا قاعدة ولا قفل ولا كتابة: يرمي Blocked إن لم يُستعد (للنسخة الاحتياطية)
export function checkRecord(record, { profile, pack, tz, now = () => Date.now() }) {
  new Link({ db: null, child: record.child, profile, pack, tz, now })._restore(record);
}

// المحرك والمجدول من سجل محفوظ، للقراءة وحدها (لوحة الوالد): بلا قفل ولا كتابة. يرمي Blocked إن لم يُستعد
export function readRecord(record, opts) {
  const l = new Link({ db: null, child: record.child, now: () => Date.now(), ...opts });
  l._restore(record);
  return { e: l.e, sc: l.sc };
}

// سجل الجهاز: رمز البالغ وأسماء الملفات. يُحفظ في مخزن الأطفال بمفتاحه، بالمعاملة نفسها وحارس rev
export async function loadDevice(db, key) {
  return (await load(db, key)) ?? { child: key, rev: 0, pin: null, salt: null, names: {} };
}

export async function saveDevice(db, dev) {
  const { rev, written_at, ...rest } = dev;
  const r = await commit(db, rest, rev);
  if (!r.ok) throw new Blocked('save', r.code);
  dev.rev = r.rev;
  return dev;
}

export async function pinHash(salt, pin, subtle = globalThis.crypto.subtle) {
  const d = await subtle.digest('SHA-256', new TextEncoder().encode(salt + ':' + pin));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
