// مولَّد من build_sw.py، لا يُعدَّل يدويًا.
// عامل الخدمة: التطبيق يعمل دون اتصال بعد أول فتح. كل إصدار في مخزن مؤقت باسمه، يُملأ كله أو لا يُثبَّت.
// الإصدار الجديد ينتظر حتى تُغلق كل نوافذ القديم، أو حتى يطلب البالغ التحديث: فلا تجمع صفحة واحدة بين ملفات إصدارين.
const VERSION = '1fb070f28b9e05e3';
const CACHE = 'mental-math-' + VERSION;
const URLS = [
  'backup.mjs',
  'engine.mjs',
  'engine_data.mjs',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'index.html',
  'items.mjs',
  'manifest.webmanifest',
  'persist.mjs',
  'scheduler.mjs',
  'stepper.mjs',
  'store.mjs',
  'ui/answers.mjs',
  'ui/app.mjs',
  'ui/config.mjs',
  'ui/dashboard.mjs',
  'ui/link.mjs',
  'ui/models.mjs',
  'ui/speech.mjs',
  'ui/style.css',
  '../slice-content.json',
];

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(URLS.map((u) => new Request(u, { cache: 'reload' })))));
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k.startsWith('mental-math-') && k !== CACHE)
    .map((k) => caches.delete(k)))));
});

self.addEventListener('message', (ev) => {
  if (ev.data === 'update') self.skipWaiting();
  if (ev.data === 'version' && ev.source) ev.source.postMessage({ version: VERSION });
});

// ملفات الإصدار من مخزنه وحده. وغيرها من الشبكة كما هو
self.addEventListener('fetch', (ev) => {
  if (ev.request.method !== 'GET') return;
  // فتح مجلد التطبيق (app/) بلا اسم الصفحة يُخدم بالصفحة نفسها
  const nav = ev.request.mode === 'navigate' && new URL(ev.request.url).pathname.endsWith('/');
  ev.respondWith(caches.open(CACHE).then((c) => c.match(nav ? 'index.html' : ev.request, { ignoreSearch: true }))
    .then((hit) => hit || fetch(ev.request)));
});
