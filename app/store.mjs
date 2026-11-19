// الحفظ الذرّي في المتصفح (9.2): IndexedDB، سجل واحد لكل طفل يُكتب في معاملة واحدة.
//
// لماذا سجل واحد: حالة المحرك والأنشطة المحفوظة والمركونة وتقدّم المجدول والبند الجاري تُكتب معًا أو لا يُكتب
// منها شيء. IndexedDB يضمن ذلك للمعاملة الواحدة، ولا يُقرّ بها (complete) إلا بعد اكتمال الكتابة. وطلبتُ
// durability: 'strict' ليُقَرّ الحفظ بعد وصوله إلى القرص لا إلى ذاكرة نظام التشغيل.
//
// الضمانات:
// - «تم الحفظ» لا يظهر إلا بعد complete المعاملة التي تحمل الحالة المطلوبة أو أحدث منها.
// - «تم الحفظ» حالة عامة: تعني أن أحدث ما طُلب حفظه محفوظ (done === seq). كتابة اكتملت وطلب أحدث منها معلّق تُعلَن
//   «أُقرّت» (acked) برقمها وعدد ما بقي، والحالة العامة باقية «جارٍ الحفظ» (ك3 في مراجعة 04e0168). وعد الطلب الأقدم
//   يتحقق عندها، وهو صادق عن نسخته.
// - المعاملة التي تفشل (امتلاء التخزين، فشل الكتابة، إغلاق التطبيق قبل complete) لا تغيّر السجل المحفوظ، والحالة
//   تبقى في الذاكرة غير محفوظة، والفشل يظهر للوالد.
// - كل سجل يحمل rev يزيد بواحد مع كل كتابة. الكتابة تقرأ rev المحفوظ في المعاملة نفسها، وتُلغى إن خالف ما يتوقعه
//   الكاتب: نافذة ثانية كتبت بعده (conflict). فلا تكتب نافذة فوق ما لم تقرأه.
// - نافذة واحدة تكتب لكل طفل: تحجز قفل Web Locks باسم الطفل. النافذة التي لم تحصل عليه للقراءة وحدها. وrev يمنع
//   الكتابة فوق غيرها ولو لم يتوفر القفل.
// - طلبات الحفظ المتكررة تُجمع: لا تُكتب معاملتان معًا، والطلب الذي يأتي أثناء كتابة يُكتب بعدها بأحدث حالة، مرة
//   واحدة لكل ما تراكم.

export const DB_NAME = 'mental-math';
export const STORE = 'children';
export const DB_VERSION = 1;

const req = (r) => new Promise((resolve, reject) => {
  r.onsuccess = () => resolve(r.result);
  r.onerror = () => reject(r.error);
});

export function openDB(name = DB_NAME, idb = globalThis.indexedDB) {
  const r = idb.open(name, DB_VERSION);
  r.onupgradeneeded = () => {
    if (!r.result.objectStoreNames.contains(STORE)) r.result.createObjectStore(STORE, { keyPath: 'child' });
  };
  return req(r);
}

// قراءة السجل المحفوظ في معاملة قراءة: يُرى السجل كله كما أُقرّ آخر مرة، أو لا شيء
export async function load(db, child) {
  const tx = db.transaction(STORE, 'readonly');
  const rec = await req(tx.objectStore(STORE).get(child));
  return rec ?? null;
}

// يكتب السجل في معاملة واحدة إن كان rev المحفوظ هو expectRev (0 لطفل لا سجل له). يعيد بعد complete وحده:
// { ok: true, rev }، أو { ok: false, code } ولم يتغير شيء: conflict، quota، write_failed، aborted.
// hooks للاختبار: beforePut(tx) تُستدعى داخل المعاملة قبل الكتابة، فيمكن إلغاؤها أو إغلاق الصفحة فيها.
export function commit(db, record, expectRev, hooks = {}) {
  return new Promise((resolve) => {
    let tx;
    try {
      tx = db.transaction(STORE, 'readwrite', { durability: 'strict' });
    } catch (err) {
      resolve({ ok: false, code: 'write_failed', detail: String(err) });
      return;
    }
    let outcome = null;
    const store = tx.objectStore(STORE);
    const g = store.get(record.child);
    g.onsuccess = () => {
      const have = g.result ? g.result.rev : 0;
      if (have !== expectRev) {
        outcome = { ok: false, code: 'conflict', have, expected: expectRev };
        tx.abort();
        return;
      }
      if (hooks.beforePut) hooks.beforePut(tx);
      try {
        const p = store.put({ ...record, rev: expectRev + 1, written_at: Date.now() });
        p.onerror = (ev) => {
          const name = p.error && p.error.name;
          outcome = { ok: false, code: name === 'QuotaExceededError' ? 'quota' : 'write_failed', detail: String(p.error) };
          ev.preventDefault();
          tx.abort();
        };
      } catch (err) {
        outcome = { ok: false, code: err.name === 'QuotaExceededError' ? 'quota' : 'write_failed', detail: String(err) };
        try {
          tx.abort();
        } catch { /* المعاملة أُلغيت أو انتهت قبل الكتابة: النتيجة مسجَّلة، و onabort يحسمها */ }
      }
    };
    tx.oncomplete = () => resolve({ ok: true, rev: expectRev + 1 });
    tx.onabort = () => {
      const err = tx.error;
      if (!outcome && err && err.name === 'QuotaExceededError') outcome = { ok: false, code: 'quota', detail: String(err) };
      resolve(outcome || { ok: false, code: 'aborted', detail: err ? String(err) : null });
    };
  });
}

// يحفظ حالة طفل واحد من نافذة واحدة. snap(): السجل الحالي من الذاكرة (persist.snapshot).
// onStatus(status): 'saving' أثناء الكتابة، و'saved' بعد complete ومعه rev حين لا طلب أحدث معلّق، و'acked' بعد
// complete لكتابة يليها طلب معلّق (معه rev و upto و pending)، و'failed' ومعه السبب.
// state: الحالة العامة التي تعرضها الواجهة: 'idle' قبل أي طلب، و'saving'، و'saved'، و'failed'، و'read_only'.
// request() يعيد وعدًا يتحقق بعد أن تُقَرّ كتابة تحمل حالة لا تقل عن حالة لحظة الطلب، أو يفشل بسببها.
export class Saver {
  constructor(db, child, snap, { rev = 0, onStatus = () => {}, hooks = {} } = {}) {
    this.db = db;
    this.child = child;
    this.snap = snap;
    this.rev = rev;                     // آخر rev قرأته هذه النافذة أو كتبته
    this.onStatus = onStatus;
    this.hooks = hooks;
    this.seq = 0;                       // رقم كل طلب
    this.done = 0;                      // آخر طلب أُقرّت كتابة تشمله
    this.waiting = [];
    this.running = false;
    this.readOnly = false;
    this.commits = 0;
    this.last = null;
    this.unsaved = null;                // سبب آخر فشل ما دامت الحالة في الذاكرة غير محفوظة
  }

  // الحالة العامة: «تم الحفظ» فقط حين أُقرّ أحدث ما طُلب. فشلٌ بعد إقرار نسخة أقدم يُبقيها «فشل» لا «تم الحفظ»
  get state() {
    if (this.readOnly) return 'read_only';
    if (this.seq === 0) return 'idle';
    if (this.unsaved) return 'failed';
    return this.done === this.seq ? 'saved' : 'saving';
  }

  request() {
    const n = ++this.seq;
    const p = new Promise((resolve, reject) => this.waiting.push({ n, resolve, reject }));
    if (!this.running) this._run();
    return p;
  }

  // إشعار الواجهة. خطأ في دالة العرض لا يوقف طابور الحفظ ولا يغيّر نتيجته (المراجعة 14)
  _status(s) {
    try {
      this.onStatus(s);
    } catch (err) {
      this.statusErrors = (this.statusErrors || 0) + 1;
    }
  }

  // كل مسار ينتهي بحسم الطلبات التي حملها، و running يعود false في كل حال (المراجعة 14). خطأ صنع اللقطة
  // (snapshot_failed) غير خطأ التخزين (quota، write_failed، aborted، conflict)، والطلب التالي يعيد المحاولة
  async _run() {
    this.running = true;
    try {
      while (this.done < this.seq) {
        if (this.readOnly) {
          this._settle(this.seq, { ok: false, code: 'read_only' });
          break;
        }
        const upto = this.seq;          // ما طُلب حتى الآن تحمله هذه الكتابة
        let record;
        try {
          record = { ...this.snap(), child: this.child };
        } catch (err) {
          this._fail({ ok: false, code: 'snapshot_failed', detail: String(err) });
          break;
        }
        this.unsaved = null;
        this._status({ status: 'saving', upto });
        let r;
        try {
          r = await commit(this.db, record, this.rev, this.hooks);
        } catch (err) {
          r = { ok: false, code: 'write_failed', detail: String(err) };
        }
        this.commits += 1;
        this.last = r;
        if (r.ok) {
          this.rev = r.rev;
          this.done = upto;
          // طلب أحدث جاء أثناء الكتابة: هذه النسخة أُقرّت، وأحدث حالة لم تُحفظ بعد (ك3)
          const pending = this.seq - upto;
          this._status(pending ? { status: 'acked', rev: r.rev, upto, pending } : { status: 'saved', rev: r.rev, upto });
          this._settle(upto, r);
        } else {
          if (r.code === 'conflict') this.readOnly = true;   // نافذة أخرى كتبت: تُعاد القراءة قبل أي كتابة
          this._fail(r);
          break;
        }
      }
    } catch (err) {                     // لا يُتوقع، ولا يُترك طلب بلا حسم
      this._fail({ ok: false, code: 'internal', detail: String(err) });
    } finally {
      this.running = false;
    }
  }

  // الحالة في الذاكرة غير محفوظة: يُرفض كل طلب معلّق بسببه، والطلب التالي يعيد المحاولة بأحدث حالة
  _fail(r) {
    this.last = r;
    this.unsaved = r.code;              // قبل الإشعار: الواجهة التي تقرأ state عند «فشل» تراها «فشل»
    this._status({ status: 'failed', code: r.code, upto: this.seq });
    this._settle(this.seq, r);
  }

  _settle(upto, r) {
    const rest = [];
    for (const w of this.waiting) {
      if (w.n <= upto) {
        if (r.ok) w.resolve(r);
        else w.reject(Object.assign(new Error(r.code), r));
      } else {
        rest.push(w);
      }
    }
    this.waiting = rest;
  }
}

// يحجز الكتابة لطفل في هذه النافذة بقفل Web Locks. يعيد release()، أو null إن كانت نافذة أخرى تحجزه.
export async function claimWriter(child, locks = globalThis.navigator && navigator.locks) {
  if (!locks) return () => {};          // بلا Web Locks: يبقى rev وحده حارسًا
  let release;
  const held = new Promise((r) => { release = r; });
  const got = await new Promise((resolve) => {
    locks.request(`mental-math-child:${child}`, { ifAvailable: true }, (lock) => {
      resolve(Boolean(lock));
      return lock ? held : undefined;
    });
  });
  return got ? release : null;
}

// يطلب تخزينًا مستديمًا (9.2). النتيجة تُعرض للوالد، فالمتصفح قد يرفض
export async function askPersistent(storage = globalThis.navigator && navigator.storage) {
  if (!storage || !storage.persist) return null;
  return storage.persist();
}
