// التحديث والاستعادة على محاكي أندرويد، بالحزم نفسها التي تُبنى للأسرة (release) إلا فحص WebView (MM_INSPECT).
//
//     node tests/android/update_test.mjs <A.apk> <B.apk> <C.apk> <fixture.json>
//
// A و B موقّعان بمفتاح واحد ورقما نسختيهما 1 و2. C بمفتاح آخر. المتوقع مكتوب من قواعد أندرويد والتطبيق قبل التشغيل:
//  1. بعد تثبيت A وكتابة ملف طفل فيه فحص استقلال معلّق، يُثبَّت B فوقه تحديثًا (رقم النسخة 2)، وسجلات الجهاز بعده هي
//     سجلات ما قبله حرفًا بحرف، ويفتح الطفل ملفه فيُعرض بند من فحص الاستقلال.
//  2. C لا يُثبَّت فوق B: أندرويد يرفضه لاختلاف الشهادة، وتبقى B وبياناتها.
//  3. النسخة الاحتياطية تُكتب في التنزيلات (AndroidFiles.save)، وبعد حذف B وتثبيت C الجهاز فارغ، واستيراد الملف يعيد
//     السجلات (إلا rev ووقت الكتابة، كما في 9.2)، ويُعرض للطفل بند من فحص الاستقلال.
// التصدير والاستيراد من الشاشة. ما لا يصل إليه الاختبار: منتقي الملفات في أندرويد (نافذة النظام)، فيُعطى حقل الاختيار
// الملف مباشرة.
import { readFileSync } from 'node:fs';
import { _android as android } from 'playwright-core';
import { canonical } from '../../app/engine.mjs';

const [A, B, C, FX] = process.argv.slice(2);
const PKG = 'net.wahamath.mentalmath';
const fx = JSON.parse(readFileSync(FX, 'utf8'));
const PACK = JSON.parse(readFileSync(new URL('../../slice-content.json', import.meta.url), 'utf8'));
const ROLE = new Map(PACK.items.map((i) => [i.id, i.role]));
const results = [];
function check(name, got, want) {
  const ok = canonical(got) === canonical(want);
  results.push(ok);
  console.log(`  ${ok ? 'نجح' : 'أخفق'}  ${results.length}. ${name}`);
  if (!ok) console.log(`        المتوقع ${JSON.stringify(want).slice(0, 600)}\n        الناتج  ${JSON.stringify(got).slice(0, 600)}`);
}

const [device] = await android.devices();
const sh = async (cmd) => (await device.shell(cmd)).toString().trim();
const version = async () => (await sh(`dumpsys package ${PKG} | grep versionCode`)).split(/\s+/)[0] ?? '';
const install = async (apk) => sh(`pm install -r /data/local/tmp/${apk.split('/').pop()}`);
for (const f of [A, B, C]) await device.push(readFileSync(f), `/data/local/tmp/${f.split('/').pop()}`);

async function open() {
  await sh(`am force-stop ${PKG}`);
  await sh(`am start -n ${PKG}/.MainActivity`);
  const wv = await device.webView({ pkg: PKG }, { timeout: 60000 });
  const page = await wv.page();
  // أول تشغيل بعد إقلاع المحاكي بطيء (تحميل WebView والمحتوى). وعند الإخفاق تُطبع الشاشة التي ظهرت بدلها
  try {
    await page.waitForSelector('[data-screen="who"]', { timeout: 180000 });
  } catch (err) {
    console.log('        الشاشة:', await page.evaluate(() => [location.href, document.getElementById('app')?.dataset.screen,
      document.body.innerText.slice(0, 300)]).catch((x) => String(x)));
    throw err;
  }
  return page;
}
const all = (page) => page.evaluate(async () => {
  const b = await import('/assets/app/backup.mjs');
  const s = await import('/assets/app/store.mjs');
  const db = await s.openDB();
  const r = await b.readAll(db);
  db.close();
  return r;
});
// الطفل يفتح ملفه من الشاشة: معرّف البند الأول المعروض
async function firstItem(page) {
  await page.click('[data-child="older1"]');
  await page.waitForSelector('[data-screen="workshop"]', { timeout: 30000 });
  await page.click('#start');
  await page.waitForSelector('.task[data-ready="true"]', { timeout: 30000 });
  return page.getAttribute('.task', 'data-item');
}
const strip = (rs) => rs.map(({ rev, written_at, ...r }) => r);

console.log(`=== التحديث والاستعادة على ${device.model()} (${await sh('getprop ro.build.version.release')})`);
await sh(`pm uninstall ${PKG}`).catch(() => {});
console.log('  ' + await install(A));
let page = await open();
const put = await page.evaluate(async (r) => {
  const s = await import('/assets/app/store.mjs');
  const db = await s.openDB();
  const out = await s.commit(db, r, 0);
  db.close();
  return out.ok;
}, fx.record);
const before = await all(page);
check('A مثبتة (رقم النسخة 1)، وكُتب ملف الطفل وفيه فحص معلّق', [await version(), put, before.map((r) => r.child)],
  ['versionCode=1', true, ['older1']]);

console.log('  ' + await install(B));
page = await open();
const after = await all(page);
check('B تُثبَّت فوق A تحديثًا (رقم النسخة 2)، والسجلات بعده هي سجلات ما قبله حرفًا بحرف',
  [await version(), JSON.stringify(after) === JSON.stringify(before)], ['versionCode=2', true]);
const shown = await firstItem(page);
check('بعد التحديث يفتح الطفل ملفه فيُعرض بند من فحص الاستقلال', ROLE.get(shown)?.startsWith('check'), true);
console.log(`        البند: ${shown}، والمعلّق في الملف: ${fx.check}`);

const refused = await install(C);
check('C (شهادة أخرى) لا تُثبَّت فوق B، وتبقى B', [/INSTALL_FAILED_UPDATE_INCOMPATIBLE/.test(refused), await version()],
  [true, 'versionCode=2']);

page = await open();
const kept = await all(page);
// من الشاشة: «للكبار» برمز جديد، ثم «احفظ نسخة احتياطية»، فيكتبها التطبيق في التنزيلات (AndroidFiles.save)
const adult = async (pg) => {
  await pg.click('#adult');
  await pg.fill('#pin', '2468');
  await pg.fill('#pin2', '2468');
  await pg.click('#pin-ok');
  await pg.waitForSelector('#backup-save', { timeout: 30000 });
};
await adult(page);
const withPin = await all(page);                         // رمز البالغ صار في سجل الجهاز
await page.click('#backup-save');
await page.waitForFunction(() => /حُفظت في/.test(document.getElementById('adult-msg')?.textContent ?? ''));
const where = (await page.textContent('#adult-msg')).replace('حُفظت في ', '').trim();
const file = await sh(`cat /sdcard/${where}`);
check('النسخة الاحتياطية من الشاشة تُكتب في التنزيلات، وفيها سجلات الجهاز كلها ومنها ملف الطفل كما كان',
  [where.startsWith('Download/mental-math-backup-'), strip(JSON.parse(file).records),
    strip(JSON.parse(file).records.filter((r) => r.child === 'older1'))],
  [true, strip(withPin.filter((r) => r.child !== '@before-import')), strip(kept)]);

await sh(`pm uninstall ${PKG}`);
console.log('  ' + await install(C));
page = await open();
const empty = await all(page);
// الاستيراد من الشاشة: الملف في حقل الاختيار، ثم زر الاستبدال (المنتقي نافذة النظام فيُعطى الحقل الملف مباشرة)
await adult(page);
await page.setInputFiles('#backup-file', { name: 'b.json', mimeType: 'application/json', buffer: Buffer.from(file) });
await page.waitForSelector('#backup-import', { timeout: 30000 });
await page.click('#backup-import');
await page.waitForSelector('[data-screen="who"]', { timeout: 60000 });
const restored = await all(page);
check('بعد حذف B وتثبيت C الجهاز فارغ، والاستيراد من الشاشة يعيد السجلات إلا rev ووقت الكتابة',
  [empty, strip(restored)], [[], strip(JSON.parse(file).records)]);
const shown2 = await firstItem(page);
check('بعد الاستيراد يفتح الطفل ملفه فيُعرض بند من فحص الاستقلال', ROLE.get(shown2)?.startsWith('check'), true);

await device.close();
console.log(results.every(Boolean) ? `نجحت الاختبارات كلها: ${results.length}` : `النتيجة: نجح ${results.filter(Boolean).length} من ${results.length}`);
process.exit(results.every(Boolean) ? 0 : 1);
