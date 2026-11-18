#!/usr/bin/env python3
"""سياسة الحفظ والاستعادة (9.2): ما يُحفظ، وكيف تُستعاد منه حالة كاملة متسقة. المرجع لـ app/persist.mjs.

الحفظ في التطبيق سجل واحد لكل طفل يُكتب في معاملة واحدة (app/store.mjs). هذا الملف يحدد محتواه وقواعد قراءته،
ولا يكتب شيئًا: الكتابة الذرّية آلية المتصفح، وتُختبر فيه.

السجل:
- engine: نص المحرك المحفوظ (dump)، بنسخة ترحيله.
- scheduler: خيارات المجدول وحالته كلها: الأنشطة المحفوظة (saved)، والمركونة (parked)، والنوايا، والعدّادات، والسجل.
- records: سجل محاولات البنود (3.1): لكل بند حقوله الخمسة ونتيجته، ومنها الإجابة الأولى والدعم والمحاولات اللاحقة
  والانقطاع والبند «غير المحسوم». منه تُشتق المؤشرات الأربعة (3.2)، فيُحفظ في المعاملة نفسها (المراجعة 14).
- current: النشاط الجاري إن كان: نوعه ومهارته وحالته (to_dict)، والبنود التي عُرضت منه، و journal: البند الجاري.
- journal: البند المعروض الآن ببنده وما طلبه النشاط (want) وأحداثه الخام حتى الآن: الدعم، والإجابات المؤكدة التي لم
  تُنهِ البند. يُحفظ كل حدث منها فور وقوعه. والحدث الذي يُنهي البند لا يُحفظ في journal: يُطوى البند ويُعطى للنشاط
  ويُفرَّغ journal في الحفظ نفسه، فلا يُحسب البند مرتين.

الاستعادة:
1. المحرك من نصه، والمجدول بخياراته وحالته، وسجل محاولات البنود كما حُفظ.
1أ. تسوية ما فسّره حدث مشروع محفوظ (المراجعة 14)، بعد ضم النشاط الجاري إلى المخزن: فحص محفوظ أو مركون تركه المعلم بحدث check_abandoned في سجل
   المحرك يُسقط من المخزن، ويُكتب إسقاطه في سجل المجدول كما يكتبه المجدول الحي عند الرفض النهائي. وما لا يفسّره
   حدث في السجل لا يُسوّى، ويُرفض في فحص الاتساق.
2. البند الجاري، إن كان، لم يكتمل بالضرورة: يُختم بانقطاع ويُعلَّم «غير محسوم» (9.2)، ويُعطى للنشاط بقواعد البند
   المنقطع نفسها (3.1). الدعم الذي طُلب فيه يبقى معه، والإجابات المؤكدة قبله تبقى.
3. النشاط الجاري يُحفظ في saved كما لو قطعه السقف، فيُستأنف بأولوية 7.1 في جلسة تالية.
4. جلسة لم تُختم في المحرك تُختم بحدث session_end: التطبيق أُغلق فيها.
5. فحص اتساق قبل القبول: لا يُقبل سجل يخالف فيه المجدولُ المحرك.
"""
import copy
import json

from item_layer import Activity, fold_item, classify
from scheduler import Scheduler, exposed

SCHEMA = 3                    # 2: سجل محاولات البنود (المراجعة 14). 3: موضع الجلسة الجارية (المرحلة 0)
OPTS = ('group', 'start', 'scope', 'learning', 'tolerant', 'compat', 'content_version', 'no_short', 'try_from_gate',
        'cap', 'retention')
STATE = ('saved', 'parked', 'carried_items', 'intent', 'pending', 'proven', 'attempt', 'ev_round', 'last_items', 'n',
         'gates_run', 'searches', 'sessions', 'day', 'cur', 'log', 'refused', 'stalled', 'elapsed', 'start_at',
         'items_before', 'start_w', 'start_what', 'stage')
TERMINAL = ('end', 'interrupt')


class Inconsistent(Exception):
    """سجل يخالف فيه المجدولُ المحرك: لا يُستعاد، ويُعرض للوالد."""


def plain(x):
    return json.loads(json.dumps(x, ensure_ascii=False, default=lambda o: o.to_dict() if isinstance(o, Activity)
                                 else sorted(o) if isinstance(o, (set, frozenset)) else dict(o)))


def options(sc):
    o = dict(group=sc.group, start=sc.start, scope=None if len(sc.ids) == len(sc.e.ids) else list(sc.ids),
             learning=sc.learning, tolerant=sc.tolerant, compat=sc.compat, content_version=sc.content_version,
             no_short=sorted(sc.no_short), try_from_gate=sc.try_from_gate, cap=sc.cap, retention=sc.retention)
    return o


def state_of(sc):
    d = {k: plain(getattr(sc, k)) for k in STATE}
    d['n'] = {k: v for k, v in d['n'].items() if v}
    d['next_id'] = next_id(sc)
    if sc.last is not None:                                 # آخر بند عُرض في الجلسة المفتوحة (R22-01)
        d['last'] = plain(sc.last)
    return d


def next_id(sc):
    """رقم معرّف الحدث التالي، دون أن يتقدم العدّاد."""
    ids = sc._ids
    if hasattr(ids, 'n'):
        return ids.n
    import itertools
    v = next(ids)
    sc._ids = itertools.count(v)
    return v


def item_ends(raw, assess):
    """هل تُنهي هذه الأحداث البند؟ بند التقييم ينتهي بأول تأكيد."""
    if not raw:
        return False
    if raw[-1][0] in TERMINAL:
        return True
    return assess and any(ev[0] == 'confirm' for ev in raw)


def snapshot(engine, sc, current=None, child=''):
    """السجل الذي يُكتب في معاملة واحدة. current: dict(kind, skill, act, items, journal) أو None."""
    if current is not None and current.get('journal'):
        j = current['journal']
        if item_ends(j['raw'], j['assess']):
            raise ValueError('البند المنتهي يُطوى ويُعطى للنشاط قبل الحفظ، ولا يُحفظ في journal')
    return dict(schema=SCHEMA, child=child, engine=engine.dump(), scheduler=dict(opts=options(sc), state=state_of(sc)),
                records=None if sc.records is None else plain(sc.records), current=plain(current))


def reconcile(engine, st):
    """تسوية النشاط المحفوظ الذي أنهى صلاحيتَه حدثٌ مشروع في سجل المحرك: ترك المعلم لمحاولة الفحص."""
    notes = []
    abandoned = {ev['check_id'] for ev in engine.s['log'] if ev['type'] == 'check_abandoned'}

    def stale(c):
        if c['kind'] != 'check':
            return False
        cid = c['act']['check_id']
        ch = engine.s['checks'].get(cid)
        return ch is not None and ch['state'] == 'abandoned' and cid in abandoned

    for c in [c for c in st['saved'] if stale(c)] + [c for c in st['parked'].values() if stale(c)]:
        if c in st['saved']:
            st['saved'].remove(c)
        else:
            del st['parked'][c['skill']]
        st['log'].append([st['sessions'], 'carry_dropped:check_abandoned', c['skill']])
        notes.append(('reconciled', c['act']['check_id'], 'check_abandoned'))
    return notes


def check_consistent(engine, st):
    """ما يجب أن يتفق فيه المجدول والمحرك."""
    bad = []
    if st['sessions'] != len(engine.s['order']):
        bad.append('عدد الجلسات في المجدول %d وفي المحرك %d' % (st['sessions'], len(engine.s['order'])))
    for c in st['saved'] + list(st['parked'].values()):
        if c['kind'] == 'check':
            cid = c['act']['check_id']
            ch = engine.s['checks'].get(cid)
            if ch is None or ch['state'] not in ('pending', 'needs_restart'):
                bad.append('فحص محفوظ %s ليس معلّقًا في المحرك' % cid)
    keys = [(c['kind'], c['skill']) for c in st['saved']]
    if len(keys) != len(set(keys)):
        bad.append('مفتاح محفوظ مرتين')
    if st['cur'] is not None and engine.s['current'] != st['cur']:
        bad.append('الجلسة الجارية في المجدول %s وفي المحرك %s' % (st['cur'], engine.s['current']))
    return bad


def restore(record, net, types, source, answer, item_seconds=None, records=None, content_versions=None, today=None):
    """يعيد (المحرك، المجدول، ملاحظات). يرفع Inconsistent إن خالف المجدولُ المحرك."""
    from transition_engine import Engine
    if record.get('schema') != SCHEMA:
        raise Inconsistent('نسخة سجل غير معروفة: %r' % record.get('schema'))
    e = Engine.restore(net, record['engine'], content_versions)
    o = dict(record['scheduler']['opts'])
    o['scope'] = None if o['scope'] is None else set(o['scope'])
    # الحالة المرشحة تُبنى في نسخ مستقلة، ولا يتغير شيء مما مرّره المستدعي إلا بعد نجاح كل المراحل (R15-01)
    if record.get('records') is not None:                  # سجل محاولات البنود كما حُفظ
        local = copy.deepcopy(record['records'])
    else:
        local = None if records is None else copy.deepcopy(records)
    sc = Scheduler(e, types, source, answer, records=local, item_seconds=item_seconds, **o)
    st = copy.deepcopy(record['scheduler']['state'])
    notes = []
    cur = copy.deepcopy(record.get('current'))
    if cur:                                                 # النشاط الجاري يُضم إلى المخزن قبل التسوية والفحص
        if cur['kind'] == 'show':
            entry = dict(kind='show', skill=cur['skill'], activity=cur['activity'], pos=cur['pos'], items=[])
        else:
            act = Activity.from_dict(cur['act'])
            items = list(cur['items'])
            j = cur.get('journal')
            if j:                                           # البند الجاري: يُختم بانقطاع، «غير محسوم»
                rec = fold_item([tuple(ev) for ev in j['raw']] + [('interrupt',)], j['answer'], j['assess'])
                # إن تغيّرت صلاحية النشاط قبل الاستعادة فالبند تاريخ يُحفظ مع سبب استبعاده، ولا يُعطى للنشاط ولا يدخل
                # عدّادًا (R17-01). الحكم حكم المحرك في الجلسة المفتوحة، كما في الجلسة الحية
                v = e.may_continue(cur['kind'], e.s['current'], act.skill, getattr(act, 'check_id', None)) \
                    if hasattr(e, 'may_continue') and e.s['current'] is not None else dict(ok=True)
                more = dict(skill=act.skill, activity=act.name, role=j['want'].get('role'), item=j.get('item'),
                            unsettled=True)
                if v['ok']:
                    shown = dict(act.shown)
                    act.feed(classify(rec))
                    for k, n in act.shown.items():          # البند المختوم هنا يدخل العدّاد كما لو خُتم في الجلسة (R16-03)
                        if n > shown.get(k, 0):
                            st['n'][k] = st['n'].get(k, 0) + n - shown.get(k, 0)
                    if j.get('item'):
                        items.append(j['item'])
                    notes.append(('unsettled_item', act.skill, j.get('item'), classify(rec)))
                else:
                    act.voided(j.get('item'), exposed(j['raw']))    # التعرّض باقٍ وإن استُبعد البند (R18-01)
                    more['void'] = v['code']
                    notes.append(('void_item', act.skill, j.get('item'), v['code']))
                if sc.records is not None:
                    sc.records.append(dict(rec, **more))
                # البند خُتم هنا، فهو آخر بند عُرض في الجلسة (R23-01)، بقاعدة التعرّض نفسها في Scheduler.seen: خُتم
                # بانقطاع، فيُحتسب تعرّضًا إن أُكدت فيه إجابة أو طُلب فيه دعم. لقطة قديمة بلا حقيقة البند: لا يُعرف
                st['last'] = None if j.get('fact') is None or st['cur'] is None else dict(
                    session=st['cur'], skill=act.skill, activity=act.name, item=j.get('item'), fact=list(j['fact']),
                    counts=exposed(j['raw']))
            entry = dict(kind=cur['kind'], skill=act.skill, act=act.to_dict(), items=items)
        st['saved'].append(entry)
        notes.append(('current_saved', cur['kind'], cur['skill']))
    notes += reconcile(e, st)
    bad = check_consistent(e, st)
    if bad:
        raise Inconsistent('؛ '.join(bad))
    for k in STATE:
        setattr(sc, k, st[k])
    sc.last = st.get('last') if st['cur'] is not None else None
    from collections import Counter
    sc.n = Counter(st['n'])
    import itertools
    sc._ids = itertools.count(st['next_id'])
    # الجلسة التعليمية غير فتح التطبيق: إغلاقه لا يختمها، فتُكمَل بهويتها ووقتها وحصصها (المرحلة 0ج). تُختم هنا
    # فقط إن انتقل يوم الأسرة: today يوم الأسرة عند الفتح، وبلا قيمة تبقى الجلسة مفتوحة
    if e.s['current'] is not None and today is not None and today != e.s['sessions'][e.s['current']]['day']:
        ses = e.s['current']
        r = e.apply(dict(id='restore-end-%s' % ses, type='session_end', session=ses))
        if not r['ok']:
            raise Inconsistent('تعذر ختم الجلسة %s: %s' % (ses, r.get('code')))
        sc.cur = sc.stage = sc.last = None                  # الجلسة خُتمت: لا «آخر بند» لها بعد (R23-01)
        notes.append(('session_closed', ses))
    if records is not None and local is not None:          # نجحت الاستعادة: تُحدَّث مصفوفة المستدعي بهويتها
        records[:] = local
        sc.records = records
    return e, sc, notes
