#!/usr/bin/env python3
"""طبقة الخطوات: تشغّل مولّد المجدول خطوة خطوة للواجهة، وتحدّد حدود الانتقال واللقطة (المرحلة 0د).

القواعد (UI-PLAN.md، القسم 2):
- الإجابة النهائية انتقال واحد: سجل البند، وتقدّم النشاط، وحدث المحرك المترتب عليه، وإزالة البند الجاري. كلها في
  خطوة واحدة للمولّد، ولا تؤخذ لقطة بين أجزائها: snapshot لا تُتاح إلا والمولّد واقف عند طلب بند، أو منتهٍ.
- حالة المولّد ليست مصدر الاستعادة. اللقطة تحمل الحالة المحفوظة والنشاط الجاري والبند الجاري، ومنها تُبنى متابعة
  جديدة: persist.restore ثم Stepper جديد على sc.g_continue() أو ما يليها.
- البند الذي لم يُعرض بعد لا journal له، فيُطلب نفسه بعد الاستعادة. والبند الذي عُرض (shown) يُختم بانقطاع عندها.
- كل طلب بند له رقم seq. الحدث الذي يحمل رقمًا غير رقم الطلب الجاري يُهمل: إجابة مكررة أو متأخرة لا تُحتسب مرتين.
- استثناء داخل الانتقال يعطّل الطبقة (broken): لا لقطة ولا خطوة بعده، والحالة المحفوظة السابقة تبقى هي المرجع.
"""
import persist

ASSESS = ('gate', 'short', 'check', 'retention')            # بنود التقييم: تنتهي بأول تأكيد
SHOWN = ('lesson', 'practice')                              # بنود العرض: لا سجل لها


class Stepper:
    def __init__(self, engine, sc):
        self.e, self.sc = engine, sc
        self.gen = None
        self.pending = None                                 # (البند، المطلوب) أو None
        self.seq = 0
        self.raw, self.shown = [], False
        self.finished, self.broken = True, False
        self.result = None

    # ------------------------------------------------------------ التشغيل
    def open(self, gen):
        """يبدأ مولّد خطوات (sc.g_continue() أو sc.g_follow_learning() ...) ويتقدم إلى أول طلب بند."""
        if not self.finished:
            raise RuntimeError('مولّد جارٍ لم ينتهِ')
        self.gen, self.finished = gen, False
        return self._advance(None, first=True)

    def _advance(self, got, first=False):
        try:
            req = next(self.gen) if first else self.gen.send(got)
        except StopIteration as stop:
            self.pending, self.finished, self.result = None, True, stop.value
        except BaseException:
            self.broken = True                              # انتقال لم يكتمل: الحالة في الذاكرة لا يُعتمد عليها
            raise
        else:
            self.pending = req
            self.seq += 1
        self.raw, self.shown = [], False
        return self.pending

    def _check(self, seq):
        if self.broken:
            raise RuntimeError('الطبقة معطّلة بعد انتقال لم يكتمل: تُعاد القراءة من المحفوظ')
        return self.pending is not None and seq == self.seq

    def assess(self):
        return self.pending[1]['activity'] in ASSESS

    def show(self, seq):
        """عُرض البند على الطفل. من هنا إغلاق التطبيق انقطاعٌ في البند."""
        if self._check(seq):
            self.shown = True
        return self.shown

    def event(self, seq, ev):
        """حدث خام من الواجهة: ('support', نوع) أو ('confirm', قيمة) أو ('end',). يعيد 'ignored' إن لم يكن للطلب الجاري،
        و'open' إن بقي البند مفتوحًا، و'next' إن أنهى البند وتم الانتقال."""
        if not self._check(seq):
            return 'ignored'
        item, w = self.pending
        if w['activity'] in SHOWN:
            if ev[0] != 'end':
                return 'ignored'
            self._advance('correct')
            return 'next'
        self.shown = True
        raw = self.raw + [tuple(ev)]
        if not persist.item_ends([list(x) for x in raw], self.assess()):
            self.raw = raw
            return 'open'
        self._advance((raw, item['answer'], self.assess()))
        return 'next'

    # ------------------------------------------------------------ اللقطة
    def current(self):
        if self.broken:
            raise RuntimeError('الطبقة معطّلة: لا لقطة')
        if self.pending is None:
            return None, []
        live = self.sc.live
        if live['kind'] == 'show':
            return dict(live, items=[]), []
        item, w = self.pending
        items = live['prior'] + [r['item'] for r in live['recs'] if r.get('item')]
        j = None
        if self.shown:
            j = dict(item=item.get('id'), want=w, answer=item['answer'], assess=self.assess(),
                     raw=[list(x) for x in self.raw])
        return dict(kind=live['kind'], skill=live['act'].skill, act=live['act'].to_dict(), items=items,
                    journal=j), live['recs']

    def snapshot(self, child=''):
        cur, recs = self.current()
        return persist.snapshot(self.e, self.sc, cur, child, extra=recs)
