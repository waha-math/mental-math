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
from scheduler import Void

ASSESS = ('gate', 'short', 'check', 'retention')            # بنود التقييم: تنتهي بأول تأكيد
SHOWN = ('lesson', 'practice')                              # بنود العرض: لا سجل لها
TEACH_SUPPORT = ('hint', 'extra_model', 'someone')          # الدعم المسموح في بنود التعليم


class Stepper:
    def __init__(self, engine, sc):
        self.e, self.sc = engine, sc
        self.gen = None
        self.pending = None                                 # (البند، المطلوب) أو None
        self.seq = 0
        self.raw, self.shown = [], False
        self.finished, self.broken = True, False
        self.result = None
        self.reject = None                                  # سبب رفض آخر حدث خالف العقد
        self.halt = None                                    # آخر توقف لتغيّر الصلاحية: (الجلسة، السبب، المهارة، النوع)

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

    def _void(self, answered):
        """النشاط الجاري لم يعد صالحًا (قرار وقع أثناءه): لا يُعرض البند ولا يُحتسب الحدث. المجدول يحفظ النشاط أو
        يركنه أو يُسقطه بقاعدة السبب ويختم الجلسة، والسبب في self.halt للبالغ."""
        if self.sc.live_invalid() is None:
            return False
        item, w = self.pending
        if w['activity'] in SHOWN:
            void = Void(answered)
        else:                                               # ما سُجّل قبل تغيّر الصلاحية يذهب مع التوقف، فلا يضيع (R17-01)
            void = Void(answered, shown=self.shown, raw=self.raw, answer=item['answer'], assess=self.assess())
        self._advance(void)
        self.halt = self.sc.halts[-1]
        return True

    def show(self, seq):
        """عُرض البند على الطفل. من هنا إغلاق التطبيق انقطاعٌ في البند. يعيد False إن لم يُعرض: طلب آخر، أو نشاط لم
        يعد صالحًا (R16-01)."""
        if not self._check(seq) or self._void(False):
            return False
        self.shown = True
        return True

    def allowed(self, ev):
        """عقد الأحداث (R16-02): سبب رفض الحدث، أو None إن كان مسموحًا للبند الجاري. يُفحص قبل أي تغيير.
        - بند عرض (درس، تدريب): ('end',) وحده.
        - بند تقييم (بوابة، تحقق قصير، فحص استقلال، فحص احتفاظ): ('confirm', عدد)، و('support', 'requested') وهو
          زر «أحتاج مساعدة»، ولا دعم آخر فيه (3.1).
        - بند تعليم (افتتاح، دليل فهم): ('confirm', عدد)، و('support', hint أو extra_model أو someone)، و('end',) بعد
          إجابة مؤكَّدة.
        """
        if not isinstance(ev, (list, tuple)) or not ev or not isinstance(ev[0], str):
            return 'حدث غير مفهوم'
        kind, a = ev[0], self.pending[1]['activity']
        if a in SHOWN:
            return None if tuple(ev) == ('end',) else 'بند العرض يقبل الإنهاء وحده'
        if kind == 'confirm':
            ok = len(ev) == 2 and isinstance(ev[1], int) and not isinstance(ev[1], bool)
            return None if ok else 'التأكيد يحمل عددًا صحيحًا واحدًا'
        if kind == 'support':
            if len(ev) != 2:
                return 'طلب الدعم يحمل نوعه'
            if a in ASSESS:
                return None if ev[1] == 'requested' else 'بند التقييم يقبل طلب «أحتاج مساعدة» (requested) وحده'
            return None if ev[1] in TEACH_SUPPORT else 'نوع دعم غير مسموح في بند تعليم'
        if kind == 'end' and len(ev) == 1:
            if a in ASSESS:
                return 'بند التقييم ينتهي بالتأكيد أو بطلب المساعدة'
            return None if any(x[0] == 'confirm' for x in self.raw) else 'لا إنهاء قبل إجابة مؤكَّدة'
        return 'نوع حدث غير معروف'

    def event(self, seq, ev):
        """حدث خام من الواجهة. يعيد:
        'ignored' إن لم يكن للطلب الجاري (مكرر أو متأخر)،
        'void' إن لم يُحتسب لأن النشاط لم يعد صالحًا،
        'rejected' إن خالف عقد الأحداث، والسبب في self.reject، ولا يتغير شيء،
        'open' إن بقي البند مفتوحًا،
        'next' إن أنهى البند وتم الانتقال.
        طلب «أحتاج مساعدة» في بند تقييم نهائي بنفسه (3.1): يُسجَّل الطلب ويُختم البند منقطعًا في الانتقال نفسه، بلا
        تأكيد ولا حدث إنهاء من الواجهة. وأثره على النشاط بقاعدة النشاط (3.6 و6.1 و6.2)."""
        if not self._check(seq):
            return 'ignored'
        if self._void(True):
            return 'void'
        self.reject = self.allowed(ev)
        if self.reject is not None:
            return 'rejected'
        item, w = self.pending
        if w['activity'] in SHOWN:
            self._advance('correct')
            return 'next'
        self.shown = True
        raw = self.raw + [tuple(ev)]
        if self.assess() and ev[0] == 'support':
            raw.append(('interrupt',))
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
            return None
        live = self.sc.live
        if live['kind'] == 'show':
            return dict(live, items=[])
        item, w = self.pending
        items = live['prior'] + [r['item'] for r in live['recs'] if r.get('item')]
        j = None
        if self.shown:
            j = dict(item=item.get('id'), want=w, answer=item['answer'], assess=self.assess(),
                     raw=[list(x) for x in self.raw])
            if item.get('fact') is not None:                # للاستعادة: تحدّث به آخر بند عُرض حين تختم هذا البند (R23-01)
                j['fact'] = list(item['fact'])
            if item.get('v') is not None:                   # بصمة تعريف البند المعروض (ك1)
                j['v'] = item['v']
        return dict(kind=live['kind'], skill=live['act'].skill, act=live['act'].to_dict(), items=items, journal=j)

    def snapshot(self, child=''):
        return persist.snapshot(self.e, self.sc, self.current(), child)
