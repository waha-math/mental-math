#!/usr/bin/env python3
"""مسار التحقق المعتمد: يُشترط نجاحه، ورمز خروجه هو الحكم.

    python3 tests/verify.py                 # كل شيء عدا Chrome
    python3 tests/verify.py --browser       # ومعه اختبارات Chrome (تحتاج npm install)
    python3 tests/verify.py --quick         # توليد المتجهات واختبارات المطابقة الأربعة وحدها
    python3 tests/verify.py --tree <مجلد>   # يتحقق من نسخة أخرى من الشجرة (يستعمله tests/test_verify.py)

ما يفعله:
1. ينسخ ملفات الشجرة إلى مجلد مؤقت نظيف. المتجهات المولَّدة (app/*_vectors.json) لا تُنسخ أبدًا، فلا يمكن أن
   يُقارَن بمتجهات قديمة. ويتأكد أنها غير موجودة في المجلد قبل التوليد.
2. يولّد المتجهات هناك بالمصدِّرات الثلاثة. إخفاق أي مصدِّر، أو غياب ملف كان عليه أن يكتبه، يوقف التحقق بفشل.
3. يشغّل الاختبارات هناك. كل خطوة يُفحص رمز خروجها.
4. لا يطبع سطر النجاح إلا إذا نجحت الخطوات كلها، ويخرج بغير صفر عند أول إخفاق مع اسم الخطوة وآخر ناتجها.

هذه غير tests/compare_vectors.py: تلك أداة عرض تبيّن فروق المتجهات عن التزام آخر، والفروق قد تكون مقصودة،
فرمز خروجها لا يثبت تطابقًا ولا يُعتمد حكمًا.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = ('conformance_vectors.json', 'item_vectors.json', 'scheduler_vectors.json', 'persist_vectors.json')
SKIP_DIRS = ('.git', 'node_modules', '__pycache__')
SAME = 'import sys; sys.exit(open(sys.argv[1], "rb").read() != open(sys.argv[2], "rb").read())'


def copy_tree(src, dst):
    """ملفات الشجرة كما هي الآن، دون المتجهات المولَّدة ودون ما لا يلزم التشغيل."""
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            if f.endswith('.pyc') or (os.path.basename(base) == 'app' and f in VECTORS):
                continue
            shutil.copy2(os.path.join(base, f), os.path.join(dst, rel, f))


def main(argv):
    tree, quick, browser = ROOT, '--quick' in argv, '--browser' in argv
    if '--tree' in argv:
        tree = os.path.abspath(argv[argv.index('--tree') + 1])
    done = []

    def fail(step, why, out=''):
        print('أخفق التحقق عند: %s' % step)
        print('  السبب: %s' % why)
        for line in out.strip().split('\n')[-6:]:
            if line.strip():
                print('  | ' + line[:300])
        print('نجح قبله %d خطوة. لا تُعتمد أي نتيجة من هذا التشغيل.' % len(done))
        return 1

    with tempfile.TemporaryDirectory() as work:
        copy_tree(tree, work)
        maps = sorted((f for f in os.listdir(work) if f.startswith('mental-math-map-v') and f.endswith('.md')),
                      key=lambda f: [int(x) for x in f.split('-v')[1].split('-')[0].split('.')])
        if not maps:
            return fail('تجهيز المجلد', 'لا ملف خريطة في %s' % tree)
        m = maps[-1]
        stale = [v for v in VECTORS if os.path.exists(os.path.join(work, 'app', v))]
        if stale:
            return fail('تجهيز المجلد', 'متجهات موجودة قبل التوليد: %s' % '، '.join(stale))

        def run(step, cmd, last=None, writes=()):
            r = subprocess.run(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if r.returncode != 0:
                return fail(step, 'رمز الخروج %d' % r.returncode, r.stdout)
            for v in writes:
                if not os.path.exists(os.path.join(work, 'app', v)):
                    return fail(step, 'لم يُكتب الملف app/%s' % v, r.stdout)
            tail = r.stdout.strip().split('\n')[-1] if r.stdout.strip() else ''
            if last and not last(tail):
                return fail(step, 'السطر الأخير ليس سطر نجاح: %s' % tail[:120], r.stdout)
            done.append(step)
            print('  نجح  %s%s' % (step, ('  ·  ' + tail[:60]) if tail and last else ''))
            return 0

        def all_passed(t):
            if t.startswith('نجحت الاختبارات كلها'):
                return True
            p = t.replace('النتيجة: نجح ', '').split(' من ')
            return t.startswith('النتيجة: نجح ') and len(p) == 2 and p[0] == p[1]

        py, node = sys.executable, 'node'
        steps = [('توليد متجهات المحرك وطبقة البنود', [py, 'export_conformance.py', m], None, VECTORS[:2]),
                 ('توليد متجهات المجدول', [py, 'export_scheduler.py', m], None, VECTORS[2:3]),
                 ('توليد متجهات الاستعادة', [py, 'export_persist.py', m], None, VECTORS[3:]),
                 ('مطابقة محرك التطبيق', [node, 'app/test_conformance.mjs'], all_passed, ()),
                 ('مطابقة طبقة البنود', [node, 'app/test_items_conformance.mjs'], all_passed, ()),
                 ('مطابقة المجدول', [node, 'app/test_scheduler_conformance.mjs'], all_passed, ()),
                 ('مطابقة الاستعادة', [node, 'app/test_persist_conformance.mjs'], all_passed, ())]
        if not quick:
            steps += [('اختبارات المحرك المرجعي', [py, 'test_transition_engine.py', m], all_passed, ()),
                      ('اختبارات طبقة البنود', [py, 'test_item_layer.py', m], all_passed, ()),
                      ('سياسة الحفظ والاستعادة', [py, 'tests/test_persist.py', m], all_passed, ()),
                      ('توليد المحتوى وفحصه', [py, 'slice_content.py', m], None, ()),
                      ('المحتوى المحفوظ هو ما يولّده المولّد', [py, '-c', SAME, os.path.join(tree, 'slice-content.json'),
                                                             'slice-content.json'], None, ()),
                      ('عامل الخدمة يطابق ملفات التطبيق', [py, 'build_sw.py', '--check'], None, ()),
                      ('تتابع البنود أثناء التشغيل', [py, 'content_sequence.py'], None, ()),
                      ('اختبار فحص التتابع', [py, 'tests/test_content_sequence.py', m], all_passed, ())]
            for t in ('r10', 'r11', 'r13', 'r14', 'r15', 'phase0', 'r22', 'defer', 'content_identity', 'record_audit',
                      'retention_help', 'session', 'extra'):
                steps.append(('حالات %s، بايثون' % t, [py, 'tests/test_%s.py' % t, m], all_passed, ()))
                steps.append(('حالات %s، JavaScript' % t, [node, 'tests/test_%s.mjs' % t], all_passed, ()))
        if browser:
            if not os.path.isdir(os.path.join(tree, 'node_modules')):
                return fail('اختبارات Chrome', 'لا node_modules في الشجرة: شغّل npm install')
            os.symlink(os.path.join(tree, 'node_modules'), os.path.join(work, 'node_modules'))
            steps.append(('اختبارات Chrome للحفظ', [node, 'tests/browser/test_store_browser.mjs'], all_passed, ()))
            steps.append(('تجربة الشريحة في Chrome', [node, 'tests/browser/test_slice_browser.mjs'], all_passed, ()))
            steps.append(('النسخة الاحتياطية والعمل دون اتصال في Chrome', [node, 'tests/browser/test_backup_browser.mjs'],
                          all_passed, ()))
        print('التحقق من %s في مجلد مؤقت نظيف (%d خطوة)' % (tree, len(steps)))
        for step in steps:
            if run(*step):
                return 1
    print('نجح التحقق: %d خطوة من %d%s' % (len(done), len(steps), '' if browser or quick else '. Chrome لم يُشغَّل'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
