#!/usr/bin/env python3
"""فحص تتابع البنود كما يراها الطفل أثناء التشغيل (3.5: لا تُعرض الحقيقة نفسها في بندين متتاليين).

    python3 content_sequence.py [slice-content.json]

لا يقرأ ترتيب البنود في الملف. يشغّل أنشطة طبقة البنود نفسها (item_layer) بمصدر البنود نفسه (content_source)،
ويستكشف كل فروع كل نشاط: إجابة صحيحة، وخاطئة، وصحيحة بعد دعم، وطلب مساعدة، وانقطاع (فيأتي البديل أو يُعاد
العرض)، واستبعاد البند لتغيّر الصلاحية بعد تعرّض (فيأتي بديله عند الاستئناف) أو بعد عرض فقط، ودخول النشاط عند بند يكرر
حقيقة ما عُرض قبله من نشاط آخر (فيطلب النشاط غيره). ويجمع كل زوج
(بند، البند الذي يليه) يمكن أن يراه الطفل، ومعه كيف انتهى الأول.

ما يغطيه:
- داخل كل نشاط: افتتاح الدرس (بالبندين الثابتين، وبكل زوج مرتب من أنواع أخطاء البوابة)، ودليل الفهم (الجولتان،
  وكل مجموعة أنواع ثبتت من قبل)، والبوابة وإعادتها (المتسامحة وغيرها)، والتحقق القصير، وفحص الاستقلال
  (المحاولات الثلاث)، وفحص الاحتفاظ (الجولات الثلاث)، وبنود الدرس، وبنود التدريب.
- بين الأنشطة التي يصلها المجدول في الجلسة نفسها للمهارة نفسها: آخر بند في الافتتاح ثم أول بند في الدرس، وآخر
  بند في الدرس ثم أول بند في دليل الفهم.

ما لا يضمنه المحتوى، ويعالجه التشغيل (R22-01): دخول نشاط بعد بند من نشاط آخر للمهارة نفسها في الجلسة نفسها، كالبوابة ثم
افتتاح الدرس، وإعادة التحقق ثم دليل الفهم. المجدول يحفظ آخر بند عُرض، والنشاط يطلب بندًا آخر أو بديلًا إن كرر
أول بنوده الحقيقة. دخول بنود الدرس والتدريب مسموح فيه التكرار: عرض تعليمي لا يصنع دليلًا ولا قرارًا. وفي أنشطة
التقييم يُؤخَّر البند الذي يكرر حقيقة ما عُرض قبله إلى أقرب موضع لا يجاور فيه حقيقته (Activity._defer)، ويُستكشف
هنا الدخول عند كل موضع وبعد كل تأخير سابق. ما لا موضع له يوسَم fact_just_seen: marked() تعدّ ما يبقى من ذلك بعد
تأخير. tests/test_content_sequence.py يصنّف كل انتقال فعلي ويُخفق بما لا صنف له.

ما لا يغطيه شيء: التتابع بين مهارتين مختلفتين، وبين جلستين.

المستثنى من القاعدة، بنصها:
- إعادة عرض البند نفسه: المنقطع في الافتتاح ودليل الفهم (3.5)، والموجَّه المكرر للتعليم (6.2).
- إعادة الحقيقة بعد انقطاع لم تُقبل قبله إجابة، ولم يُقدَّم فيه دعم أو جواب أو تغذية راجعة (R22-02). وصف السجل بأنه
  منقطع لا يكفي: البند الذي طُلب فيه دعم ثم انقطع نتيجته help لا interrupted، وما يليه يُفحص. وبهذا يُعاد في فحص
  الاستقلال عرض حقيقة الخانة نفسها بديلًا حين لا قيمة أخرى تحقق شرطها، بقرار الأب (3.6). والبديل نفسه يُفحص مع ما
  يليه كأي بند.
"""
import json
import os
import sys
from collections import Counter, deque

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from item_layer import (Activity, GateRun, ShortCheckRun, OpeningRun, EvidenceRun, CheckRun,  # noqa: E402
                        RetentionRun, peek_fact)
from content_source import ContentSource  # noqa: E402

TEACH = ('correct', 'wrong', 'supported', 'help', 'interrupted', 'void_exposed', 'void_shown')
ASSESS = ('correct', 'wrong', 'supported', 'help', 'interrupted')
MARKED = '|marked'                                      # زوج يكرر الحقيقة بعد تأخير، ولا علاج له: البند يوسَم
ENTRY = '*'                                             # ما قبل هذا البند من نشاط آخر
SCORE_ONLY = ('answers', 'correct', 'shown', 'reshown', 'spent')


def fact(it):
    n = it['numbers']
    if 'a' in n:
        return (n['a'], n['b'])
    v = n.get('n', n.get('e'))
    return tuple(sorted((v, 10 - v)))


def live_defer(d):
    """ما بقي فاعلًا من تأخير بنود التقييم في لقطة نشاط: مواضع المرحلة الجارية من الموضع الجاري فصاعدًا. ما قبلها
    عُرض وانتهى، ولا يقرؤه النشاط بعدها (Activity._defer و _at يسألان عن الموضع الجاري وما بعده فقط)."""
    pos, stage = d.get('slot', d.get('pos', 0)), d.get('stage', '') if d.get('_class') == 'GateRun' else ''
    out = {}
    for k, v in (d.get('defer') or {}).items():
        if k.startswith(stage) and k[len(stage):].isdigit() and int(k[len(stage):]) >= pos:
            out[k] = v
    return out


def live_alt(d):
    """ما بقي فاعلًا من بدائل الخانات وانقطاعاتها في لقطة بوابة أو فحص استقلال: ما يخص الخانة الجارية وحدها. الخانة التي
    طُلب لها بديل تبقى الجارية حتى تُحسم (البديل لا يُؤخَّر)، فمدخل خانة أخرى في alt و alt_index و cuts خانة انتهت، ولا
    يقرؤها النشاط بعدها: want و feed يسألان عن الخانة الجارية، والباقي في alt_used و total_cuts وهما في المفتاح."""
    if d.get('_class') not in ('GateRun', 'CheckRun') or d.get('done'):
        return {}
    a = Activity.from_dict(d)
    cur = a._key() if d['_class'] == 'GateRun' else a._k()
    return {f: {k: v for k, v in (d.get(f) or {}).items() if k == cur} for f in ('alt', 'alt_index', 'cuts') if f in d}


EXPOSED_ENTRY = True                                    # للمقارنة وحدها: False يعطّل فرع «الصحيح عند دخول موسوم»


def explore(act, source, outcomes, label, pairs, firsts, lasts, stuck=None):
    """كل فروع النشاط. pairs: (السابق، التالي، كيف انتهى السابق، الوصف). firsts: أول بند ممكن. lasts: (آخر بند ممكن،
    نتيجة النشاط عنده)."""
    queue, seen, facts = deque([(act.to_dict(), None, None)]), set(), {}
    while queue:
        d, prev, how = queue.popleft()
        # ما لا يغيّر البند التالي (عدّ الصحيح، والأجوبة المحفوظة، وعدّ المعروض) لا يدخل مفتاح الحالة
        # ولا ما انتهى من تأخير البنود: يبقى في المفتاح ما هو فاعل منه وحده (live_defer)
        live = live_defer(d)
        key = (json.dumps(dict({k: v for k, v in d.items() if k not in SCORE_ONLY}, defer=live, **live_alt(d)),
                          sort_keys=True, ensure_ascii=False), prev)
        if key in seen:
            continue
        seen.add(key)
        a = Activity.from_dict(d)
        while True:
            weak = False                                    # البند يُعرض موسومًا: الصحيح فيه exposed لا correct (ت2)
            w = a.want()
            if w is None:
                if prev is not None and prev != ENTRY:
                    lasts.add((prev, a.result))
                break
            item = source(a.skill, w)
            if item is None:
                a.unavailable()
                continue
            facts[item['id']] = item.get('fact')
            # أنشطة التقييم تفحص كل بند مع ما عُرض قبله منها (drive_steps): إن كرر الحقيقة أُخّر وطُلب غيره
            if (outcomes is ASSESS and prev not in (None, ENTRY, item['id']) and how != 'interrupted'
                    and facts.get(prev) is not None and facts[prev] == item.get('fact')):
                b = Activity.from_dict(a.to_dict())
                if b.repeated(item['id'], lambda q: peek_fact(source, a.skill, q)):
                    queue.append((b.to_dict(), prev, how))
                    break
                # لا موضع يُؤخَّر إليه بعد تأخير سابق: يُعرض موسومًا. وكذلك بديل جاء بعد «أداء بعد تعرض مباشر» بحقيقة
                # ما قبله (ت2): يوسَم هو أيضًا ويُستكمل ببديل تالٍ أو ينتهي النشاط بلا حكم
                if live or how == 'exposed':
                    how += MARKED
                    weak = True
            if prev is None:
                firsts.add(item['id'])
            elif prev != ENTRY:
                pairs.add((prev, item['id'], how, label))
            # دخول النشاط عند هذا البند بعد بند من نشاط آخر بالحقيقة نفسها (R22-01): النشاط يطلب غيره إن كان له علاج.
            # ما قبل البند التالي عندئذ من نشاط آخر، فلا زوج له هنا، لكن ما بعده يُستكشف
            # في أنشطة التقييم العلاج تأخير البند (defer)، ويُستكشف الدخول عند كل موضع وبعد كل تأخير سابق
            b = Activity.from_dict(a.to_dict())
            if b.repeated(item['id'], lambda q: peek_fact(source, a.skill, q)):
                queue.append((b.to_dict(), ENTRY, None))
            elif outcomes is ASSESS and not live:
                if stuck is not None:
                    stuck.add((item['id'], w['role'], label))   # لا علاج عند هذا البند: يُعرض موسومًا
                if EXPOSED_ENTRY:
                    c = Activity.from_dict(a.to_dict())     # والصحيح فيه بعد هذا الدخول exposed (ت2)
                    c.feed('exposed')
                    queue.append((c.to_dict(), item['id'], 'exposed'))
            for o in outcomes:
                if weak and o == 'correct':
                    o = 'exposed'
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


def collect(items, types, stuck=None):
    """types: أنواع دليل كل مهارة. يعيد الأزواج الممكنة أثناء التشغيل، وعدد الأنشطة المستكشفة. stuck: تُجمع فيه
    بنود أنشطة التقييم التي لا يجد التأخير لها موضعًا إن كررت حقيقة ما قبلها عند الدخول (بند، دوره، الوصف)."""
    by_id = {i['id']: i for i in items}
    pairs, explored = set(), 0
    for skill, ts in types.items():
        src = ContentSource(items)

        def run(act, outcomes, label):
            nonlocal explored
            explored += 1
            f, l = set(), set()
            explore(act, src, outcomes, label, pairs, f, l, stuck=stuck if outcomes is ASSESS else None)
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
        open_last |= {i for i, result in l if result != 'skip'}     # الدرس لا يلي افتتاحًا انتهى بتخطٍّ أو اختصار
        for t1 in ts:
            for t2 in ts:
                _f, l = run(OpeningRun(skill, ts, try_types=[t1, t2], typed=True), TEACH,
                            'افتتاح الدرس، نوعا الخطأ %s ثم %s' % (t1, t2))
                open_last |= {i for i, result in l if result != 'skip'}
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
            if src(skill, dict(RetentionRun(skill, rnd, attempt=2).want(), peek=True)) is not None:
                run(RetentionRun(skill, rnd, attempt=2), ASSESS, 'فحص الاحتفاظ، الجولة %d ببنودها البديلة' % rnd)
        if lesson:
            pairs.update((a, lesson[0], 'junction', 'آخر الافتتاح ثم أول الدرس') for a in open_last)
            pairs.update((lesson[-1], b, 'junction', 'آخر الدرس ثم أول دليل الفهم') for b in ev_first)
    return pairs, by_id, explored


def violations(pairs, by_id, marked=False):
    out = []
    for a, b, how, label in sorted(pairs):
        x, y = by_id[a], by_id[b]
        if a == b or fact(x) != fact(y):
            continue                                        # البند نفسه أُعيد عرضه، أو حقيقتان مختلفتان
        if how == 'interrupted':
            continue                                        # انقطاع بلا إجابة مقبولة ولا دعم قبله (help غير interrupted)
        if how.endswith(MARKED) != marked:
            continue
        out.append((a, b, how, label, list(fact(x))))
    return out


def marked(pairs, by_id):
    """ما بقي بلا علاج في أنشطة التقييم: بعد تأخير بند، ينقطع البند الذي قبل المؤجَّل ويأتي بديله بحقيقة المؤجَّل،
    والمؤجَّل في آخر مرحلته فلا موضع يُؤخَّر إليه. يُعرض موسومًا fact_just_seen. ليست مخالفة محتوى: تُعدّ وحدها،
    وtests/test_content_sequence.py يثبّت قائمتها."""
    return violations(pairs, by_id, marked=True)


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
    print('وخارجها، بعد تأخير بند تقييم، بلا موضع آخر، فيوسَم البند: %d زوجًا في %d فرعًا' % (
        len({(a, b) for a, b, _h, _l, _f in marked(pairs, by_id)}), len(marked(pairs, by_id))))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
