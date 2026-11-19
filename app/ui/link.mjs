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
      records: [], retention: true, content: this.content });
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

  // «ابدأ»: يبني من المحفوظ، ثم يكمل الجلسة الجارية أو يعقد التالية. يعيد 'item' أو 'ended' أو 'done' (لا جلسة باقية)
  async start() {
    if (this.busy) return 'busy';
    this.busy = true;
    try {
      const record = await load(this.db, this.child);
      if (record.rev !== this.saver.rev) throw new Blocked('conflict', 'rev');
      this._restore(record);
      this.sc.today = familyDay(this.now(), this.tz);
      const st = new Stepper(this.e, this.sc, () => this.now());
      st.open(this.sc.g_session());
      this.st = st;
      this.sessionOf = this.sc.cur ?? this.e.s.order[this.e.s.order.length - 1] ?? null;
      if (st.finished && st.result === false) {
        this.st = null;
        return 'done';
      }
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
