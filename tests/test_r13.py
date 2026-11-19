#!/usr/bin/env python3
"""حالة المراجعة الثالثة عشرة بلغة بايثون: نشاط محفوظ لا يستبدله نشاط آخر يبلغ السقف.

    python3 tests/test_r13.py <ملف الخريطة> [--code=مجلد]

R13-01-a: سيناريو المراجع بمحتوى الشريحة ومصدر البنود الحقيقي، ونتائجه المتوقعة في tests/r13_cases.json.
R13-01-b: الضمان لكل نوع: ستة أنشطة من ستة أنواع يقطعها السقف واحدًا بعد آخر تُحفظ كلها، وحفظ مفتاح محفوظ من قبل
خطأ صريح لا استبدال صامت. --code يشغّل الحالتين على نسخة أخرى من الكود (مثلًا الالتزام 8b6f81d).
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--code')]
code = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--code=')), os.path.dirname(HERE))
sys.path.insert(0, os.path.abspath(code))
from transition_engine import Engine, load_network, OPEN_CHECK  # noqa: E402
from scheduler import Scheduler, Capped  # noqa: E402
from content_source import ContentSource  # noqa: E402
from item_layer import GateRun, ShortCheckRun, RetentionRun, OpeningRun, EvidenceRun, CheckRun  # noqa: E402

NET = load_network(args[0])
C = json.load(open(os.path.join(HERE, 'r13_cases.json'), encoding='utf-8'))
ITEMS = json.load(open(os.path.join(HERE, '..', 'slice-content.json'), encoding='utf-8'))['items']
results = []


def saved(sc):
    """الأنشطة المحفوظة: saved في هذه النسخة، و carry الواحد قبلها."""
    if hasattr(sc, 'saved'):
        return list(sc.saved)
    return [sc.carry] if sc.carry else []


def brief(sc):
    return [[c['kind'], c['skill'], len(c['items'])] for c in saved(sc)]


class Child:
    """يجيب صحيحًا عن مهارة رأى درسها، وخطأً قبل ذلك."""
    def __init__(self):
        self.known = set()

    def __call__(self, item, want):
        a = want['activity']
        if a in ('lesson', 'practice'):
            if a == 'lesson':
                self.known.add(item['skill'])
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention', 'describe')
        ans = item['answer'] if item['skill'] in self.known else item['answer'] + 1
        return [('confirm', ans)] + ([] if assess else [('end',)]), item['answer'], assess


def case_a():
    S = C['scenario']
    e = Engine(NET, group=S['group'])
    for k, (skill, bypass) in enumerate(S['decisions']):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة'))
    src = ContentSource(ITEMS)
    timed = []                                              # (الجلسة، النشاط) لكل بند له مدة

    def seconds(w):
        s = S['seconds'].get(w['activity'], 0)
        if s:
            timed.append((sc.cur, w['activity']))
        return s
    sc = Scheduler(e, S['types'], src, Child(), group=S['group'], scope=set(S['scope']), learning=True,
                   cap=S['cap'], item_seconds=seconds, retention=True)
    sc.search()
    sc.start_session()
    for _ in range(S['follow_before']):
        sc.follow_learning()
    bad, X = [], C['expect_before_absence']
    ind = [x for x in e.valid_evidence(X['met'], 'independent')]
    got = dict(day=sc.day, met=e.derive()[X['met']], met_day=e.s['sessions'][ind[-1]['session']]['day'] if ind else None,
               due=(e.retention_next(X['met']) or [None, None])[1], check=e.s['checks'].get(X['check_id'], {}).get('state'),
               saved=brief(sc))
    want = dict(day=X['day'], met='met', met_day=X['met_day'], due=X['retention_due_day'], check=X['check_state'],
                saved=X['saved'])
    if got != want:
        return ['قبل الغياب: %r، والمتوقع %r' % (got, want)]
    first4 = C['check_items'][:4]
    if saved(sc)[0]['items'] != first4:
        return ['قبل الغياب: خانات الاستقلال المحفوظة %r، والمتوقع %r' % (saved(sc)[0]['items'], first4)]
    kept = copy.deepcopy(saved(sc)[0])

    sc.day = S['absent_to_day'] - 1                          # غياب: الجلسة التالية في يوم الاحتفاظ
    sc.follow_learning()
    X = C['expect_absence_session']
    cur = e.s['order'][-1]
    got = dict(day=e.s['sessions'][cur]['day'], saved=brief(sc), teach=e.s['sessions'][cur]['teach'],
               check=e.s['checks'][C['expect_before_absence']['check_id']]['state'])
    want = dict(day=X['day'], saved=X['saved'], teach=X['teach'], check=X['check_state'])
    if got != want:
        bad.append('جلسة يوم الاحتفاظ: %r، والمتوقع %r' % (got, want))
    chk = [c for c in saved(sc) if c['kind'] == 'check']
    if not chk or chk[0] != kept:
        bad.append('فحص الاستقلال المحفوظ تغيّر أو اختفى: خاناته وإجاباته ومعرّفاته ليست كما كانت')
    ret = [c for c in saved(sc) if c['kind'] == 'retention']
    if not ret or ret[0]['items'] != C['retention_items'][:4]:
        bad.append('تقدّم الاحتفاظ لم يُحفظ ببنوده الأربعة')
    if bad:
        return bad

    for _ in range(S['follow_after_max']):
        if not saved(sc) and not sc.parked and sc.satisfied():
            break
        sc.follow_learning()
    rr = [x for x in e.s['retention'] if x['skill'] == '1-4-1']
    if len(rr) != 1 or rr[0]['items'] != C['retention_items'] or rr[0]['correct'] != 5:
        bad.append('الاحتفاظ لم يكتمل ببنوده الخمسة: %r' % ([(x['items'], x['correct']) for x in rr],))
    cid = C['expect_before_absence']['check_id']
    starts = [x for x in e.s['log'] if x['type'] == 'check_started' and x['skill'] == '1-4-2']
    res = [x for x in e.s['log'] if x['type'] == 'independence_result' and x['skill'] == '1-4-2']
    if len(starts) != 1 or len(res) != 1 or res[0]['check_id'] != cid or res[0]['result'] != 'pass' \
            or res[0].get('items') != C['check_items']:
        bad.append('الاستقلال لم يكتمل بخاناته العشر في المحاولة الأصلية: بدء %d، نتائج %r' % (
            len(starts), [(x['check_id'], x['result'], x.get('items')) for x in res]))
    if any(c['state'] in OPEN_CHECK for c in e.s['checks'].values()) or saved(sc) or sc.parked or sc.refused:
        bad.append('بقيت محاولة معلّقة أو نشاط محفوظ أو اقتراح مرفوض')
    if len(src.served) != len(set(src.served)):
        bad.append('عُرض بند مرتين')
    per = {}
    for ses, _a in timed:
        per[ses] = per.get(ses, 0) + 1
    if max(per.values()) > C['per_session_max_timed_items']:
        bad.append('تجاوزت جلسة السقف: %r' % per)
    follow = [x for x in e.s['order'] if e.s['sessions'][x]['kind'] == 'follow']
    if max(e.s['sessions'][x]['teach'] for x in follow) > C['per_session_max_teach']:
        bad.append('جلسة استهلكت أكثر من حصة تعليمية')
    return bad


def case_b():
    """ستة أنشطة من ستة أنواع، لستّ مهارات، يقطعها السقف واحدًا بعد آخر في جلسة واحدة."""
    e = Engine(NET, group='older')
    sc = Scheduler(e, {}, lambda s, w: None, lambda i, w: 'correct', cap=1)
    sc.elapsed = 1
    acts = [('gate', GateRun('2-1-1', ['ف1', 'ف3'])), ('short', ShortCheckRun('2-1-2', ['ف1', 'ف3'])),
            ('retention', RetentionRun('2-1-3', 1)), ('opening', OpeningRun('2-2-1', ['ف1', 'ف3'])),
            ('evidence', EvidenceRun('2-2-2', ['ف1', 'ف3'])), ('check', CheckRun('2-2-3', '2-2-3/check/1', 1))]
    for kind, act in acts:
        act.shown['x'] = 1                                  # عُرض منه بند
        try:
            sc.cut(act, kind, ['%s/item' % act.skill])
        except Capped:
            pass
    want = [[k, a.skill, 1] for k, a in acts]
    bad = [] if brief(sc) == want else ['المحفوظ بعد ستة أنشطة: %r، والمتوقع %r' % (brief(sc), want)]
    again = GateRun('2-1-1', ['ف1', 'ف3'])
    again.shown['x'] = 1
    try:
        sc.cut(again, 'gate', [])
        bad.append('حُفظ مفتاح محفوظ من قبل دون خطأ')
    except Capped:
        bad.append('حفظ مفتاح محفوظ من قبل انتهى بالسقف بلا خطأ صريح')
    except Exception:                                       # noqa: BLE001
        pass
    if brief(sc) != want:
        bad.append('تغيّر المحفوظ بعد محاولة حفظ المفتاح نفسه: %r' % brief(sc))
    return bad


CASES = [('R13-01-a', True, 'سيناريو المراجع: استقلال 1-4-2 محفوظ بأربع خانات، وغياب حتى يوم احتفاظ 1-4-1، والاحتفاظ '
                            'يبلغ السقف. يبقى الاستقلال كما هو، ويُحفظ الاحتفاظ ببنوده الأربعة، ثم يكتمل الاحتفاظ بخمسة '
                            'والاستقلال بعشر في محاولته الأصلية، بلا تكرار ولا محاولة معلّقة، والسقف والحصة محترمان', case_a),
         ('R13-01-b', False, 'لكل نوع: ستة أنشطة من ستة أنواع يقطعها السقف واحدًا بعد آخر تُحفظ كلها، وحفظ مفتاح محفوظ من '
                             'قبل خطأ صريح لا يغيّر المحفوظ', case_b)]

print('=== حالة المراجعة الثالثة عشرة، بلغة بايثون، على الكود في %s' % os.path.relpath(os.path.abspath(code)))
for cid, rep, title, fn in CASES:
    try:
        bad = fn()
    except Exception as x:                                   # noqa: BLE001
        bad = ['استثناء: %r' % (x,)]
    results.append(not bad)
    print('  %s  %s %s%s' % ('نجح' if not bad else 'أخفق', cid, title, ' [أعاد المراجع إنتاجه]' if rep else ''))
    for b in bad[:3]:
        print('        ' + b)
print('النتيجة: نجح %d من %d' % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
