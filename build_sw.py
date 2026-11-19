"""يولّد app/sw.js، عامل الخدمة الذي يجعل التطبيق يعمل دون اتصال (9.2).

    python3 build_sw.py           # يكتب app/sw.js
    python3 build_sw.py --check   # يفشل إن لم يطابق app/sw.js الملفات الحالية (خطوة في verify.py)

قائمة الملفات تُستخرج من الشيفرة لا تُكتب يدويًا: كل وحدة يستوردها app/ui/app.mjs بالتتابع، ومعها الصفحة والتنسيق
والمحتوى والبيان والأيقونات. والإصدار بصمة sha256 لمحتواها كلها، فأي تغيير في ملف منها يغيّر sw.js، والمتصفح لا يحدّث
عامل الخدمة إلا إذا تغيّر ملفه.
"""
import hashlib
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
FIXED = ['app/index.html', 'app/ui/style.css', 'slice-content.json', 'app/manifest.webmanifest',
         'app/icons/icon-192.png', 'app/icons/icon-512.png']
IMPORT = re.compile(r"""(?:^|\n)\s*import\s[^;]*?from\s+'([^']+)'""")


def modules(start='app/ui/app.mjs'):
    seen, todo = [], [start]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.append(m)
        for rel in IMPORT.findall((ROOT / m).read_text(encoding='utf-8')):
            todo.append(posixpath.normpath(posixpath.join(posixpath.dirname(m), rel)))
    return sorted(seen)


def render():
    files = sorted(set(FIXED) | set(modules()))
    h = hashlib.sha256()
    for f in files:
        h.update(f.encode() + b'\0' + (ROOT / f).read_bytes() + b'\0')
    version = h.hexdigest()[:16]
    urls = ',\n'.join("  '%s'" % posixpath.relpath(f, 'app') for f in files)
    return TEMPLATE.replace('@VERSION@', version).replace('@URLS@', urls), files


TEMPLATE = """// مولَّد من build_sw.py، لا يُعدَّل يدويًا.
// عامل الخدمة: التطبيق يعمل دون اتصال بعد أول فتح. كل إصدار في مخزن مؤقت باسمه، يُملأ كله أو لا يُثبَّت.
// الإصدار الجديد ينتظر حتى تُغلق كل نوافذ القديم، أو حتى يطلب البالغ التحديث: فلا تجمع صفحة واحدة بين ملفات إصدارين.
const VERSION = '@VERSION@';
const CACHE = 'mental-math-' + VERSION;
const URLS = [
@URLS@,
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
"""

if __name__ == '__main__':
    text, files = render()
    out = APP / 'sw.js'
    if '--check' in sys.argv:
        ok = out.exists() and out.read_text(encoding='utf-8') == text
        print('app/sw.js %s (%d ملفًا)' % ('يطابق الملفات' if ok else 'لا يطابق الملفات: شغّل python3 build_sw.py', len(files)))
        sys.exit(0 if ok else 1)
    out.write_text(text, encoding='utf-8')
    print('كُتب app/sw.js: %d ملفًا' % len(files))
    for f in files:
        print('  ' + f)
