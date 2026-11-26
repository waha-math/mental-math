#!/usr/bin/env python3
"""المتطلب الخارجي من الشاشة، في المرجع. الحالات والمتوقع في tests/test_external.mjs، وهنا يُطابَق المرجع بالتطبيق: تسلسل
الأنشطة وبنود بوابة الجاهزية في كل يوم هي نفسها في اللغتين، وحال المتطلب في النهاية.

    python3 tests/test_external.py <ملف الخريطة>
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from transition_engine import Engine, load_network  # noqa: E402
from scheduler import Scheduler  # noqa: E402
from content_source import ContentSource  # noqa: E402
from stepper import Stepper  # noqa: E402

NET = load_network(sys.argv[1])
PACK = json.load(open(os.path.join(ROOT, 'slice-content.json'), encoding='utf-8'))
IDENT = dict(version=PACK['version'], digest=PACK['digest'])
JS = json.loads(subprocess.run(['node', '-e', """
const m = await import('./tests/test_external.mjs');
const { PROFILES } = await import('./app/ui/config.mjs');
const out = {};
for (const r of [true, false]) { const x = m.run(r); out[String(r)] = { out: x.out, ready: x.ready, ext: x.ext }; }
console.log(JSON.stringify({ out, P: PROFILES.older1, DAY0: m.DAY0, SKILL: m.SKILL }));
""", '--input-type=module'], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
P, DAY0, SKILL = JS['P'], JS['DAY0'], JS['SKILL']


def right_of(it):
    """القيمة الصحيحة كما تكتبها الشاشة (tests/browser/answer_input.mjs rightOf)."""
    a = it['answer']
    if not isinstance(a, dict):
        return a
    t = a['t']
    if t == 'dec':
        s = str(a['n']).rjust(a['s'] + 1, '0')
        return '%s.%s' % (s[:-a['s']], s[-a['s']:]) if a['s'] else s
    return dict(frac=lambda: [a['n'], a['d']], qr=lambda: [a['q'], a['r']], dur=lambda: [a['m'] // 60, a['m'] % 60],
                money=lambda: [a['p'] // 100, a['p'] % 100], est=lambda: a['ref'])[t]()


def wrong_of(it):
    """قيمة خاطئة من النوع نفسه (wrongOf)."""
    if it.get('cards'):
        return next(c for c in it['cards'] if c != it['answer'])
    a = it['answer']
    if not isinstance(a, dict):
        return 8 if a == 9 else a + 1
    t = a['t']
    if t == 'dec':
        return right_of(it) + '1'
    return dict(frac=lambda: [a['n'] + 1, a['d']], qr=lambda: [a['q'], a['r'] + 1],
                dur=lambda: [a['m'] // 60 + 1, a['m'] % 60], money=lambda: [a['p'] // 100 + 1, a['p'] % 100],
                est=lambda: a['hi'] + 1)[t]()


def run(reads):
    e = Engine(NET, group=P['group'])
    e.apply(dict(id='d0', type='teacher_open', skill=SKILL, bypass=list(e.pre[SKILL]), reason='x'))
    sc = Scheduler(e, P['types'], ContentSource(PACK['items'], True, IDENT), None, group=P['group'], scope=set(P['scope']),
                   learning=True, cap=P['cap'], item_seconds=lambda w: 10, records=[], retention=True, content=IDENT,
                   day_cap=P.get('day_cap'))
    out, ready = [], []
    days = [DAY0, DAY0] if reads else [DAY0, DAY0, DAY0 + 1, DAY0 + 2, DAY0 + 3]
    for k, day in enumerate(days):
        if not reads and k == 4:
            e.apply(dict(id='r0', type='teacher_ready', ext='clock', reason='يقرأ الساعة في البيت'))
        sc.today = day
        st = Stepper(e, sc, lambda: day * 86400000)
        st.open(sc.g_session())
        acts, shown = [], []
        while st.pending is not None:
            item, w = st.pending
            key = '%s %s' % (w['activity'], item['skill'])
            if not acts or acts[-1] != key:
                acts.append(key)
            if w['activity'] == 'ready':
                shown.append(item['id'])
            st.show(st.seq)
            a = w['activity']
            right = reads if a == 'ready' else item['skill'] != SKILL
            evs = [('end',)] if a in ('lesson', 'practice') else \
                [('confirm', right_of(item) if right else wrong_of(item))] + \
                ([] if a in ('gate', 'short', 'check', 'retention', 'describe', 'ready') else [('end',)])
            for ev in evs:
                st.event(st.seq, ev)
        out.append(acts)
        ready.append(shown)
    return dict(out=out, ready=ready, ext=e.ext_ready('clock'))


print('=== المتطلب الخارجي، المرجع')
results = []
for reads in (True, False):
    r = run(reads)
    ok = r == JS['out'][str(reads).lower()]
    results.append(ok)
    print('  %s  %s: المرجع يطابق التطبيق' % ('نجح' if ok else 'أخفق', 'يقرأ الساعة' if reads else 'لا يقرأ'))
    if not ok:
        print('        %r\n        %r' % (r, JS['out'][str(reads).lower()]))
print('نجحت الاختبارات كلها: %d' % len(results) if all(results) else 'النتيجة: نجح %d من %d' % (results.count(True), len(results)))
sys.exit(0 if all(results) else 1)
