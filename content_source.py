#!/usr/bin/env python3
"""مصدر البنود من بنك الشريحة (slice-content.json) لطبقة البنود: يحوّل ما تطلبه want() إلى بند بعينه.

يتحقق أن نوع دليل البند هو النوع المطلوب، فإن اختلفا فالمحتوى والطبقة لا يتفقان، ويتوقف التشغيل.
allow_same_fact لبدائل المجال الصغير التي لا عدد آخر يحقق شرط خانتها (22 بديلًا في 1-4-1 و1-4-2).
بقرار الأب في 13 نوفمبر 2026 (3.6): تُعاد الحقيقة نفسها بعد الانقطاع، ويُعلَّم البند المعروض
reshown_same_fact، فيُسجَّل «أُعيد عرضه بعد انقطاع». False يعيد النص السابق للقرار (لا بديل، فيُعلَّق الفحص
للمراجعة)، وهو للمقارنة وحدها.
"""
import json
from collections import defaultdict

LESSON_ROLES = ('lesson.watch', 'lesson.model', 'lesson.fade', 'lesson.nomodel')


def load_items(path='slice-content.json'):
    return json.load(open(path, encoding='utf-8'))['items']


class ContentSource:
    def __init__(self, items, allow_same_fact=True):
        self.by = defaultdict(list)
        for it in items:
            self.by[(it['skill'], it['group'], it['role'])].append(it)
        self.allow_same_fact = allow_same_fact
        self.served = []                                    # معرّفات البنود المعروضة بترتيبها

    def _typed(self, skill, group, role, t):
        return [i for i in self.by[(skill, group, role)] if i['evidence'] == t]

    @staticmethod
    def _at(lst, k):
        return lst[k] if k is not None and 0 <= k < len(lst) else None

    def __call__(self, skill, w):
        a = w['activity']
        if a == 'lesson':
            it = self._at([i for r in LESSON_ROLES for i in self.by[(skill, 'lesson', r)]], w['pos'])
        elif a == 'practice':
            it = self._at(self.by[(skill, 'practice', 'practice')], w['pos'])
        elif a == 'gate':
            g = 'gate' if w.get('attempt', 1) == 1 else 'regate'     # الإعادة وإعادة التحقق ببنود جديدة
            if w['alternate']:
                it = self._at(self._typed(skill, g, 'gate.alternate', w['type']), w['alt_index'])
            elif w['role'] == 'gate':
                it = self._at(self.by[(skill, g, 'gate')], w['pos'])
            else:
                it = self._at(self._typed(skill, g, 'gate.compensation', w['type']), w['pos'])
        elif a == 'short':
            it = self._at(self.by[(skill, 'short', 'short_check')], w['pos'])
        elif a == 'opening':
            if w.get('typed'):                              # 6.2: نوعا الخطأ في بوابة المهارة، بندان لكل نوع
                it = self._at(self._typed(skill, 'tryfirst', 'opening.try', w['type']), w['type_index'])
            else:
                it = self._at(self.by[(skill, 'opening', w['role'])], w['pos'])
        elif a == 'evidence':                               # كل جولة ببنودها الجديدة (3.5)
            it = self._at([i for i in self._typed(skill, 'evidence', w['role'], w['type'])
                           if i.get('round', 1) == w.get('round', 1)], w['pos'])
        elif a == 'check':
            group = 'check' + w['attempt']
            it = next((i for i in self.by[(skill, group, w['role'])] if i['slot'] == w['slot']), None)
            if it and it.get('note', '').startswith('لا قيمة أخرى'):
                # لا عدد آخر يحقق شرط الخانة: تُعاد الحقيقة نفسها بقرار الأب، أو لا بديل في النص السابق للقرار
                it = dict(it, reshown_same_fact=True) if self.allow_same_fact else None
        elif a == 'retention':                              # 3.7: خمسة بنود جديدة لكل جولة
            it = self._at([i for i in self.by[(skill, 'deferred', 'deferred_check')] if i['slot'] == w['round']],
                          w['pos'])
        else:
            raise ValueError('نشاط غير معروف: %r' % (a,))
        if it is not None:
            if 'type' in w and it['evidence'] != w['type'] and a not in ('lesson', 'practice'):
                raise AssertionError('المحتوى يخالف الطبقة: %s يُطلب %s والبند %s' % (it['id'], w['type'], it['evidence']))
            self.served.append(it['id'])
        return it
