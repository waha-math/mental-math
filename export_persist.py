#!/usr/bin/env python3
"""يصدّر متجهات مطابقة الاستعادة (app/persist.mjs) من المرجع (persist.py).

    python3 export_persist.py <ملف الخريطة>
    node app/test_persist_conformance.mjs

مسارات تعلّم عشوائية ببذرة ثابتة على محتوى الشريحة، بسقف وقت. عند حدود جلسات عشوائية، وأحيانًا في منتصف جلسة لم
تُختم، يُصنع سجل حفظ. وإن كان في المجدول نشاط محفوظ، يُجعل أحيانًا نشاطًا جاريًا: يُعرض منه عدد عشوائي من البنود،
ثم بند جارٍ بأحداث خام لم تُنهه (دعم، أو إجابة مؤكدة في بند غير تقييمي). وقبل بعض اللقطات يترك المعلم محاولة فحص
محفوظة، أو يُبطل جلسة منتهية (المراجعة 14). ويُفسد بعض السجلات عمدًا ليُرفض.
لكل سجل: نصه، وما تعيده الاستعادة في المرجع: بصمة المحرك، وحالة المجدول، والملاحظات، والسجلات، أو سبب الرفض.
"""
import copy
import hashlib
import json
import os
import random
import re
import sys

MAP = sys.argv[1]
sys.argv = [sys.argv[0], MAP]
from transition_engine import Engine, load_network, ROW  # noqa: E402
from scheduler import Scheduler, Capped  # noqa: E402
from content_source import ContentSource, load_items  # noqa: E402
from item_layer import Activity, fold_item, classify  # noqa: E402
import persist  # noqa: E402

NET = load_network(MAP)
TYPES = {}
for sid, _t, _m, _r, ev, _a in ROW.findall(open(MAP, encoding='utf-8').read()):
    if sid in NET[1] and sid not in TYPES:
        TYPES[sid] = re.findall(r'ف\d', ev)
ITEMS = load_items()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'persist_vectors.json')
UNITS = [(['1-4-1', '1-4-2'], 'young', None, [('1-4-1', ['1-3-3'])]),
         (['3-5-1', '3-5-2', '3-5-3'], 'older', '3-5-1',
          [('3-5-1', ['3-3-2', '3-2-3']), ('3-5-2', ['3-2-1', '3-3-1', '2-5-2'])])]
SUPPORT = ['hint', 'extra_model', 'someone', 'requested']


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def digest(e):
    return hashlib.sha256(canon(dict(s=e.s, d=e.derive())).encode('utf-8')).hexdigest()


class Child:
    def __init__(self, rng):
        self.rng = rng

    def __call__(self, item, want):
        a = want['activity']
        if a in ('lesson', 'practice'):
            return 'correct'
        assess = a in ('gate', 'short', 'check', 'retention')
        ans = item['answer']
        x = self.rng.random()
        tail = [] if assess else [('end',)]
        if x < 0.05:
            return [('interrupt',)], ans, assess
        if x < 0.2:
            return [('confirm', ans + 1)] + tail, ans, assess
        return [('confirm', ans)] + tail, ans, assess


def make_current(rng, sc, src):
    """نشاط محفوظ يصير جاريًا: بنود تُعرض منه، ثم بند جارٍ لم ينتهِ."""
    cands = [c for c in sc.saved if c['kind'] != 'show']
    if not cands:
        return None
    c = rng.choice(cands)
    sc.unsave(c)
    act = Activity.from_dict(c['act'])
    items = list(c['items'])
    for _ in range(rng.randint(0, 3)):
        w = act.want()
        if w is None:
            break
        it = src(act.skill, w)
        if it is None:
            break
        raw, ans, assess = sc.answer(it, w)
        act.feed(classify(fold_item(raw, ans, assess)))
        items.append(it['id'])
    journal = None
    w = act.want()
    if w is not None:
        it = src(act.skill, w)
        if it is not None:
            assess = w['activity'] in ('gate', 'short', 'check', 'retention')
            raw = [['support', rng.choice(SUPPORT)] for _ in range(rng.randint(0, 2))]
            if not assess and rng.random() < 0.5:
                raw.append(['confirm', it['answer'] + rng.choice([0, 1])])
            journal = dict(item=it['id'], want=w, answer=it['answer'], assess=assess, raw=raw)
    return dict(kind=c['kind'], skill=c['skill'], act=act.to_dict(), items=items, journal=journal)


def corrupt(rng, rec):
    r = copy.deepcopy(rec)
    k = rng.randint(0, 3)
    st = r['scheduler']['state']
    if k == 0:
        st['sessions'] += 1
    elif k == 1:
        r['schema'] = 0
    elif k == 2 and st['saved']:
        st['saved'].append(copy.deepcopy(st['saved'][0]))
    else:
        st['cur'] = 'S999'
    return r


def outcome(rec, today=None):
    """today=None: الاستعادة في اليوم نفسه، فالجلسة المفتوحة تبقى. وبيوم آخر تُختم (المرحلة 0ج)."""
    src = ContentSource(ITEMS)
    try:
        e, sc, notes = persist.restore(copy.deepcopy(rec), NET, TYPES, src, lambda i, w: 'correct',
                                       item_seconds=lambda w: 0, records=[], today=today)
    except persist.Inconsistent:
        return dict(refused=True)
    return dict(h=digest(e), state=persist.state_of(sc), notes=[list(n) for n in notes], records=sc.records,
                again=persist.snapshot(e, sc) == persist.snapshot(*persist.restore(
                    json.loads(json.dumps(persist.snapshot(e, sc))), NET, TYPES, ContentSource(ITEMS),
                    lambda i, w: 'correct', item_seconds=lambda w: 0, records=[], today=today)[:2]))


vectors, kinds = [], dict(boundary=0, open_session=0, current=0, journal=0, refused=0, abandoned=0, invalidated=0)
for seed in range(160):
    rng = random.Random(seed)
    scope, group, start, decisions = UNITS[seed % 2]
    e = Engine(NET, group=group)
    for k, (skill, bypass) in enumerate(decisions):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=skill, bypass=bypass, reason='قرار الشريحة'))
    src = ContentSource(ITEMS)
    secs = rng.choice([30, 60])
    sc = Scheduler(e, TYPES, src, Child(rng), group=group, start=start, scope=set(scope), learning=True,
                   cap=rng.choice([120, 240, 360]), item_seconds=lambda w, s=secs: s, retention=rng.random() < 0.5,
                   records=[])
    sc.search()
    sc.start_session()
    stops = sorted(rng.sample(range(1, 30), 3))
    for n in range(30):
        if sc.satisfied() and not sc.saved and not sc.parked:
            break
        if n in stops:
            mid = rng.random() < 0.3
            if mid:                                         # جلسة بدأت ولم تُختم
                sc.begin('follow')
                kinds['open_session'] += 1
            work = copy.deepcopy((e.s, sc.saved, sc.parked))
            checks = [c['act']['check_id'] for c in sc.saved + list(sc.parked.values()) if c['kind'] == 'check']
            if checks and rng.random() < 0.3:               # قرار المعلم قبل الحفظ (المراجعة 14)
                e.apply(dict(id='abandon-%d' % n, type='check_abandoned', check_id=rng.choice(checks),
                             reason='قرار المعلم'))
                kinds['abandoned'] += 1
            ended = [x for x in e.s['order'] if e.s['sessions'][x]['ended'] and not e.s['sessions'][x]['invalid']]
            if ended and rng.random() < 0.15:
                e.apply(dict(id='inval-%d' % n, type='invalidate_session', target=rng.choice(ended)))
                kinds['invalidated'] += 1
            cur = make_current(rng, sc, src) if rng.random() < 0.6 else None
            rec = json.loads(json.dumps(persist.snapshot(e, sc, cur, child='k%d' % seed)))
            e.s, sc.saved, sc.parked = work                 # الحالة الحية لا تتغير بصنع السجل
            kinds['boundary'] += 1
            kinds['current'] += cur is not None
            kinds['journal'] += bool(cur and cur.get('journal'))
            vectors.append(dict(record=rec, expect=outcome(rec)))
            if json.loads(rec['engine'])['current'] is not None:   # جلسة مفتوحة: تُستعاد أيضًا في يوم جديد فتُختم
                vectors.append(dict(record=rec, today=10 ** 6, expect=outcome(rec, 10 ** 6)))
            if rng.random() < 0.2:
                bad = corrupt(rng, rec)
                vectors.append(dict(record=bad, expect=outcome(bad)))
                kinds['refused'] += 1
            if mid:
                sc.end()
            continue
        sc.follow_learning()

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(dict(types=TYPES, vectors=vectors), f, ensure_ascii=False, separators=(',', ':'))
refused = sum(1 for v in vectors if v['expect'].get('refused'))
print('سجلات: %d (عند حد جلسة أو في منتصف جلسة لم تُختم %d، منها في جلسة مفتوحة %d، وبنشاط جارٍ %d، وببند جارٍ %d، '
      'وبعد ترك المعلم محاولة محفوظة %d، وبعد إبطال جلسة %d، ومفسدة %d). رفضها المرجع: %d' % (
          len(vectors), kinds['boundary'], kinds['open_session'], kinds['current'], kinds['journal'],
          kinds['abandoned'], kinds['invalidated'], kinds['refused'], refused))
print('الحجم: %.1f ميغابايت' % (os.path.getsize(OUT) / 1e6))
