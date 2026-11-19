// النسخة الاحتياطية (9.2): كل ما على الجهاز في ملف واحد، ويُستعاد على الجهاز نفسه أو غيره. لا DOM هنا.
//
// ما في الملف: كل سجلات مخزن الأطفال كما هي، ومنها سجل الجهاز (رمز البالغ مجزّأً، وأسماء الملفات). فالملف خاص بالأسرة.
//
// الضمانات:
// - التصدير يقرأ السجلات كلها في معاملة قراءة واحدة: صورة واحدة متسقة، لا سجل من لحظة وآخر من لحظة بعدها.
// - الاستيراد يُفحص كله قبل أن يُكتب منه شيء: الصيغة، وكل سجل طفل يُستعاد بالمحتوى الحالي كما يُستعاد عند الفتح
//   (check). سجل واحد مرفوض يرفض الملف كله، ولا يتغير شيء.
// - الاستيراد يستبدل ما على الجهاز كله في معاملة واحدة: يُكتب كله أو لا يُكتب منه شيء. وما كان على الجهاز قبله يُحفظ في
//   السجل UNDO في المعاملة نفسها، فيمكن التراجع عنه مرة واحدة.
// - rev كل سجل بعد الاستيراد أكبر من rev ما كان على الجهاز، فنافذة مفتوحة قبل الاستيراد تُرفض كتابتها (conflict) ولا
//   تكتب فوقه.
import { STORE } from './store.mjs';

export const FORMAT = 'mental-math-backup';
export const FORMAT_VERSION = 1;
export const UNDO = '@before-import';

const req = (r) => new Promise((resolve, reject) => {
  r.onsuccess = () => resolve(r.result);
  r.onerror = () => reject(r.error);
});
const done = (tx) => new Promise((resolve) => {
  tx.oncomplete = () => resolve({ ok: true });
  tx.onabort = () => resolve({ ok: false, code: tx.error && tx.error.name === 'QuotaExceededError' ? 'quota' : 'aborted',
    detail: tx.error ? String(tx.error) : null });
});

// السجلات كلها في معاملة قراءة واحدة، بلا سجل التراجع، مرتبة بالمفتاح
export async function readAll(db) {
  const tx = db.transaction(STORE, 'readonly');
  const all = await req(tx.objectStore(STORE).getAll());
  return all.filter((r) => r.child !== UNDO).sort((a, b) => (a.child < b.child ? -1 : a.child > b.child ? 1 : 0));
}

export function makeBackup(records, { content, made_at }) {
  return { format: FORMAT, version: FORMAT_VERSION, made_at, content, records };
}

// يفحص الملف قبل أي كتابة. device: مفتاح سجل الجهاز. children: مفاتيح ملفات الأطفال المعروفة.
// check(record): يرمي إن لم يُستعد السجل. يعيد { ok: true, children } أو { ok: false, code, detail }
export function checkBackup(obj, { device, children, check }) {
  const no = (code, detail = null) => ({ ok: false, code, detail });
  if (obj === null || typeof obj !== 'object' || obj.format !== FORMAT) return no('not_backup');
  if (obj.version !== FORMAT_VERSION) return no('version', String(obj.version));
  if (!Array.isArray(obj.records)) return no('not_backup');
  const seen = new Set();
  const kids = [];
  for (const r of obj.records) {
    if (r === null || typeof r !== 'object' || typeof r.child !== 'string') return no('record');
    if (seen.has(r.child)) return no('duplicate', r.child);
    seen.add(r.child);
    if (!Number.isInteger(r.rev) || r.rev < 1) return no('record', r.child);
    if (r.child === device) {
      const okPin = (r.pin === null && r.salt === null) || (typeof r.pin === 'string' && typeof r.salt === 'string');
      if (!okPin || r.names === null || typeof r.names !== 'object'
        || Object.values(r.names).some((n) => typeof n !== 'string')) return no('device');
      continue;
    }
    if (!children.includes(r.child)) return no('unknown_child', r.child);
    try {
      check(r);
    } catch (err) {
      return no(err.reason ?? 'restore_rejected', `${r.child}: ${err.detail ?? err.message ?? err}`);
    }
    kids.push(r.child);
  }
  return { ok: true, children: kids };
}

// يستبدل ما في المخزن بالسجلات records في معاملة واحدة. keepUndo: يحفظ ما كان قبله في UNDO
function replace(db, records, { keepUndo, made_at }) {
  let tx;
  try {
    tx = db.transaction(STORE, 'readwrite', { durability: 'strict' });
  } catch (err) {
    return Promise.resolve({ ok: false, code: 'write_failed', detail: String(err) });
  }
  const end = done(tx);
  const store = tx.objectStore(STORE);
  const g = store.getAll();
  g.onsuccess = () => {
    const before = g.result.filter((r) => r.child !== UNDO);
    const rev = new Map(before.map((r) => [r.child, r.rev]));
    const top = Math.max(0, ...before.map((r) => r.rev));
    try {
      for (const r of before) if (!records.some((x) => x.child === r.child)) store.delete(r.child);
      // كل سجل يُكتب بـ rev أكبر من كل ما كان على الجهاز: لا تطابق نافذةٌ قديمة rev سجلٍ جديد صدفة
      for (const r of records) store.put({ ...r, rev: Math.max(rev.get(r.child) ?? 0, top) + 1 });
      if (keepUndo) store.put({ child: UNDO, made_at, records: before });
      else store.delete(UNDO);
    } catch (err) {
      try { tx.abort(); } catch { /* أُلغيت */ }
    }
  };
  return end;
}

export function importBackup(db, obj, { made_at }) {
  return replace(db, obj.records, { keepUndo: true, made_at });
}

// ما حُفظ قبل آخر استيراد، أو null
export async function undoInfo(db) {
  const tx = db.transaction(STORE, 'readonly');
  const u = await req(tx.objectStore(STORE).get(UNDO));
  return u ?? null;
}

// يعيد ما كان على الجهاز قبل آخر استيراد، ويحذف سجل التراجع، في معاملة واحدة
export async function undoImport(db) {
  const u = await undoInfo(db);
  if (u === null) return { ok: false, code: 'no_undo' };
  return replace(db, u.records, { keepUndo: false });
}
