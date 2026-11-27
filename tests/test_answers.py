#!/usr/bin/env python3
"""أنواع الإجابة (5.3): الحالات في tests/answer_cases.json، مكتوبة من الخريطة قبل التشغيل، وتعيدها
tests/test_answers.mjs في التطبيق بالحالات نفسها.

    python3 tests/test_answers.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from item_layer import same  # noqa: E402

cases = json.load(open(os.path.join(ROOT, 'tests', 'answer_cases.json'), encoding='utf-8'))
bad = [(v, a, want, why) for v, a, want, why in cases if same(v, a) != want]
print('=== أنواع الإجابة، المرجع')
for v, a, want, why in bad:
    print('  أخفق  %s: %r مع %r، المتوقع %r' % (why, v, a, want))
print('نجحت الاختبارات كلها: %d' % len(cases) if not bad else 'النتيجة: نجح %d من %d' % (len(cases) - len(bad), len(cases)))
sys.exit(1 if bad else 0)
