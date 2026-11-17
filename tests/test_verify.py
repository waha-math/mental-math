#!/usr/bin/env python3
"""يختبر مسار التحقق نفسه (tests/verify.py): لا يعلن نجاحًا بمتجهات قديمة، ولا حين يخفق مصدِّر.

    python3 tests/test_verify.py

الحالات، ونتائجها مكتوبة من القاعدة:
1. شجرة سليمة فيها متجهات قديمة فاسدة مزروعة في app/: التحقق السريع ينجح، لأنه لا ينسخها ويولّد غيرها.
   (لو استُعملت القديمة لأخفقت المطابقة، فنجاحه دليل أنها لم تُستعمل.)
2. الشجرة نفسها والمصدِّر export_conformance.py مكسور عمدًا: رمز الخروج غير صفر، والناتج يسمّي خطوة التوليد،
   ولا يحوي سطر النجاح، ولا تُشغَّل بعده أي مطابقة.
3. مصدِّر يخرج بصفر دون أن يكتب ملفه: إخفاق كذلك.
4. اختبار مطابقة يطبع سطرًا أخيرًا ليس سطر نجاح ويخرج بصفر: إخفاق كذلك.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify  # noqa: E402


def check(tree):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'verify.py'), '--quick', '--tree', tree],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return r.returncode, r.stdout


def edit(path, fn):
    s = open(path, encoding='utf-8').read()
    open(path, 'w', encoding='utf-8').write(fn(s))


results = []


def expect(title, got, want):
    ok = got == want
    results.append(ok)
    print('  %s  %s' % ('نجح' if ok else 'أخفق', title))
    if not ok:
        print('        %r، والمتوقع %r' % (got, want))


with tempfile.TemporaryDirectory() as tmp:
    tree = os.path.join(tmp, 'tree')
    verify.copy_tree(verify.ROOT, tree)
    for v in verify.VECTORS:                                 # متجهات قديمة فاسدة: لو قُرئت لأخفقت المطابقة
        open(os.path.join(tree, 'app', v), 'w', encoding='utf-8').write('{"nets":{},"traces":[{"stale":true}]}')
    code, out = check(tree)
    expect('1. شجرة سليمة ومتجهات قديمة مزروعة: ينجح بمتجهات مولَّدة الآن',
           [code, 'نجح التحقق: 7 خطوة من 7' in out], [0, True])

    exporter = os.path.join(tree, 'export_conformance.py')
    good = open(exporter, encoding='utf-8').read()
    edit(exporter, lambda s: 'raise SystemExit("مصدِّر مكسور عمدًا")\n' + s)
    code, out = check(tree)
    expect('2. مصدِّر مكسور والمتجهات القديمة موجودة: فشل واضح عند التوليد، بلا مطابقة ولا إعلان نجاح',
           [code != 0, 'أخفق التحقق عند: توليد متجهات المحرك وطبقة البنود' in out, 'نجح التحقق' in out, 'مطابقة' in out],
           [True, True, False, False])

    edit(exporter, lambda s: 'raise SystemExit(0)\n' + good)
    code, out = check(tree)
    expect('3. مصدِّر يخرج بصفر ولا يكتب ملفه: فشل', [code != 0, 'لم يُكتب الملف app/conformance_vectors.json' in out,
                                                    'نجح التحقق' in out], [True, True, False])

    open(exporter, 'w', encoding='utf-8').write(good)
    edit(os.path.join(tree, 'app', 'test_conformance.mjs'), lambda s: "console.log('أخفق 1');\nprocess.exit(0);\n" + s)
    code, out = check(tree)
    expect('4. اختبار يخرج بصفر وسطره الأخير ليس سطر نجاح: فشل',
           [code != 0, 'أخفق التحقق عند: مطابقة محرك التطبيق' in out, 'نجح التحقق' in out], [True, True, False])

print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
