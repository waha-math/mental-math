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
5 إلى 7 (R23-02). «آخر بند عُرض» يُغيَّر عمدًا في التطبيق وحده: في التشغيل (تكشفه مطابقة المجدول)، وعند ختم البند في
   الاستعادة (تكشفه مطابقة الاستعادة)، وتغيير لا يغيّر قرارًا (يكشفه شريط المراجعة 22 الذي يحمل last عند كل بند).
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

    # R23-02: اختلاف «آخر بند عُرض» (last) بين المرجع والتطبيق يجب أن تكشفه المطابقة. يُغيَّر عمدًا في التطبيق وحده
    def swap(path, old, new):
        s = open(path, encoding='utf-8').read()
        if s.count(old) != 1:
            raise AssertionError('لم أجد الموضع المراد تغييره في %s' % path)
        open(path, 'w', encoding='utf-8').write(s.replace(old, new))
        return s

    conf = os.path.join(tree, 'app', 'test_conformance.mjs')
    edit(conf, lambda s: s.replace("console.log('أخفق 1');\nprocess.exit(0);\n", '', 1))     # يعود اختبار المطابقة سليمًا
    js_sched = os.path.join(tree, 'app', 'scheduler.mjs')
    keep = swap(js_sched, 'fact: [...item.fact], counts };', 'fact: [...item.fact], counts: !counts };')
    code, out = check(tree)
    expect('5. التطبيق يكتب «هل يُحتسب تعرّضًا» معكوسًا في التشغيل: مطابقة المجدول تُخفق',
           [code != 0, 'أخفق التحقق عند: مطابقة المجدول' in out, 'نجح التحقق' in out], [True, True, False])
    open(js_sched, 'w', encoding='utf-8').write(keep)

    js_persist = os.path.join(tree, 'app', 'persist.mjs')
    keep = swap(js_persist, 'counts: exposed(j.raw) };', 'counts: !exposed(j.raw) };')
    code, out = check(tree)
    expect('6. التطبيق يكتبه معكوسًا عند ختم البند في الاستعادة: مطابقة الاستعادة تُخفق',
           [code != 0, 'أخفق التحقق عند: مطابقة الاستعادة' in out, 'نجح التحقق' in out], [True, True, False])
    open(js_persist, 'w', encoding='utf-8').write(keep)

    # تغيير لا يغيّر قرارًا: معرّف آخر بند. شريط المراجعة 22 يحمل last عند كل بند، فيكشفه اختباره على التطبيق
    keep = swap(js_sched, 'this.last = { session: this.cur, skill, activity, item: item.id ?? null,',
                'this.last = { session: this.cur, skill, activity, item: null,')
    r = subprocess.run(['node', os.path.join(HERE, 'test_r22.mjs'), os.path.join(tree, 'app')],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    expect('7. التطبيق يكتب معرّف آخر بند خطأً ولا يتغير قرار: اختبار الشريط يُخفق عند مقارنة آخر بند',
           [r.returncode != 0, any(l.strip().startswith('أخفق  1ب.') for l in r.stdout.split('\n'))], [True, True])
    open(js_sched, 'w', encoding='utf-8').write(keep)

    # تأخير بند التقييم: مطابقة اللغتين فيه بحالات مشتركة tests/defer_cases.json متوقَّعها واحد، وبأربعة مسارات في
    # متجهات المجدول بتصادم مفروض. انحراف في التطبيق وحده يجب أن يُخفق اختباره هناك
    def failing():
        r = subprocess.run(['node', os.path.join(HERE, 'test_defer.mjs'), os.path.join(tree, 'app')],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return [r.returncode != 0, sorted(l.strip().split()[1] for l in r.stdout.split('\n') if l.strip().startswith('أخفق'))]

    js_items = os.path.join(tree, 'app', 'items.mjs')
    keep = swap(js_items, 'this.defer[key(pos + j)] = cur;', 'this.defer[key(pos + j)] = pos;')
    expect('8. التطبيق يضع في الموضع الجديد بند الترتيب لا البند المؤجَّل من قبل: حالة التأخير الثاني تُخفق وحدها',
           failing(), [True, ['ب4.']])
    open(js_items, 'w', encoding='utf-8').write(keep)
    keep = swap(js_items, 'return mine.some((m) => same(m, f)); })) continue;', 'return same(fact, f); })) continue;')
    expect('9. التطبيق لا ينظر في بديل المؤجَّل: حالتا البديل تُخفقان وحدهما', failing(), [True, ['ب6.', 'ف2.']])
    open(js_items, 'w', encoding='utf-8').write(keep)
    # انحراف يغيّر ترتيب العرض: التطبيق يتخطى أقرب موضع. مسارات التصادم المفروض في متجهات المجدول تكشفه
    keep = swap(js_items, 'for (let j = 1; j <= last - pos; j += 1) {', 'for (let j = 2; j <= last - pos; j += 1) {')
    code, out = check(tree)
    expect('10. التطبيق يتخطى أقرب موضع للتأخير: مطابقة المجدول تُخفق',
           [code != 0, 'أخفق التحقق عند: مطابقة المجدول' in out, 'نجح التحقق' in out], [True, True, False])
    open(js_items, 'w', encoding='utf-8').write(keep)

    # ك1: التطبيق يستأنف نشاطًا جاريًا ببنك تغيّر بدل أن يرفض. لا متجه مطابقة يحمل هوية محتوى، فالكاشف اختبار المشهد
    js_persist = os.path.join(tree, 'app', 'persist.mjs')
    keep = swap(js_persist, 'throw new ContentChanged(bound, content, pending);', 'o.content = content;')
    r = subprocess.run(['node', os.path.join(HERE, 'test_content_identity.mjs'), os.path.join(tree, 'app')],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    expect('11. التطبيق يستأنف ببنك تغيّر بصمت بدل الرفض: حالة الرفض في اختبار هوية المحتوى تُخفق',
           [r.returncode != 0, sorted(l.strip().split()[1] for l in r.stdout.split('\n') if l.strip().startswith('أخفق'))],
           [True, ['8.']])
    open(js_persist, 'w', encoding='utf-8').write(keep)

print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
