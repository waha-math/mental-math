#!/usr/bin/env python3
"""مصدر البنود من بنك الشريحة (slice-content.json) لطبقة البنود: يحوّل ما تطلبه want() إلى بند بعينه.

يتحقق أن نوع دليل البند هو النوع المطلوب، فإن اختلفا فالمحتوى والطبقة لا يتفقان، ويتوقف التشغيل.
allow_same_fact لبدائل المجال الصغير التي لا عدد آخر يحقق شرط خانتها (22 بديلًا في 1-4-1 و1-4-2).
بقرار الأب في 13 نوفمبر 2026 (3.6): تُعاد الحقيقة نفسها بعد الانقطاع، ويُعلَّم البند المعروض
reshown_same_fact، فيُسجَّل «أُعيد عرضه بعد انقطاع». False يعيد النص السابق للقرار (لا بديل، فيُعلَّق الفحص
للمراجعة)، وهو للمقارنة وحدها.
"""
import hashlib
import json
from collections import defaultdict

LESSON_ROLES = ('lesson.watch', 'lesson.model', 'lesson.fade', 'lesson.nomodel')


def load_items(path='slice-content.json'):
    return json.load(open(path, encoding='utf-8'))['items']


# ---------------------------------------------------------------- هوية المحتوى (ك1 في مراجعة 04e0168)
# معرّف البند لا يكفي لمعرفة ما رآه الطفل: أعداد البند وجوابه قد تتغير والمعرّف باقٍ. لكل بند بصمة تعريفه (v)، ولكل
# حزمة رقم إصدار لا يُعاد استعماله وبصمة (digest). المحاولة تُربط بالحزمة التي بدأت بها (persist)، ولا يُستأنف نشاط
# جارٍ ببنك آخر بصمت.
PACK_PARTS = ('texts', 'ui', 'cards', 'describe', 'items')   # ما يراه الطفل ويُحكم به: يدخل بصمة الحزمة


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def item_digest(item):
    """بصمة تعريف البند: كل حقوله عدا البصمة نفسها. أي تغيير في أعداده أو جوابه أو دوره أو نوعه يغيّرها."""
    return hashlib.sha256(canon({k: v for k, v in item.items() if k != 'v'}).encode('utf-8')).hexdigest()[:16]


def pack_digest(pack):
    """بصمة الحزمة: نصوصها وبنودها كما تُحفظ. لا يدخلها رقم الإصدار ولا البصمة."""
    return hashlib.sha256(canon({k: pack[k] for k in PACK_PARTS if k in pack}).encode('utf-8')).hexdigest()


def identity(pack):
    """هوية الحزمة التي تُربط بها المحاولة."""
    return dict(version=pack['version'], digest=pack['digest'])


def next_version(ledger, digest):
    """رقم إصدار حزمة بصمتها digest، وفق سجل الإصدارات ledger (قائمة مداخل فيها version و digest، بترتيبها). بصمة آخر
    مدخل: رقمه. بصمة جديدة: الرقم التالي، ولا يُعاد رقم سبق. بصمة سبقت وليست الأخيرة: خطأ، فالرجوع إلى محتوى قديم
    إصدار جديد يُكتب صراحةً لا استعادة لرقم."""
    if ledger and ledger[-1]['digest'] == digest:
        return ledger[-1]['version']
    if any(x['digest'] == digest for x in ledger):
        raise ValueError('بصمة محتوى سبقت في سجل الإصدارات وليست الأخيرة: %s' % digest[:12])
    return (ledger[-1]['version'] if ledger else 0) + 1


def load_pack(path='slice-content.json'):
    """الحزمة كما حُفظت، بعد التحقق من أن بصماتها بصمات محتواها. تُرفض حزمة عُدّل بند فيها ولم تتغير هويتها."""
    pack = json.load(open(path, encoding='utf-8'))
    bad = [i['id'] for i in pack['items'] if i.get('v') != item_digest(i)]
    if bad:
        raise ValueError('بنود لا توافق بصمتُها تعريفَها: %s' % '، '.join(bad[:5]))
    if pack.get('digest') != pack_digest(pack):
        raise ValueError('بصمة الحزمة لا توافق محتواها')
    return pack


class ContentSource:
    def __init__(self, items, allow_same_fact=True, content=None):
        self.content = content                              # هوية الحزمة التي منها البنود: dict(version, digest)، إن عُرفت
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
            # البديل (R18-01) برقمه بين بدائل النوع في الجولة، لا بموضع البند الذي يحل محله
            it = self._at([i for i in self._typed(skill, 'evidence', w['role'], w['type'])
                           if i.get('round', 1) == w.get('round', 1)],
                          w['alternate'] - 1 if w.get('alternate') else w['pos'])
        elif a == 'check':
            group = 'check' + w['attempt']
            it = next((i for i in self.by[(skill, group, w['role'])] if i['slot'] == w['slot']), None)
            if it and it.get('note', '').startswith('لا قيمة أخرى'):
                # لا عدد آخر يحقق شرط الخانة: تُعاد الحقيقة نفسها بقرار الأب، أو لا بديل في النص السابق للقرار
                it = dict(it, reshown_same_fact=True) if self.allow_same_fact else None
        elif a == 'retention':                              # 3.7: خمسة بنود جديدة لكل جولة
            it = self._at([i for i in self.by[(skill, 'deferred', w.get('role', 'deferred_check'))]
                           if i['slot'] == w['round'] and i.get('set', 0) == w.get('alternate', 0)], w['pos'])
        else:
            raise ValueError('نشاط غير معروف: %r' % (a,))
        if it is not None:
            if 'type' in w and it['evidence'] != w['type'] and a not in ('lesson', 'practice'):
                raise AssertionError('المحتوى يخالف الطبقة: %s يُطلب %s والبند %s' % (it['id'], w['type'], it['evidence']))
            if not w.get('peek'):                           # سؤال عن بند دون عرضه (تأخير بند التقييم)
                self.served.append(it['id'])
        return it
