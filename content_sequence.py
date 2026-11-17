#!/usr/bin/env python3
"""فحص تتابع البنود كما يراها الطفل أثناء التشغيل (3.5: لا تُعرض الحقيقة نفسها في بندين متتاليين).

    python3 content_sequence.py [slice-content.json]

لا يقرأ ترتيب البنود في الملف. يشغّل أنشطة طبقة البنود نفسها (item_layer) بمصدر البنود نفسه (content_source)،
ويستكشف كل فروع كل نشاط: إجابة صحيحة، وخاطئة، وصحيحة بعد دعم، وطلب مساعدة، وانقطاع (فيأتي البديل أو يُعاد
العرض)، واستبعاد البند لتغيّر الصلاحية بعد تعرّض (فيأتي بديله عند الاستئناف) أو بعد عرض فقط. ويجمع كل زوج
(بند، البند الذي يليه) يمكن أن يراه الطفل، ومعه كيف انتهى الأول.

ما يغطيه:
- داخل كل نشاط: افتتاح الدرس (بالبندين الثابتين، وبكل زوج مرتب من أنواع أخطاء البوابة)، ودليل الفهم (الجولتان،
  وكل مجموعة أنواع ثبتت من قبل)، والبوابة وإعادتها (المتسامحة وغيرها)، والتحقق القصير، وفحص الاستقلال
  (المحاولات الثلاث)، وفحص الاحتفاظ (الجولات الثلاث)، وبنود الدرس، وبنود التدريب.
- بين الأنشطة التي يصلها المجدول في الجلسة نفسها للمهارة نفسها: آخر بند في الافتتاح ثم أول بند في الدرس، وآخر
  بند في الدرس ثم أول بند في دليل الفهم.

ما لا يغطيه: التتابع بين أنشطة أخرى في الجلسة (فحص احتفاظ ثم بوابة مثلًا)، وبين مهارتين مختلفتين، وبين جلستين.

المستثنى من القاعدة، بنصها:
- إعادة عرض البند نفسه: المنقطع في الافتتاح ودليل الفهم (3.5)، والموجَّه المكرر للتعليم (6.2).
- البند الذي يلي بندًا منقطعًا: المنقطع لم تُقبل فيه إجابة ولم يُعطَ فيه دعم ولا تغذية راجعة، فلا يتسرّب منه غير
  رؤية السؤال (3.6). وبهذا يُعاد في فحص الاستقلال عرض حقيقة الخانة نفسها بديلًا حين لا قيمة أخرى تحقق شرطها، بقرار
  الأب. لكن البديل نفسه يُفحص مع ما يليه كأي بند.
"""
import json
import os
import sys
from collections import Counter, deque

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from item_layer import (Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun,  # noqa: E402
                        RetentionRun)
from content_source import ContentSource  # noqa: E402

TEACH = ('correct', 'wrong', 'supported', 'help', 'interrupted', 'void_exposed', 'void_shown')
ASSESS = ('correct', 'wrong', 'supported', 'help', 'interrupted')
SCORE_ONLY = ('answers', 'correct', 'shown', 'reshown')


def fact(it):
    n = it['numbers']
    if 'a' in n:
        return (n['a'], n['b'])
    v = n.get('n', n.get('e'))
    return tuple(sorted((v, 10 - v)))


def explore(act, source, outcomes, label, pairs, firsts, lasts):
    """كل فروع النشاط. pairs: (السابق، التالي، كيف انتهى السابق، الوصف). firsts: أول بند ممكن. lasts: آخر بند ممكن."""
    queue, seen = deque([(act.to_dict(), None, None)]), set()
    while queue:
        d, prev, how = queue.popleft()
        # ما لا يغيّر البند التالي (عدّ الصحيح، والأجوبة المحفوظة، وعدّ المعروض) لا يدخل مفتاح الحالة
        key = (json.dumps({k: v for k, v in d.items() if k not in SCORE_ONLY}, sort_keys=True, ensure_ascii=False), prev)
        if key in seen:
            continue
        seen.add(key)
        a = Activity.from_dict(d)
        while True:
            w = a.want()
            if w is None:
                if prev is not None:
                    lasts.add(prev)
                break
            item = source(a.skill, w)
            if item is None:
                a.unavailable()
                continue
            if prev is None:
                firsts.add(item['id'])
            else:
                pairs.add((prev, item['id'], how, label))
            for o in outcomes:
                b = Activity.from_dict(a.to_dict())
                if o == 'void_exposed':
                    b.voided(item['id'], True)
                elif o == 'void_shown':
                    b.voided(item['id'], False)
                else:
                    b.feed(o)
                queue.append((b.to_dict(), item['id'], o))
            break


def subsets(xs):
    out = [[]]
    for x in xs:
        out += [s + [x] for s in out]
    return out


def collect(items, types):
    """types: أنواع دليل كل مهارة. يعيد الأزواج الممكنة أثناء التشغيل، وعدد الأنشطة المستكشفة."""
    by_id = {i['id']: i for i in items}
    pairs, explored = set(), 0
    for skill, ts in types.items():
        src = ContentSource(items)

        def run(act, outcomes, label):
            nonlocal explored
            explored += 1
            f, l = set(), set()
            explore(act, src, outcomes, label, pairs, f, l)
            return f, l

        def shown(activity):
            ids, k = [], 0
            while True:
                it = src(skill, dict(activity=activity, pos=k))
                if it is None:
                    return ids
                ids.append(it['id'])
                k += 1

        lesson, practice = shown('lesson'), shown('practice')
        for name, ids in (('الدرس', lesson), ('التدريب', practice)):
            pairs.update((a, b, 'shown', name) for a, b in zip(ids, ids[1:]))
        open_last = set()
        _f, l = run(OpeningRun(skill, ts, typed=True), TEACH, 'افتتاح الدرس، البندان الثابتان')
        open_last |= l
        for t1 in ts:
            for t2 in ts:
                _f, l = run(OpeningRun(skill, ts, try_types=[t1, t2], typed=True), TEACH,
                            'افتتاح الدرس، نوعا الخطأ %s ثم %s' % (t1, t2))
                open_last |= l
        ev_first = set()
        for rnd in (1, 2):
            for proven in subsets(ts):
                if len(proven) == len(ts):
                    continue
                f, _l = run(EvidenceRun(skill, ts, proven=proven, round=rnd), TEACH,
                            'دليل الفهم، الجولة %d%s' % (rnd, '، ثبت من قبل: ' + ' '.join(proven) if proven else ''))
                ev_first |= f
        for attempt in (1, 2):
            for tolerant in (True, False):
                run(GateRun(skill, ts, tolerant=tolerant, attempt=attempt), ASSESS,
                    '%s%s' % ('البوابة' if attempt == 1 else 'إعادة البوابة', '' if tolerant else '، غير متسامحة'))
        run(ShortCheckRun(skill, ts), ASSESS, 'التحقق القصير')
        for k, attempt in enumerate('ABC'):
            run(CheckRun(skill, '%s/check/%d' % (skill, k + 1), 1, attempt=attempt), ASSESS,
                'فحص الاستقلال، المحاولة %s' % attempt)
        for rnd in (1, 2, 3):
            run(RetentionRun(skill, rnd), ASSESS, 'فحص الاحتفاظ، الجولة %d' % rnd)
        if lesson:
            pairs.update((a, lesson[0], 'junction', 'آخر الافتتاح ثم أول الدرس') for a in open_last)
            pairs.update((lesson[-1], b, 'junction', 'آخر الدرس ثم أول دليل الفهم') for b in ev_first)
    return pairs, by_id, explored


def violations(pairs, by_id):
    out = []
    for a, b, how, label in sorted(pairs):
        x, y = by_id[a], by_id[b]
        if a == b or fact(x) != fact(y):
            continue                                        # البند نفسه أُعيد عرضه، أو حقيقتان مختلفتان
        if how == 'interrupted':
            continue                                        # السابق منقطع: لم يتسرّب منه غير رؤية السؤال (3.6)
        out.append((a, b, how, label, list(fact(x))))
    return out


def load_types(items):
    types = {}
    for it in items:
        if it['group'] == 'evidence' and it['role'] == 'evidence' and it.get('round', 1) == 1:
            ts = types.setdefault(it['skill'], [])
            if it['evidence'] not in ts:
                ts.append(it['evidence'])
    return types


def main(argv):
    path = argv[0] if argv else os.path.join(ROOT, 'slice-content.json')
    items = json.load(open(path, encoding='utf-8'))['items']
    pairs, by_id, explored = collect(items, load_types(items))
    bad = violations(pairs, by_id)
    print('تتابع البنود أثناء التشغيل: %d نشاطًا مستكشَفًا، و%d زوجًا ممكنًا' % (explored, len(pairs)))
    per = Counter((a.split('/')[0], label.split('،')[0]) for a, _b, _h, label, _f in bad)
    for (skill, label), n in sorted(per.items()):
        print('  %s · %s: %d' % (skill, label, n))
    for a, b, how, label, f in bad[:12]:
        print('    %s ثم %s (%s) في %s: الحقيقة %s' % (a, b, how, label, f))
    print('الحقيقة نفسها في بندين متتاليين: %d' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
