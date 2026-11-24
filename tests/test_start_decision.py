#!/usr/bin/env python3
"""قرار البداية كما يقرؤه البالغ، في المرجع. الحالات والمتوقع في tests/test_start_decision.mjs، وهنا يُطابَق المرجع
بالتطبيق: تسلسل الأنشطة في الجلسات الثلاث لكل (ملف، طفل) هو نفسه في اللغتين، ويحقق القواعد الثلاث نفسها.

    python3 tests/test_start_decision.py <ملف الخريطة>
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
const m = await import('./tests/test_start_decision.mjs');
const { PROFILES } = await import('./app/ui/config.mjs');
const out = {};
for (const c of ['young', 'older1']) for (const k of ['knows', 'none']) out[c + '|' + k] = m.run(c, k).out;
console.log(JSON.stringify({ out, PROFILES, DAY0: m.DAY0 }));
""", '--input-type=module'], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
results = []


def run(child, kid):
    P = JS['PROFILES'][child]
    e = Engine(NET, group=P['group'])
    for k, d in enumerate(P['decisions']):
        e.apply(dict(id='d%d' % k, type='teacher_open', skill=d['skill'], bypass=d['bypass'], reason='x'))
    sc = Scheduler(e, P['types'], ContentSource(PACK['items'], True, IDENT), None, group=P['group'], scope=set(P['scope']),
                   learning=True, cap=P['cap'], item_seconds=lambda w: 10, records=[], retention=True, content=IDENT,
                   day_cap=P.get('day_cap'))
    dec = {d['skill'] for d in P['decisions']}
    out = []
    for day in (JS['DAY0'], JS['DAY0'], JS['DAY0'] + 1):
        sc.today = day
        st = Stepper(e, sc, lambda: day * 86400000)
        st.open(sc.g_session())
        acts = []
        while st.pending is not None:
            item, w = st.pending
            key = '%s %s' % (w['activity'], item['skill'])
            if not acts or acts[-1] != key:
                acts.append(key)
            st.show(st.seq)
            a = w['activity']
            right = kid == 'knows' and item['skill'] not in dec
            evs = [('end',)] if a in ('lesson', 'practice') else \
                [('confirm', item['answer'] if right else item['answer'] + 1)] + \
                ([] if a in ('gate', 'short', 'check', 'retention', 'describe') else [('end',)])
            for ev in evs:
                st.event(st.seq, ev)
        out.append(acts)
    anc = set().union(*(e.anc[d] for d in dec))
    return out, anc, P['decisions'][0]['skill'], dec


print('=== قرار البداية، المرجع')
for child in ('young', 'older1'):
    for kid in ('knows', 'none'):
        out, anc, first, dec = run(child, kid)
        bad = []
        if out[0] != ['gate ' + first]:
            bad.append('الأولى: %r' % out[0])
        if not (out[1] and out[1][0].startswith('opening ') and out[1][0].split()[1] in dec
                and out[1][1] == 'lesson ' + out[1][0].split()[1]):
            bad.append('الثانية: %r' % out[1])
        below = [k for s in out for k in s if k.split()[0] in ('gate', 'short') and k.split()[1] in anc]
        if below:
            bad.append('تحت القرار: %r' % below)
        if out != JS['out'][child + '|' + kid]:
            bad.append('يخالف التطبيق: %r / %r' % (out, JS['out'][child + '|' + kid]))
        results.append(not bad)
        print('  %s  %s، %s' % ('نجح' if not bad else 'أخفق', child, kid))
        for b in bad:
            print('        ' + b)
print('نجحت الاختبارات كلها: %d' % len(results) if all(results) else 'النتيجة: نجح %d من %d' % (results.count(True), len(results)))
sys.exit(0 if all(results) else 1)
