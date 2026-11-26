"""المراحل 4 إلى 8 في مولّد الوحدات (units.py): سجلّ للأداءات ومواصفات المهارات.

كل أداء يُسجَّل مرة بـ perf(): نصّه وجوابه ورسمه (render)، وجوابه محسوبًا ثانيةً بلا render (truth)، وحقيقته (fact)، ومجاله
لكل مهارة (domain)، ووصف وسيلته (resource)، وبطاقاته إن كان حكمًا. units.py يقرأ هذا السجلّ في مواضعه: PERFS و domain و
fact و truth و check. والرسم يُتحقق منه بـ MODEL_OK، من أعداد البند وجوابه.

أنواع الجواب (5.3): عدد صحيح (ج1)، أو قاموس بنوعه t كما في item_layer.same.
"""
from math import gcd

LRI, PDI, MINUS, BOX, TIMES, DIV = '⁦', '⁩', '−', '▢', '×', '÷'

PERFS, TRUTHS, FACTS, DOMAINS, RESOURCE, CARD_PERFS, CARD_FN = {}, {}, {}, {}, {}, {}, {}
MODEL_OK = {}
SKILLS = {}
ANSWER_MAX = 20000                                          # 8-3-3: ⁦ 104 × 107 = 11128 ⁩


def eq(s):
    return LRI + ' ' + s + ' ' + PDI


def perf(name, render, truth, domain, resource, fact=None, cards=None):
    """domain: دالة (مهارة) تعيد قائمة أعداد البنود، أو قائمة واحدة لكل المهارات."""
    assert name not in PERFS, name
    PERFS[name], TRUTHS[name], RESOURCE[name] = render, truth, resource
    DOMAINS[name] = domain if callable(domain) else (lambda skill, d=domain: d)
    FACTS[name] = fact or (lambda n: [n[k] for k in sorted(n) if not isinstance(n[k], (dict, list))])
    if callable(cards):                                     # بطاقات البند من أعداده: (معرّفات، نص كل بطاقة) (ج8)
        CARD_PERFS[name], CARD_FN[name] = 'labels', cards
    elif cards:
        CARD_PERFS[name] = cards


def S(types, perf_map, slots):
    return dict(types=types, perf=perf_map, slots=slots)


def plain(text, ans):
    return eq(text), eq(text), ans, None


def judge(text, ok):
    return 'هل هذا صحيح؟ ' + eq(text), 'Is this true? ' + eq(text), 'yes' if ok else 'no', None


def cnt(n, one, two, few, many, fem=False):
    """المعدود في العربية: 1 مفرد، 2 مثنى، وما ينتهي بـ 3 إلى 10 جمع، وبـ 11 إلى 99 مفرد منصوب، وغيره مفرد."""
    r = n % 100
    if n == 1:
        return '%s %s' % (one, 'واحدة' if fem else 'واحد')
    if n == 2:
        return two
    if 3 <= r <= 10:
        return '%d %s' % (n, few)
    if 11 <= r <= 99:
        return '%d %s' % (n, many)
    return '%d %s' % (n, one)


def qr(q, r):
    return dict(t='qr', q=q, r=r)


# ---------------------------------------------------------------- المرحلة 4: حقائق الضرب والقسمة
# الرسم: arr مصفوفة نقاط rows × cols؛ shade أعمدة ملوّنة (نصف جدول 10)، cross أعمدة مشطوبة (جدول 9)، split خط بعد
# عمود (المربع عند 5)، hide تُخفى النقاط ويبقى الإطار (عامل ناقص). share: أطباق وكومة تمر لم تُوزَّع
def ask_arr(m):
    return dict(kind='arr', **m)


MODEL_OK['arr'] = lambda m, n, ans: (
    m['rows'] >= 1 and m['cols'] >= 1 and ans == m['rows'] * (m.get('shade') or m['cols'] - m.get('cross', 0)))
MODEL_OK['share'] = lambda m, n, ans: (
    m['total'] >= 0 and m['plates'] >= 1 and (ans == m['total'] // m['plates'] if isinstance(ans, int)
                                               else (ans['q'], ans['r']) == divmod(m['total'], m['plates'])))

TABLE = {'4-2-1': 2, '4-2-2': 10, '4-2-3': 5, '4-3-1': 4, '4-3-2': 8, '4-4-1': 3, '4-4-2': 6, '4-5-1': 9,
         '4-5-2': 11, '4-6-2': 7}
# القصص: «عدد ...» يصح مع أي عدد (المعدود في العربية يتغير بين 3-10 و11-99)
CTX_MUL = [('عدد العلب {a}، وفي كل علبة عدد من الأقلام هو {b}. كم عدد الأقلام كلها؟',
            'There are {a} boxes with {b} pencils in each. How many pencils are there altogether?'),
           ('عدد الصفوف في الحديقة {a}، وفي كل صف عدد من الأشجار هو {b}. كم عدد الأشجار كلها؟',
            'A garden has {a} rows with {b} trees in each row. How many trees are there?'),
           ('عدد الأطباق {a}، وعلى كل طبق عدد من حبات التمر هو {b}. كم حبة تمر على الأطباق كلها؟',
            'There are {a} plates with {b} dates on each. How many dates are there altogether?')]
CTX_DIV = [('عدد حبات التمر {n}، نوزعها بالتساوي على أطفال عددهم {k}. كم يأخذ كل طفل؟',
            '{n} dates are shared equally among {k} children. How many does each child get?'),
           ('عدد الأقلام {n}، نضعها في علب بالتساوي، وعدد العلب {k}. كم في كل علبة؟',
            '{n} pencils are put equally into {k} boxes. How many are in each box?')]
CTX_DIVR = [('عدد حبات التمر {n}، نوزعها بالتساوي على أطفال عددهم {k}. كم يأخذ كل طفل، وكم يبقى؟',
             '{n} dates are shared equally among {k} children. How many does each child get, and how many are left?'),
            ('عدد الأقلام {n}، نضعها في علب بالتساوي، وعدد العلب {k}. كم في كل علبة، وكم يبقى خارجها؟',
             '{n} pencils are put equally into {k} boxes. How many go in each box, and how many are left over?')]


def ctx(table, nums, ans, **kw):
    ar, en = table[nums['c'] % len(table)]
    return ar.format(**kw), en.format(**kw), ans, None


def fact_mul(n):                                            # a × b والتبديل حقيقة واحدة (3.5)
    return ['×', min(n['a'], n['b']), max(n['a'], n['b'])]


# 4-1-1: مجموعات متساوية ومصفوفات (المجاميع حتى 25)
D411 = [dict(a=a, b=b) for a in range(2, 6) for b in range(2, 6)]
perf('arr_count', lambda n: ('%s كم نقطة في المصفوفة؟' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                             '%s How many dots are in the array?' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                             n['a'] * n['b'], ask_arr(dict(rows=n['a'], cols=n['b']))),
     lambda n: n['a'] * n['b'], D411, 'مصفوفة نقاط', fact_mul)
perf('groups_sum', lambda n: plain('%d %s %d = %s = %s' % (n['a'], TIMES, n['b'], ' + '.join([str(n['b'])] * n['a']), BOX),
                                   n['a'] * n['b']),
     lambda n: n['a'] * n['b'], D411, 'بلا نموذج: الجمع المتكرر مكتوب', fact_mul)
perf('ctx_mul', lambda n: ctx(CTX_MUL, n, n['a'] * n['b'], a=n['a'], b=n['b']),
     lambda n: n['a'] * n['b'], lambda skill: [dict(d, c=c) for d in (D411 if skill == '4-1-1' else D481) for c in range(3)],
     'صورة الموقف، والنص منطوق', fact_mul)
# 4-1-2: التبديل
D412 = [dict(a=a, b=b) for a in range(2, 10) for b in range(2, 10) if a != b and a * b <= 50]
perf('comm_model', lambda n: ('%s %s' % (eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], n['a'] * n['b'])),
                                         eq('%d %s %d = %s' % (n['b'], TIMES, n['a'], BOX))),
                              '%s %s' % (eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], n['a'] * n['b'])),
                                         eq('%d %s %d = %s' % (n['b'], TIMES, n['a'], BOX))),
                              n['a'] * n['b'], ask_arr(dict(rows=n['b'], cols=n['a']))),
     lambda n: n['a'] * n['b'], D412, 'تدوير المصفوفة', fact_mul)
perf('comm', lambda n: plain('%d %s %d = %d %s %s' % (n['a'], TIMES, n['b'], n['b'], TIMES, BOX), n['a']),
     lambda n: n['a'], D412, 'بلا نموذج', fact_mul)
perf('judge_comm', lambda n: judge('%d %s %d = %d %s %d' % (n['a'], TIMES, n['b'], n['b'], TIMES, n['a'] + n['w']),
                                   n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D412 for w in (0, 1)], 'بلا نموذج', fact_mul,
     cards='yesno')
# 4-1-3: الضرب في 0 وفي 1
D413 = [dict(a=a, z=z, s=s) for a in range(2, 11) for z in (0, 1) for s in (0, 1)]


def zo_text(n):
    return ('%d %s %d' % (n['z'], TIMES, n['a'])) if n['s'] == 0 else ('%d %s %d' % (n['a'], TIMES, n['z']))


perf('zero_one', lambda n: plain('%s = %s' % (zo_text(n), BOX), n['a'] * n['z']),
     lambda n: n['a'] * n['z'], D413, 'بلا نموذج', lambda n: ['×', n['z'], n['a'], n['s']])
perf('judge_zero', lambda n: judge('%s = %d' % (zo_text(n), n['a'] * n['z'] if n['w'] == 0 else (n['a'] if n['z'] == 0 else 1)),
                                   n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D413 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['×', n['z'], n['a'], n['s']], cards='yesno')


# الجداول: حقائق الضرب وحقائق قسمتها عائلةً واحدة. op: 0 ضرب والجدول ثانيًا، 1 ضرب والجدول أولًا، 2 قسمة
def table_dom(skill):
    t = TABLE[skill]
    ks = range(1, 10) if t == 11 else range(2, 11)
    return [dict(t=t, k=k, op=op) for k in ks for op in (0, 1, 2) if not (t == 11 and op == 2)]


def table_text(n):
    t, k, op = n['t'], n['k'], n['op']
    if op == 2:
        return '%d %s %d = %s' % (t * k, DIV, t, BOX), k
    return ('%d %s %d = %s' % (k, TIMES, t, BOX) if op == 0 else '%d %s %d = %s' % (t, TIMES, k, BOX)), t * k


def table_fact(n):                                          # الضرب والقسمة في العائلة حقيقة واحدة
    return ['×', n['t'], n['k']]


perf('table', lambda n: plain(*table_text(n)), lambda n: n['k'] if n['op'] == 2 else n['t'] * n['k'], table_dom,
     'بلا نموذج', table_fact)
perf('arr_rows', lambda n: ('%s كم نقطة في المصفوفة؟' % eq('%d %s %d' % (n['k'], TIMES, n['t'])),
                            '%s How many dots are in the array?' % eq('%d %s %d' % (n['k'], TIMES, n['t'])),
                            n['t'] * n['k'], ask_arr(dict(rows=n['t'], cols=n['k']))),
     lambda n: n['t'] * n['k'], lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'مصفوفة من صفّين', table_fact)
perf('tens_k', lambda n: ('%s كم العدد؟ (كل حزمة عشرة)' % eq('%d %s 10' % (n['k'], TIMES)),
                          '%s What is the number? (each bundle is ten)' % eq('%d %s 10' % (n['k'], TIMES)),
                          10 * n['k'], dict(kind='tens', tens=n['k'], ones=0)),
     lambda n: 10 * n['k'], lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'حزم العشرات', table_fact)
perf('half10_model', lambda n: ('%s في كل صف عشر نقاط، والملوّن نصفها. كم نقطة ملوّنة؟' % eq('%d %s 5' % (n['k'], TIMES)),
                                '%s Each row has ten dots and half are coloured. How many dots are coloured?'
                                % eq('%d %s 5' % (n['k'], TIMES)),
                                5 * n['k'], ask_arr(dict(rows=n['k'], cols=10, shade=5))),
     lambda n: 5 * n['k'], lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'مصفوفة تُقصّ نصفين', table_fact)
perf('half10_step', lambda n: plain('%d %s 5 = %s %s 2' % (n['k'], TIMES, BOX, DIV), 10 * n['k']),
     lambda n: 10 * n['k'], lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'بلا نموذج', table_fact)
# خطوة الجدول من جدول يعرفه: 4 = 2 + 2، و8 = 4 + 4، و3 = 2 + 1، و6 = 3 + 3، و9 = 10 − 1، و11 = 10 + 1
STEP = {4: (2, '+', 2), 8: (4, '+', 4), 3: (2, '+', 1), 6: (3, '+', 3), 9: (10, MINUS, 1), 11: (10, '+', 1)}


def step_text(n):
    t, k = n['t'], n['k']
    a, op, b = STEP[t]
    return '%d %s %d = %d %s %s' % (k, TIMES, t, a * k, op, BOX), b * k


perf('table_step', lambda n: plain(*step_text(n)), lambda n: STEP[n['t']][2] * n['k'],
     lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'بلا نموذج', table_fact)
perf('nine_model', lambda n: ('%s في كل صف عشر نقاط، شُطب منها واحدة. كم نقطة بقيت؟' % eq('%d %s 9' % (n['k'], TIMES)),
                              '%s Each row has ten dots and one is crossed out. How many dots are left?'
                              % eq('%d %s 9' % (n['k'], TIMES)),
                              9 * n['k'], ask_arr(dict(rows=n['k'], cols=10, cross=1))),
     lambda n: 9 * n['k'], lambda skill: [d for d in table_dom(skill) if d['op'] == 0], 'مصفوفة يُشطب منها عمود',
     table_fact)


# 4-6: المربعات، وجدول 7 من جار المربع، والحقائق الأصعب
D461 = [dict(k=k, s=0) for k in range(2, 11)]
perf('square_model', lambda n: ('%s كم نقطة في المربع؟' % eq('%d %s %d' % (n['k'], TIMES, n['k'])),
                                '%s How many dots are in the square?' % eq('%d %s %d' % (n['k'], TIMES, n['k'])),
                                n['k'] ** 2, ask_arr(dict(rows=n['k'], cols=n['k'], split=5 if n['k'] > 5 else 0))),
     lambda n: n['k'] ** 2, D461, 'مصفوفة مربعة مقسومة عند 5', lambda n: ['×', n['k'], n['k'], 1])
perf('square', lambda n: plain('%d %s %d = %s' % (n['k'], TIMES, n['k'], BOX), n['k'] ** 2),
     lambda n: n['k'] ** 2, D461, 'بلا نموذج', lambda n: ['×', n['k'], n['k'], 2])


def seven_step(n):
    k = n['k']
    if k < 7:                                               # ⁦ 6 × 7 = 6 × 6 + 6 ⁩
        return '%d %s 7 = %d + %s' % (k, TIMES, k * k, BOX), k * (7 - k)
    return '%d %s 7 = %d + %s' % (k, TIMES, 49, BOX), 7 * (k - 7)   # ⁦ 8 × 7 = 49 + 7 ⁩


perf('seven_step', lambda n: plain(*seven_step(n)), lambda n: n['k'] * (7 - n['k']) if n['k'] < 7 else 7 * (n['k'] - 7),
     [dict(t=7, k=k, op=0) for k in (4, 5, 6, 8, 9, 10)], 'بلا نموذج', table_fact)
HARD = [(6, 7), (6, 8), (6, 9), (7, 7), (7, 8), (7, 9), (8, 8), (8, 9), (9, 9)]
D463 = [dict(a=a, b=b, s=s) for a, b in HARD for s in (0, 1) if not (a == b and s)]
perf('hard', lambda n: plain('%d %s %d = %s' % (((n['a'], TIMES, n['b']) if n['s'] == 0 else (n['b'], TIMES, n['a'])) + (BOX,)),
                             n['a'] * n['b']),
     lambda n: n['a'] * n['b'], D463, 'بلا نموذج', fact_mul)
perf('judge_hard', lambda n: judge('%d %s %d = %d' % (n['a'], TIMES, n['b'], n['a'] * n['b'] + n['w']), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(a=a, b=b, w=w) for a, b in HARD for w in (0, -2, 2, 6)],
     'بلا نموذج', fact_mul, cards='yesno')


# 4-7: القسمة عاملًا ناقصًا، والقسمة مع باقٍ
D471 = [dict(k=k, q=q) for k in range(2, 10) for q in range(2, 10)]
perf('div_share', lambda n: ('%s نوزع النقاط على الأطباق بالتساوي. كم في كل طبق؟' % eq('%d %s %d' % (n['k'] * n['q'], DIV, n['k'])),
                             '%s Share the dots equally on the plates. How many on each plate?'
                             % eq('%d %s %d' % (n['k'] * n['q'], DIV, n['k'])),
                             n['q'], dict(kind='share', total=n['k'] * n['q'], plates=n['k'])),
     lambda n: n['q'], D471, 'توزيع تمر على أطباق', lambda n: ['×', min(n['k'], n['q']), max(n['k'], n['q'])])
perf('div_step', lambda n: plain('%s %s %d = %d' % (BOX, TIMES, n['k'], n['k'] * n['q']), n['q']),
     lambda n: n['q'], D471, 'بلا نموذج: القسمة عامل ناقص', lambda n: ['×', min(n['k'], n['q']), max(n['k'], n['q'])])
perf('ctx_div', lambda n: ctx(CTX_DIV, n, n['q'], n=n['k'] * n['q'], k=n['k']),
     lambda n: n['q'], lambda skill: [dict(d, c=c) for d in D471 for c in range(2)], 'صورة الموقف، والنص منطوق',
     lambda n: ['×', min(n['k'], n['q']), max(n['k'], n['q'])])
D472 = [dict(k=k, q=q, r=r) for k in range(3, 10) for q in range(2, 10) for r in range(1, k)]


def divr_text(n):
    return '%d %s %d' % (n['k'] * n['q'] + n['r'], DIV, n['k'])


perf('divr_share', lambda n: ('%s نوزع على الأطباق بالتساوي. كم في كل طبق، وكم يبقى؟' % eq(divr_text(n)),
                              '%s Share equally on the plates. How many on each plate, and how many are left?' % eq(divr_text(n)),
                              qr(n['q'], n['r']), dict(kind='share', total=n['k'] * n['q'] + n['r'], plates=n['k'])),
     lambda n: qr(n['q'], n['r']), D472, 'توزيع تمر مع ما يبقى', lambda n: ['÷', n['k'] * n['q'] + n['r'], n['k']])
perf('divr', lambda n: ('%s الخارج؟ والباقي؟' % eq('%s = %s' % (divr_text(n), BOX)),
                        '%s Quotient? Remainder?' % eq('%s = %s' % (divr_text(n), BOX)), qr(n['q'], n['r']), None),
     lambda n: qr(n['q'], n['r']), D472, 'بلا نموذج', lambda n: ['÷', n['k'] * n['q'] + n['r'], n['k']])
perf('ctx_divr', lambda n: ctx(CTX_DIVR, n, qr(n['q'], n['r']), n=n['k'] * n['q'] + n['r'], k=n['k']),
     lambda n: qr(n['q'], n['r']), lambda skill: [dict(d, c=c) for d in D472 for c in range(2)],
     'صورة الموقف، والنص منطوق', lambda n: ['÷', n['k'] * n['q'] + n['r'], n['k']])

# 4-8: مختلطة، والاشتقاق، وترتيب العمليات
D481 = [dict(a=a, b=b) for a in range(2, 11) for b in range(2, 11)]
perf('mixed_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']),
     lambda n: n['a'] * n['b'], D481, 'بلا نموذج', fact_mul)
perf('mixed_div', lambda n: plain('%d %s %d = %s' % (n['a'] * n['b'], DIV, n['b'], BOX), n['a']),
     lambda n: n['a'], D481, 'بلا نموذج', fact_mul)
perf('ctx_div2', lambda n: ctx(CTX_DIV, n, n['a'], n=n['a'] * n['b'], k=n['b']),
     lambda n: n['a'], [dict(d, c=c) for d in D481 for c in range(2)], 'صورة الموقف، والنص منطوق', fact_mul)
D483 = [dict(a=a, b=b) for a in range(11, 16) for b in range(2, 10)]
perf('derive_step', lambda n: plain('%d %s %d = %d + %s' % (n['a'], TIMES, n['b'], 10 * n['b'], BOX), (n['a'] - 10) * n['b']),
     lambda n: (n['a'] - 10) * n['b'], D483, 'مصفوفة مقسومة: عشرة وما بعدها', fact_mul)
perf('derive', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']),
     lambda n: n['a'] * n['b'], D483, 'بلا نموذج', fact_mul)
D484 = [dict(a=a, b=b, c=c, f=f) for a in range(2, 10) for b in range(2, 10) for c in range(2, 10) for f in range(3)
        if a <= b and a * b + c <= 100 and a * b - c > 0]


def order_text(n):
    a, b, c, f = n['a'], n['b'], n['c'], n['f']
    return ['%d %s %d + %d' % (a, TIMES, b, c), '%d + %d %s %d' % (c, a, TIMES, b), '%d %s %d %s %d' % (a, TIMES, b, MINUS, c)][f]


def order_val(n):
    return n['a'] * n['b'] + (n['c'] if n['f'] < 2 else -n['c'])


perf('order', lambda n: plain('%s = %s' % (order_text(n), BOX), order_val(n)), order_val, D484,
     'أقواس ملوّنة حول الضرب (في الدرس)', lambda n: ['o', n['a'], n['b'], n['c'], n['f']])


def order_wrong(n):                                         # الخطأ الشائع: من اليسار إلى اليمين
    a, b, c, f = n['a'], n['b'], n['c'], n['f']
    return [(a * b + c), (c + a) * b, a * b - c][f]


perf('judge_order', lambda n: judge('%s = %d' % (order_text(n), order_val(n) if n['w'] == 0 else order_wrong(n)),
                                    n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D484 if d['f'] == 1 for w in (0, 1)],
     'بلا نموذج', lambda n: ['o', n['a'], n['b'], n['c'], n['f']], cards='yesno')

SKILLS.update({
    '4-1-1': S(['ف1', 'ف3', 'ف4'], {'ف1': 'arr_count', 'ف3': 'groups_sum', 'ف4': 'ctx_mul', 'solve': 'groups_sum'},
               [(5, 'الناتج حتى 12', lambda n: n['a'] * n['b'] <= 12), (5, 'الناتج فوق 12', lambda n: n['a'] * n['b'] > 12)]),
    '4-1-2': S(['ف1', 'ف5'], {'ف1': 'comm_model', 'ف5': 'judge_comm', 'solve': 'comm'},
               [(5, 'الأول أصغر', lambda n: n['a'] < n['b']), (5, 'الأول أكبر', lambda n: n['a'] > n['b'])]),
    '4-1-3': S(['ف3', 'ف5'], {'ف3': 'zero_one', 'ف5': 'judge_zero', 'solve': 'zero_one'},
               [(5, 'في صفر', lambda n: n['z'] == 0), (5, 'في واحد', lambda n: n['z'] == 1)]),
})
for sk, first in (('4-2-1', 'arr_rows'), ('4-2-2', 'tens_k')):
    SKILLS[sk] = S(['ف1', 'ف3'], {'ف1': first, 'ف3': 'table', 'solve': 'table'},
                   [(3, 'ضرب، المضروب حتى 5', lambda n: n['op'] < 2 and n['k'] <= 5),
                    (3, 'ضرب، المضروب فوق 5', lambda n: n['op'] < 2 and n['k'] > 5),
                    (4, 'قسمة في العائلة نفسها', lambda n: n['op'] == 2)])
# خانتا الضرب بزوجية المضروب لا بحجمه: نصف العشرة يعطي عشرات تامة للزوجي (5 × 8 = 40) وخمسة في الآحاد للفردي (5 × 7 = 35).
# والقسمة بحجم المضروب كانت تترك للخانة أربع حقائق، تجاورها كلها عند الدخول فلا يُؤخَّر البند ولا يُبدَّل
SKILLS['4-2-3'] = S(['ف1', 'ف2', 'ف3'], {'ف1': 'half10_model', 'ف2': 'half10_step', 'ف3': 'table', 'solve': 'table'},
                    [(3, 'ضرب، المضروب زوجي', lambda n: n['op'] < 2 and n['k'] % 2 == 0),
                     (3, 'ضرب، المضروب فردي', lambda n: n['op'] < 2 and n['k'] % 2 == 1),
                     (4, 'قسمة في العائلة نفسها', lambda n: n['op'] == 2)])
for sk in ('4-3-1', '4-3-2', '4-4-1', '4-4-2'):
    SKILLS[sk] = S(['ف2', 'ف3'], {'ف2': 'table_step', 'ف3': 'table', 'solve': 'table'},
                   [(3, 'ضرب، المضروب حتى 5', lambda n: n['op'] < 2 and n['k'] <= 5),
                    (4, 'ضرب، المضروب فوق 5', lambda n: n['op'] < 2 and n['k'] > 5),
                    (3, 'قسمة في العائلة نفسها', lambda n: n['op'] == 2)])
SKILLS['4-5-2'] = S(['ف2', 'ف3'], {'ف2': 'table_step', 'ف3': 'table', 'solve': 'table'},   # 11 في رقم واحد: بلا قسمة
                    [(3, 'العدد أولًا، حتى 5', lambda n: n['op'] == 0 and n['k'] <= 5),
                     (4, 'العدد أولًا، فوق 5', lambda n: n['op'] == 0 and n['k'] > 5),
                     (3, '11 أولًا', lambda n: n['op'] == 1)])
SKILLS['4-5-1'] = S(['ف1', 'ف2', 'ف3'], {'ف1': 'nine_model', 'ف2': 'table_step', 'ف3': 'table', 'solve': 'table'},
                    [(3, 'ضرب، المضروب حتى 5', lambda n: n['op'] < 2 and n['k'] <= 5),
                     (4, 'ضرب، المضروب فوق 5', lambda n: n['op'] < 2 and n['k'] > 5),
                     (3, 'قسمة في العائلة نفسها', lambda n: n['op'] == 2)])
SKILLS.update({
    '4-6-1': S(['ف1', 'ف3'], {'ف1': 'square_model', 'ف3': 'square', 'solve': 'square'},
               [(4, 'مربع حتى 5', lambda n: n['k'] <= 5), (6, 'مربع فوق 5', lambda n: n['k'] > 5)]),
    '4-6-2': S(['ف2', 'ف3'], {'ف2': 'seven_step', 'ف3': 'table', 'solve': 'table'},
               [(3, 'ضرب، المضروب حتى 5', lambda n: n['op'] < 2 and n['k'] <= 5),
                (4, 'ضرب، المضروب فوق 5', lambda n: n['op'] < 2 and n['k'] > 5),
                (3, 'قسمة في العائلة نفسها', lambda n: n['op'] == 2)]),
    '4-6-3': S(['ف3', 'ف5'], {'ف3': 'hard', 'ف5': 'judge_hard', 'solve': 'hard'},
               [(4, 'فيها 6 أو 7 أصغرَ العاملين', lambda n: min(n['a'], n['b']) <= 7),
                (6, 'كلاهما 8 أو 9، أو 7 في 9', lambda n: min(n['a'], n['b']) >= 7)]),
    '4-7-1': S(['ف1', 'ف2', 'ف4'], {'ف1': 'div_share', 'ف2': 'div_step', 'ف4': 'ctx_div', 'solve': 'div_step'},
               [(5, 'القاسم حتى 5', lambda n: n['k'] <= 5), (5, 'القاسم فوق 5', lambda n: n['k'] > 5)]),
    '4-7-2': S(['ف1', 'ف3', 'ف4'], {'ف1': 'divr_share', 'ف3': 'divr', 'ف4': 'ctx_divr', 'solve': 'divr'},
               [(5, 'القاسم حتى 5', lambda n: n['k'] <= 5), (5, 'القاسم فوق 5', lambda n: n['k'] > 5)]),
    '4-8-1': S(['ف3', 'ف4'], {'ف3': 'mixed_mul', 'ف4': 'ctx_mul', 'solve': 'mixed_mul'},
               [(3, 'فيها 2 أو 5 أو 10', lambda n: {2, 5, 10} & {n['a'], n['b']}),
                (7, 'بلا 2 ولا 5 ولا 10', lambda n: not {2, 5, 10} & {n['a'], n['b']})]),
    '4-8-2': S(['ف3', 'ف4'], {'ف3': 'mixed_div', 'ف4': 'ctx_div2', 'solve': 'mixed_div'},
               [(3, 'القاسم 2 أو 5 أو 10', lambda n: n['b'] in (2, 5, 10)),
                (7, 'قاسم آخر', lambda n: n['b'] not in (2, 5, 10))]),
    '4-8-3': S(['ف2', 'ف3'], {'ف2': 'derive_step', 'ف3': 'derive', 'solve': 'derive'},
               [(5, 'من 11 إلى 12', lambda n: n['a'] <= 12), (5, 'من 13 إلى 15', lambda n: n['a'] > 12)]),
    '4-8-4': S(['ف3', 'ف5'], {'ف3': 'order', 'ف5': 'judge_order', 'solve': 'order'},
               [(4, 'الضرب أولًا في الكتابة', lambda n: n['f'] == 0), (3, 'الضرب ثانيًا في الكتابة', lambda n: n['f'] == 1),
                (3, 'ضرب ثم طرح', lambda n: n['f'] == 2)]),
})


# ---------------------------------------------------------------- المرحلة 5: الأعداد الكبيرة والتقدير
# الرسم: places جدول المنازل بأرقامه (shift منزلق: كم منزلة يتحرك العدد)، area مستطيل بضلعيه، jumps و round كما في
# المرحلة 3 بأعداد أكبر
def digits4(v):
    return [v // 1000, v // 100 % 10, v // 10 % 10, v % 10]


MODEL_OK['places'] = lambda m, n, ans: (
    sum(d * 10 ** (len(m['digits']) - 1 - k) for k, d in enumerate(m['digits'])) == m['value']
    and ('point' not in m or (m['point'] == 1 and m['shift'] == n['op'] * n['z'])))
MODEL_OK['area'] = lambda m, n, ans: m['a'] * m['b'] == ans


def est(exact, ref, pct):
    """ج7: المقبول ما بعد عن الناتج الدقيق pct في المئة على الأكثر، ومعه التقدير بالتقريب ref."""
    d = max(exact * pct // 100, 10)
    lo, hi = min(exact - d, ref), max(exact + d, ref)
    return dict(t='est', lo=max(lo, 0), hi=hi, ref=ref)


def rnd(v, u):                                              # إلى أقرب u، وما في المنتصف إلى الأكبر (قرار 25 نوفمبر)
    return (v + u // 2) // u * u


D511 = [dict(v=v, k=k) for v in range(1001, 10000, 37) for k in range(4) if digits4(v)[k]]
PLACE = ['آلاف', 'مئات', 'عشرات', 'آحاد']


def decomp_text(n):
    v, k = n['v'], n['k']
    parts = [d * 10 ** (3 - j) for j, d in enumerate(digits4(v)) if d]
    shown = [str(p) if p != digits4(v)[k] * 10 ** (3 - k) else BOX for p in parts]
    return '%d = %s' % (v, ' + '.join(shown)), digits4(v)[k] * 10 ** (3 - k)


perf('places_read', lambda n: ('ما العدد في جدول المنازل؟', 'What number is in the place value table?', n['v'],
                               dict(kind='places', digits=digits4(n['v']), value=n['v'])),
     lambda n: n['v'], [d for d in D511 if d['k'] == 0], 'جدول المنازل', lambda n: ['p', n['v']])
perf('decomp4', lambda n: plain(*decomp_text(n)), lambda n: digits4(n['v'])[n['k']] * 10 ** (3 - n['k']), D511,
     'بلا نموذج', lambda n: ['p', n['v'], n['k']])
D512 = [dict(a=a, z=z) for a in range(2, 100) for z in (1, 2) if a % 10 or a < 10]
D512 += [dict(a=a, z=1) for a in range(101, 1000, 7) if a % 10]
perf('shift_model', lambda n: ('%s كم يصير العدد بعد أن ينتقل في جدول المنازل؟' % eq('%d %s %d' % (n['a'], TIMES, 10 ** n['z'])),
                               '%s What does the number become after it moves in the place value table?'
                               % eq('%d %s %d' % (n['a'], TIMES, 10 ** n['z'])),
                               n['a'] * 10 ** n['z'], dict(kind='places', digits=[int(c) for c in str(n['a'])], value=n['a'],
                                                           shift=n['z'])),
     lambda n: n['a'] * 10 ** n['z'], D512, 'منزلق المنازل', lambda n: ['s', n['a'], n['z']])
perf('shift_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, 10 ** n['z'], BOX), n['a'] * 10 ** n['z']),
     lambda n: n['a'] * 10 ** n['z'], D512, 'بلا نموذج', lambda n: ['s', n['a'], n['z']])
perf('shift_div_model', lambda n: ('%s كم يصير العدد بعد أن ينتقل في جدول المنازل؟' % eq('%d %s %d' % (n['a'] * 10 ** n['z'], DIV, 10 ** n['z'])),
                                   '%s What does the number become after it moves in the place value table?'
                                   % eq('%d %s %d' % (n['a'] * 10 ** n['z'], DIV, 10 ** n['z'])),
                                   n['a'], dict(kind='places', digits=[int(c) for c in str(n['a'] * 10 ** n['z'])],
                                                value=n['a'] * 10 ** n['z'], shift=-n['z'])),
     lambda n: n['a'], D512, 'منزلق المنازل', lambda n: ['s', n['a'], -n['z']])
perf('shift_div', lambda n: plain('%d %s %d = %s' % (n['a'] * 10 ** n['z'], DIV, 10 ** n['z'], BOX), n['a']),
     lambda n: n['a'], D512, 'بلا نموذج', lambda n: ['s', n['a'], -n['z']])
D521 = [dict(a=a, b=b) for a in range(112, 900, 13) for b in range(105, 900, 17) if a + b < 1000 and a % 10 and b % 10]


def left_step(n):
    a, b = n['a'], n['b']
    h, t = a // 100 * 100 + b // 100 * 100, a // 10 % 10 * 10 + b // 10 % 10 * 10
    return '%d + %d = %d + %d + %s' % (a, b, h, t, BOX), a % 10 + b % 10


perf('left_step', lambda n: plain(*left_step(n)), lambda n: n['a'] % 10 + n['b'] % 10, D521, 'مجموع جارٍ من اليسار',
     lambda n: ['+', min(n['a'], n['b']), max(n['a'], n['b'])])
perf('add3', lambda n: plain('%d + %d = %s' % (n['a'], n['b'], BOX), n['a'] + n['b']), lambda n: n['a'] + n['b'], D521,
     'بلا نموذج', lambda n: ['+', min(n['a'], n['b']), max(n['a'], n['b'])])
D522 = [dict(a=a, b=h - d, d=d, op=op) for a in range(301, 990, 11) for h in range(200, 800, 100) for d in (1, 2)
        for op in (1, -1) if (op < 0 and a - (h - d) > 0) or (op > 0 and a + h - d < 1000)]


def adj_text(n):
    a, b, d, op = n['a'], n['b'], n['d'], n['op']
    if op > 0:
        return '%d + %d = %d + %d %s %s' % (a, b, a, b + d, MINUS, BOX), d
    return '%d %s %d = %d %s %d + %s' % (a, MINUS, b, a, MINUS, b + d, BOX), d


perf('adj3_step', lambda n: plain(*adj_text(n)), lambda n: n['d'], D522, 'بلا نموذج', lambda n: ['a', n['a'], n['b'], n['op']])
perf('adj3', lambda n: plain('%d %s %d = %s' % (n['a'], '+' if n['op'] > 0 else MINUS, n['b'], BOX), n['a'] + n['op'] * n['b']),
     lambda n: n['a'] + n['op'] * n['b'], D522, 'بلا نموذج', lambda n: ['a', n['a'], n['b'], n['op']])
perf('judge_adj3', lambda n: judge('%d %s %d = %d %s %d %s %d' % (n['a'], MINUS, n['b'], n['a'], MINUS, n['b'] + n['d'],
                                                                 '+' if n['w'] == 0 else MINUS, n['d']), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D522 if d['op'] < 0 for w in (0, 1)],
     'بلا نموذج', lambda n: ['a', n['a'], n['b'], n['op']], cards='yesno')
D523 = [dict(a=a, b=b) for a in range(301, 1000, 7) for b in range(112, 900, 11)
        if a > b and a // 100 > b // 100 and b % 100 and a % 100 < b % 100]


def comp_jumps(a, b):
    up = (b // 100 + 1) * 100
    return up - b, up, a - up


perf('comp3_line', lambda n: ('%s من %d إلى %d قفزتان. كم مجموعهما؟' % (eq('%d %s %d' % (n['a'], MINUS, n['b'])), n['b'], n['a']),
                              '%s From %d to %d in two jumps. What do they add up to?' % (eq('%d %s %d' % (n['a'], MINUS, n['b'])), n['b'], n['a']),
                              n['a'] - n['b'],
                              dict(kind='jumps', line='up', start=n['b'], jumps=[comp_jumps(n['a'], n['b'])[0], comp_jumps(n['a'], n['b'])[2]],
                                   stations=[comp_jumps(n['a'], n['b'])[1], n['a']], hide=None, ten=False)),
     lambda n: n['a'] - n['b'], D523, 'خط الأعداد', lambda n: ['-', n['a'], n['b']])
perf('comp3_step', lambda n: ('من %d إلى %d قفزة %s' % (n['b'], comp_jumps(n['a'], n['b'])[1], BOX),
                              'From %d to %d is a jump of %s' % (n['b'], comp_jumps(n['a'], n['b'])[1], BOX),
                              comp_jumps(n['a'], n['b'])[0], None),
     lambda n: comp_jumps(n['a'], n['b'])[0], D523, 'بلا نموذج', lambda n: ['-', n['a'], n['b']])
perf('sub3', lambda n: plain('%d %s %d = %s' % (n['a'], MINUS, n['b'], BOX), n['a'] - n['b']), lambda n: n['a'] - n['b'],
     D523, 'بلا نموذج', lambda n: ['-', n['a'], n['b']])
CTX_SUB3 = [('في المكتبة {a} كتابًا، استعار الأطفال منها {b}. كم بقي؟',
             'The library has {a} books. The children borrowed {b}. How many are left?'),
            ('عدد المقاعد في المسرح {a}، جلس الناس في {b} منها. كم مقعدًا بقي فارغًا؟',
             'A theatre has {a} seats and people sat in {b}. How many seats are empty?')]
perf('ctx_sub3', lambda n: ctx(CTX_SUB3, n, n['a'] - n['b'], a=n['a'], b=n['b']), lambda n: n['a'] - n['b'],
     [dict(d, c=c) for d in D523 for c in range(2) if d['a'] % 100 >= 11 and (d['a'] - d['b']) % 100 >= 11], 'صورة الموقف، والنص منطوق',
     lambda n: ['-', n['a'], n['b']])
D531 = [dict(a=a) for a in range(102, 1000) if a % 100 and a % 10 and a % 7 == 0]
perf('thousand_line', lambda n: ('من %d إلى 1000 قفزتان. كم مجموعهما؟' % n['a'], 'From %d to 1000 in two jumps. What do they add up to?' % n['a'],
                                 1000 - n['a'], dict(kind='jumps', line='up', start=n['a'],
                                                     jumps=[(n['a'] // 100 + 1) * 100 - n['a'], 1000 - (n['a'] // 100 + 1) * 100],
                                                     stations=[(n['a'] // 100 + 1) * 100, 1000], hide=None, ten=False)),
     lambda n: 1000 - n['a'], D531, 'خط أعداد حتى 1000', lambda n: ['k', n['a']])
perf('thousand_step', lambda n: ('من %d إلى %d قفزة %d، ومن %d إلى 1000 قفزة %s' % (
    n['a'], (n['a'] // 100 + 1) * 100, (n['a'] // 100 + 1) * 100 - n['a'], (n['a'] // 100 + 1) * 100, BOX),
    'From %d to %d is a jump of %d, and from %d to 1000 is a jump of %s' % (
    n['a'], (n['a'] // 100 + 1) * 100, (n['a'] // 100 + 1) * 100 - n['a'], (n['a'] // 100 + 1) * 100, BOX),
    1000 - (n['a'] // 100 + 1) * 100, None),
     lambda n: 1000 - (n['a'] // 100 + 1) * 100, D531, 'بلا نموذج', lambda n: ['k', n['a']])
perf('thousand', lambda n: plain('%d + %s = 1000' % (n['a'], BOX), 1000 - n['a']), lambda n: 1000 - n['a'], D531,
     'بلا نموذج', lambda n: ['k', n['a']])
D532 = [dict(a=a) for a in range(102, 1000) if a % 10 and a % 3 == 0] + [dict(a=a) for a in range(110, 1000, 10) if a % 100]
perf('short_comp_step', lambda n: ('في %s الرقم الأيمن غير الصفري %d يُكمَّل إلى 10: %s' % (
    eq('1000 %s %d' % (MINUS, n['a'])), [int(c) for c in str(n['a']) if c != '0'][-1], BOX),
    'In %s the rightmost nonzero digit %d is completed to 10: %s' % (
    eq('1000 %s %d' % (MINUS, n['a'])), [int(c) for c in str(n['a']) if c != '0'][-1], BOX),
    10 - [int(c) for c in str(n['a']) if c != '0'][-1], None),
     lambda n: 10 - [int(c) for c in str(n['a']) if c != '0'][-1], D532, 'جدول المنازل', lambda n: ['k', n['a']])
perf('short_comp', lambda n: plain('1000 %s %d = %s' % (MINUS, n['a'], BOX), 1000 - n['a']), lambda n: 1000 - n['a'],
     D532, 'بلا نموذج', lambda n: ['k', n['a']])
perf('judge_short_comp', lambda n: judge('1000 %s %d = %d' % (MINUS, n['a'], 1000 - n['a'] if n['w'] == 0 else 1000 - n['a'] + 10),
                                         n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(a=d['a'], w=w) for d in D532 if d['a'] % 10 == 0 for w in (0, 1)],
     'بلا نموذج', lambda n: ['k', n['a']], cards='yesno')
CTX_CHANGE3 = [('ثمن الدراجة {a} جنيهًا، ودفعنا {m} جنيه. كم الباقي بالجنيه؟',
                'The bike costs {a} pounds and we pay {m} pounds. How much change, in pounds?'),
               ('اشترينا أغراضًا بـ{a} جنيهًا، ومعنا ورقة {m} جنيه. كم يعيد البائع؟',
                'We buy things for {a} pounds and pay with a note of {m} pounds. How much does the seller give back?')]
D533 = [dict(a=a, m=m, c=c) for m in (200, 500) for a in range(111, m, 7) if a % 100 >= 11 for c in range(2)]
perf('change3', lambda n: ctx(CTX_CHANGE3, n, n['m'] - n['a'], a=n['a'], m=n['m']), lambda n: n['m'] - n['a'], D533,
     'نقود اللعب، والنص منطوق', lambda n: ['c', n['a'], n['m']])
D541 = [dict(a=a, b=b, x=x, y=y) for a in range(2, 10) for b in range(2, 10) for x in (10, 100) for y in (10, 100)
        if a * b * x * y <= 9000 and not (x == 100 and y == 100)]
perf('area_mul', lambda n: ('%s ما مساحة المستطيل؟' % eq('%d %s %d' % (n['a'] * n['x'], TIMES, n['b'] * n['y'])),
                            '%s What is the area of the rectangle?' % eq('%d %s %d' % (n['a'] * n['x'], TIMES, n['b'] * n['y'])),
                            n['a'] * n['x'] * n['b'] * n['y'], dict(kind='area', a=n['a'] * n['x'], b=n['b'] * n['y'])),
     lambda n: n['a'] * n['b'] * n['x'] * n['y'], D541, 'نموذج المساحة', lambda n: ['m', n['a'], n['b'], n['x'] * n['y']])
perf('mul_tens', lambda n: plain('%d %s %d = %s' % (n['a'] * n['x'], TIMES, n['b'] * n['y'], BOX), n['a'] * n['b'] * n['x'] * n['y']),
     lambda n: n['a'] * n['b'] * n['x'] * n['y'], D541, 'بلا نموذج', lambda n: ['m', n['a'], n['b'], n['x'] * n['y']])
perf('judge_mul_tens', lambda n: judge('%d %s %d = %d' % (n['a'] * n['x'], TIMES, n['b'] * n['y'],
                                                        n['a'] * n['b'] * n['x'] * n['y'] // (10 if n['w'] else 1)), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D541 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['m', n['a'], n['b'], n['x'] * n['y']], cards='yesno')
D542 = [dict(q=q, b=b, x=x) for q in range(2, 10) for b in range(2, 10) for x in (10, 100) if q * b * x <= 9000]
perf('div_tens_step', lambda n: plain('%d %s %d = %d %s %s' % (n['q'] * n['b'] * n['x'] * 10, DIV, n['b'] * 10,
                                                              n['q'] * n['b'] * n['x'], DIV, BOX), n['b']),
     lambda n: n['b'], [d for d in D542 if d['q'] * d['b'] * d['x'] * 10 <= 9000], 'نموذج المساحة بضلع مجهول',
     lambda n: ['d', n['q'], n['b'], n['x']])
perf('div_tens', lambda n: plain('%d %s %d = %s' % (n['q'] * n['b'] * n['x'], DIV, n['b'], BOX), n['q'] * n['x']),
     lambda n: n['q'] * n['x'], D542, 'بلا نموذج', lambda n: ['d', n['q'], n['b'], n['x']])
D551 = [dict(v=v, u=u) for v in range(103, 9999, 41) for u in (10, 100, 1000) if v % u and (u < 1000 or v > 1000)]
UNIT = {10: ('عشرة', 'ten'), 100: ('مئة', 'hundred'), 1000: ('ألف', 'thousand')}
perf('round_big_line', lambda n: ('إلى أي %s نقرّب %d؟' % (UNIT[n['u']][0], n['v']), 'Round %d to the nearest %s.' % (n['v'], UNIT[n['u']][1]),
                                  rnd(n['v'], n['u']), dict(kind='round', lo=n['v'] // n['u'] * n['u'], hi=n['v'] // n['u'] * n['u'] + n['u'],
                                                            v=n['v'])),
     lambda n: rnd(n['v'], n['u']), D551, 'خط الأعداد', lambda n: ['r', n['v'], n['u']])
perf('round_big', lambda n: ('%d مقرَّبًا إلى أقرب %s = %s' % (n['v'], UNIT[n['u']][0], BOX),
                             '%d rounded to the nearest %s = %s' % (n['v'], UNIT[n['u']][1], BOX), rnd(n['v'], n['u']), None),
     lambda n: rnd(n['v'], n['u']), D551, 'بلا نموذج', lambda n: ['r', n['v'], n['u']])
D552 = [dict(a=a, b=b, op=op) for a in range(151, 999, 29) for b in range(121, 999, 31) for op in (1, -1)
        if (op > 0 and a + b < 2000) or (op < 0 and a - b > 99)]


def est_as(n):
    a, b, op = n['a'], n['b'], n['op']
    return est(a + op * b, rnd(a, 100) + op * rnd(b, 100), 10)


perf('est_add', lambda n: ('قدّر: %s' % eq('%d %s %d %s %s' % (n['a'], '+' if n['op'] > 0 else MINUS, n['b'], '≈', BOX)),
                           'Estimate: %s' % eq('%d %s %d %s %s' % (n['a'], '+' if n['op'] > 0 else MINUS, n['b'], '≈', BOX)),
                           est_as(n), None),
     est_as, D552, 'بلا نموذج', lambda n: ['e', n['a'], n['b'], n['op']])
CTX_EST = [('ثمن حقيبة {a} جنيهًا، وثمن حذاء {b} جنيهًا. كم جنيهًا ندفع تقريبًا؟',
            'A bag costs {a} pounds and shoes cost {b} pounds. About how much do we pay?'),
           ('قطع السائق في الصباح {a} كيلومترًا، وفي المساء {b}. كم كيلومترًا قطع تقريبًا؟',
            'A driver went {a} km in the morning and {b} km in the evening. About how far did he go?')]
perf('ctx_est', lambda n: ctx(CTX_EST, n, est_as(dict(n, op=1)), a=n['a'], b=n['b']), lambda n: est_as(dict(n, op=1)),
     [dict(d, c=c) for d in D552 if d['op'] > 0 and d['a'] % 100 >= 11 and d['b'] % 100 >= 11 for c in range(2)], 'صورة الموقف، والنص منطوق',
     lambda n: ['e', n['a'], n['b'], 1])
D553 = [dict(a=a, b=b) for a in range(12, 99) for b in range(12, 99) if a % 10 and b % 10 and a <= b and (a + b) % 5 == 0]


def est_mul(n):
    return est(n['a'] * n['b'], rnd(n['a'], 10) * rnd(n['b'], 10), 15)


perf('est_mul', lambda n: ('قدّر: %s' % eq('%d %s %d ≈ %s' % (n['a'], TIMES, n['b'], BOX)),
                           'Estimate: %s' % eq('%d %s %d ≈ %s' % (n['a'], TIMES, n['b'], BOX)), est_mul(n), None),
     est_mul, D553, 'نموذج المساحة', lambda n: ['E', n['a'], n['b']])
CTX_EST_MUL = [('ثمن الكتاب {b} جنيهًا، واشترينا كتبًا عددها {a}. كم ندفع تقريبًا؟',
                'A book costs {b} pounds and we buy {a} books. About how much do we pay?')]
perf('ctx_est_mul', lambda n: ctx(CTX_EST_MUL, dict(n, c=0), est_mul(n), a=n['a'], b=n['b']), est_mul, D553,
     'صورة الموقف، والنص منطوق', lambda n: ['E', n['a'], n['b']])
D554 = [dict(a=a, b=b, w=w) for a in range(12, 99, 3) for b in range(11, 99, 4) for w in range(3)]


def shown_sum(n):                                           # 0 الصحيح، 1 قريب منه، 2 بعيد بمنزلة (غير معقول)
    s = n['a'] + n['b']
    return [s, s + 2, s * 10 + n['b'] % 10][n['w']]


perf('reasonable', lambda n: ('الجواب %d عن %s. هل هو معقول؟' % (shown_sum(n), eq('%d + %d' % (n['a'], n['b']))),
                              'The answer %d to %s. Is it reasonable?' % (shown_sum(n), eq('%d + %d' % (n['a'], n['b']))),
                              'no' if n['w'] == 2 else 'yes', None),
     lambda n: 'no' if n['w'] == 2 else 'yes', D554, 'بلا نموذج', lambda n: ['+', n['a'], n['b'], n['w']], cards='yesno')

SKILLS.update({
    '5-1-1': S(['ف1', 'ف3'], {'ف1': 'places_read', 'ف3': 'decomp4', 'solve': 'decomp4'},
               [(3, 'الآلاف', lambda n: n['k'] == 0), (3, 'المئات', lambda n: n['k'] == 1), (2, 'العشرات', lambda n: n['k'] == 2),
                (2, 'الآحاد', lambda n: n['k'] == 3)]),
    '5-1-2': S(['ف1', 'ف3'], {'ف1': 'shift_model', 'ف3': 'shift_mul', 'solve': 'shift_mul'},
               [(5, 'في 10', lambda n: n['z'] == 1), (5, 'في 100', lambda n: n['z'] == 2)]),
    '5-1-3': S(['ف1', 'ف3'], {'ف1': 'shift_div_model', 'ف3': 'shift_div', 'solve': 'shift_div'},
               [(5, 'على 10', lambda n: n['z'] == 1), (5, 'على 100', lambda n: n['z'] == 2)]),
    '5-2-1': S(['ف2', 'ف3'], {'ف2': 'left_step', 'ف3': 'add3', 'solve': 'add3'},
               [(5, 'آحاد بلا عبور', lambda n: n['a'] % 10 + n['b'] % 10 < 10), (5, 'آحاد بعبور', lambda n: n['a'] % 10 + n['b'] % 10 >= 10)]),
    '5-2-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'adj3_step', 'ف3': 'adj3', 'ف5': 'judge_adj3', 'solve': 'adj3'},
               [(5, 'جمع', lambda n: n['op'] > 0), (5, 'طرح', lambda n: n['op'] < 0)]),
    '5-2-3': S(['ف1', 'ف2', 'ف3', 'ف4'], {'ف1': 'comp3_line', 'ف2': 'comp3_step', 'ف3': 'sub3', 'ف4': 'ctx_sub3', 'solve': 'sub3'},
               [(5, 'المئتان متجاورتان', lambda n: n['a'] // 100 - n['b'] // 100 == 1),
                (5, 'بينهما مئة أو أكثر', lambda n: n['a'] // 100 - n['b'] // 100 > 1)]),
    '5-3-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'thousand_line', 'ف2': 'thousand_step', 'ف3': 'thousand', 'solve': 'thousand'},
               [(5, 'من أقل من 500', lambda n: n['a'] < 500), (5, 'من 500 فأكثر', lambda n: n['a'] >= 500)]),
    '5-3-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'short_comp_step', 'ف3': 'short_comp', 'ف5': 'judge_short_comp', 'solve': 'short_comp'},
               [(6, 'آحاده غير صفر', lambda n: n['a'] % 10 != 0), (4, 'آحاده صفر', lambda n: n['a'] % 10 == 0)]),
    '5-3-3': S(['ف4'], {'ف4': 'change3', 'solve': 'change3'},
               [(5, 'من 200', lambda n: n['m'] == 200), (5, 'من 500', lambda n: n['m'] == 500)]),
    '5-4-1': S(['ف1', 'ف3', 'ف5'], {'ف1': 'area_mul', 'ف3': 'mul_tens', 'ف5': 'judge_mul_tens', 'solve': 'mul_tens'},
               [(5, 'عشرات في عشرات', lambda n: n['x'] == n['y'] == 10), (5, 'فيها مئات', lambda n: 100 in (n['x'], n['y']))]),
    '5-4-2': S(['ف2', 'ف3'], {'ف2': 'div_tens_step', 'ف3': 'div_tens', 'solve': 'div_tens'},
               [(5, 'الخارج عشرات', lambda n: n['x'] == 10), (5, 'الخارج مئات', lambda n: n['x'] == 100)]),
    '5-5-1': S(['ف1', 'ف3'], {'ف1': 'round_big_line', 'ف3': 'round_big', 'solve': 'round_big'},
               [(3, 'إلى أقرب 10', lambda n: n['u'] == 10), (4, 'إلى أقرب 100', lambda n: n['u'] == 100),
                (3, 'إلى أقرب 1000', lambda n: n['u'] == 1000)]),
    '5-5-2': S(['ف3', 'ف4'], {'ف3': 'est_add', 'ف4': 'ctx_est', 'solve': 'est_add'},
               [(5, 'جمع', lambda n: n['op'] > 0), (5, 'طرح', lambda n: n['op'] < 0)]),
    '5-5-3': S(['ف3', 'ف4'], {'ف3': 'est_mul', 'ف4': 'ctx_est_mul', 'solve': 'est_mul'},
               [(5, 'أحدهما أقل من 40', lambda n: n['a'] < 40), (5, 'كلاهما 40 فأكثر', lambda n: n['a'] >= 40)]),
    '5-5-4': S(['ف5'], {'ف5': 'reasonable', 'solve': 'reasonable'},
               [(4, 'معقول: الناتج', lambda n: n['w'] == 0), (3, 'معقول: قريب', lambda n: n['w'] == 1),
                (3, 'غير معقول: بعيد بمنزلة', lambda n: n['w'] == 2)]),
})


# ---------------------------------------------------------------- المرحلة 6: الضرب والقسمة بأعداد كبيرة
# الرسم: grid مستطيل مقسوم: أطوال أجزاء ضلعه الأعلى top وضلعه الجانبي side مكتوبة، والمناطق بلا نواتجها؛ cross شريط
# يُنزع من آخر الضلع الأعلى (التعويض). halve مستطيلان: قبل القصّ وبعد إعادة الترتيب، وضلع الثاني الطويل مجهول.
# strip شريط المقسوم مقسومًا إلى جزأين بأطوالهما، والقاسم مكتوب
MODEL_OK['grid'] = lambda m, n, ans: (sum(m['top']) - m.get('cross', 0)) * sum(m['side']) == ans
MODEL_OK['halve'] = lambda m, n, ans: m['a'] * m['b'] == m['a2'] * ans
MODEL_OK['strip'] = lambda m, n, ans: sum(m['parts']) == m['by'] * ans and all(p % m['by'] == 0 for p in m['parts'])


def split2(v):
    return [v // 10 * 10, v % 10] if v % 10 else [v]


D611 = [dict(a=a, b=b) for a in range(12, 100) for b in range(3, 10) if a % 10 and a % 3 == 0]
CTX_MUL2 = [('ثمن الكرة {a} جنيهًا، واشترينا كرات عددها {b}. كم ندفع؟',
             'A ball costs {a} pounds and we buy {b} balls. How much do we pay?'),
            ('في الصندوق {a} برتقالة، وعدد الصناديق {b}. كم برتقالة في الصناديق كلها؟',
             'Each crate has {a} oranges and there are {b} crates. How many oranges are there?')]
perf('grid_mul', lambda n: ('%s كم المجموع؟' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                            '%s What is the total?' % eq('%d %s %d' % (n['a'], TIMES, n['b'])), n['a'] * n['b'],
                            dict(kind='grid', top=split2(n['a']), side=[n['b']])),
     lambda n: n['a'] * n['b'], D611, 'نموذج المساحة', fact_mul)
perf('dist_step', lambda n: plain('%d %s %d = %d + %s' % (n['a'], TIMES, n['b'], n['a'] // 10 * 10 * n['b'], BOX), n['a'] % 10 * n['b']),
     lambda n: n['a'] % 10 * n['b'], D611, 'بلا نموذج', fact_mul)
perf('mul21', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     D611, 'بلا نموذج', fact_mul)
perf('ctx_mul2', lambda n: ctx(CTX_MUL2, n, n['a'] * n['b'], a=n['a'], b=n['b']), lambda n: n['a'] * n['b'],
     [dict(d, c=c) for d in D611 for c in range(2)], 'صورة الموقف، والنص منطوق', fact_mul)
D612 = [dict(a=a, b=b) for a in range(112, 999, 7) for b in range(2, 10) if a * b < 10000 and a % 10 and a // 10 % 10]


def dist3(n):
    a, b = n['a'], n['b']
    return '%d %s %d = %d + %d + %s' % (a, TIMES, b, a // 100 * 100 * b, a // 10 % 10 * 10 * b, BOX), a % 10 * b


perf('dist3_step', lambda n: plain(*dist3(n)), lambda n: n['a'] % 10 * n['b'], D612, 'بلا نموذج', fact_mul)
perf('mul31', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     D612, 'بلا نموذج', fact_mul)
D621 = [dict(a=a, b=b) for t in range(2, 10) for a in (10 * t - 1, 10 * t - 2) for b in range(3, 10)]
D622 = [dict(a=a, b=b) for t in range(2, 10) for a in (10 * t + 1, 10 * t + 2) for b in range(3, 10)]


def comp_text(n):
    a, b = n['a'], n['b']
    r = round(a, -1)
    return '%d %s %d = %d %s %s' % (a, TIMES, b, r * b, MINUS if a < r else '+', BOX), abs(r - a) * b


perf('comp_model', lambda n: ('%s كم المجموع بعد نزع الشريط؟' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                              '%s What is the total after the strip is removed?' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                              n['a'] * n['b'], dict(kind='grid', top=[round(n['a'], -1)], side=[n['b']], cross=round(n['a'], -1) - n['a'])),
     lambda n: n['a'] * n['b'], D621, 'مساحة يُنزع منها شريط', fact_mul)
perf('comp_step', lambda n: plain(*comp_text(n)), lambda n: abs(round(n['a'], -1) - n['a']) * n['b'],
     lambda skill: D621 if skill == '6-2-1' else D622, 'بلا نموذج', fact_mul)
perf('comp_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     lambda skill: D621 if skill == '6-2-1' else D622, 'بلا نموذج', fact_mul)
perf('judge_comp', lambda n: judge('%d %s %d = %d %s %d' % (n['a'], TIMES, n['b'], round(n['a'], -1) * n['b'],
                                                          '+' if n['w'] == 0 else MINUS, (n['a'] - round(n['a'], -1)) * n['b']),
                                   n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D622 for w in (0, 1)], 'بلا نموذج', fact_mul, cards='yesno')
D631 = [dict(a=a, b=b) for a in range(12, 50, 2) for b in (15, 25, 35, 45) if a * b < 10000]
perf('halve_model', lambda n: ('%s نقصّ المستطيل نصفين ونضع النصف بجانب الآخر. %s' % (
    eq('%d %s %d' % (n['a'], TIMES, n['b'])), eq('%d %s %s' % (n['a'] // 2, TIMES, BOX))),
    'Cut the rectangle in half and put the halves side by side. %s %s' % (
    eq('%d %s %d' % (n['a'], TIMES, n['b'])), eq('%d %s %s' % (n['a'] // 2, TIMES, BOX))),
    2 * n['b'], dict(kind='halve', a=n['a'], b=n['b'], a2=n['a'] // 2)),
     lambda n: 2 * n['b'], D631, 'مستطيل يُقصّ ويُعاد ترتيبه', fact_mul)
perf('halve_step', lambda n: plain('%d %s %d = %d %s %s' % (n['a'], TIMES, n['b'], n['a'] // 2, TIMES, BOX), 2 * n['b']),
     lambda n: 2 * n['b'], D631, 'بلا نموذج', fact_mul)
perf('halve_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     D631, 'بلا نموذج', fact_mul)
D632 = [dict(a=a, f=f) for a in range(12, 100, 2) for f in (5, 50)]
perf('five_step', lambda n: plain('%d %s %d = %s %s 2' % (n['a'], TIMES, n['f'], BOX, DIV), n['a'] * n['f'] * 2),
     lambda n: n['a'] * n['f'] * 2, D632, 'مستطيل يُقصّ نصفين', lambda n: ['×', n['f'], n['a']])
perf('five_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['f'], BOX), n['a'] * n['f']), lambda n: n['a'] * n['f'],
     D632, 'بلا نموذج', lambda n: ['×', n['f'], n['a']])
D633 = [dict(a=a, w=w) for a in range(8, 100, 4) for w in (0,)]
perf('q25_step', lambda n: plain('%d %s 25 = %s %s 100' % (n['a'], TIMES, BOX, TIMES), n['a'] // 4),
     lambda n: n['a'] // 4, D633, 'أربعة أرباع تصنع واحدًا', lambda n: ['×', 25, n['a']])
perf('q25_mul', lambda n: plain('%d %s 25 = %s' % (n['a'], TIMES, BOX), n['a'] * 25), lambda n: n['a'] * 25, D633,
     'بلا نموذج', lambda n: ['×', 25, n['a']])
perf('judge_q25', lambda n: judge('%d %s 25 = %d' % (n['a'], TIMES, n['a'] * 25 if n['w'] == 0 else n['a'] // 2 * 100), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(a=d['a'], w=w) for d in D633 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['×', 25, n['a']], cards='yesno')
D641 = [dict(a=a, b=b, f=f) for a in (15, 25, 35, 45) for f in (2, 4) for b in range(f * 3, 50, f) if a * b < 10000 and (a * f) % 10 == 0]
perf('factor_step', lambda n: plain('%d %s %d = %d %s %s' % (n['a'], TIMES, n['b'], n['a'] * n['f'], TIMES, BOX), n['b'] // n['f']),
     lambda n: n['b'] // n['f'], D641, 'مصفوفة يُعاد تجميعها', fact_mul)
perf('factor_mul', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     D641, 'بلا نموذج', fact_mul)
D642 = [dict(a=a) for a in range(12, 100) if a % 10]
perf('e11_step', lambda n: plain('%d %s 11 = %d + %s' % (n['a'], TIMES, 10 * n['a'], BOX), n['a']), lambda n: n['a'], D642,
     'مساحة مقسومة إلى 10 و1', lambda n: ['×', 11, n['a']])
perf('e11', lambda n: plain('%d %s 11 = %s' % (n['a'], TIMES, BOX), 11 * n['a']), lambda n: 11 * n['a'], D642, 'بلا نموذج',
     lambda n: ['×', 11, n['a']])
perf('judge_e11', lambda n: judge('%d %s 11 = %d' % (n['a'], TIMES, 11 * n['a'] if n['w'] == 0 else int('%d%d%d' % (
    n['a'] // 10, (n['a'] // 10 + n['a'] % 10) % 10, n['a'] % 10))), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(a=d['a'], w=w) for d in D642 if d['a'] // 10 + d['a'] % 10 >= 10 for w in (0, 1)],
     'بلا نموذج', lambda n: ['×', 11, n['a']], cards='yesno')
D643 = [dict(a=a, f=f) for a in range(11, 40) for f in (12, 15) if a % 10]
perf('e1215_step', lambda n: plain('%d %s %d = %d + %s' % (n['a'], TIMES, n['f'], 10 * n['a'], BOX), (n['f'] - 10) * n['a']),
     lambda n: (n['f'] - 10) * n['a'], D643, 'مساحة مقسومة', lambda n: ['×', n['f'], n['a']])
perf('e1215', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['f'], BOX), n['f'] * n['a']), lambda n: n['f'] * n['a'], D643,
     'بلا نموذج', lambda n: ['×', n['f'], n['a']])
D651 = [dict(a=a, b=b) for a in range(12, 60) for b in range(12, 20) if a % 10 and b % 10 and a * b < 10000 and a > b]
perf('m22_step', lambda n: plain('%d %s %d = %d + %s' % (n['a'], TIMES, n['b'], 10 * n['a'], BOX), (n['b'] - 10) * n['a']),
     lambda n: (n['b'] - 10) * n['a'], D651, 'نموذج المساحة بجزأين', fact_mul)
perf('m22', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'], D651,
     'بلا نموذج', fact_mul)
CTX_MUL22 = [('في القاعة صفوف عددها {b}، وفي كل صف {a} مقعدًا. كم مقعدًا في القاعة؟',
              'A hall has {b} rows with {a} seats in each row. How many seats are there?')]
perf('ctx_m22', lambda n: ctx(CTX_MUL22, dict(n, c=0), n['a'] * n['b'], a=n['a'], b=n['b']), lambda n: n['a'] * n['b'], D651,
     'صورة الموقف، والنص منطوق', fact_mul)
D652 = [dict(a=a, b=b, w=w) for a in range(12, 50) for b in range(12, 30) if a % 10 and b % 10 and a > b for w in (0, 1)]
perf('grid4', lambda n: ('%s كم مجموع المناطق الأربع؟' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                         '%s What do the four parts add up to?' % eq('%d %s %d' % (n['a'], TIMES, n['b'])), n['a'] * n['b'],
                         dict(kind='grid', top=split2(n['a']), side=split2(n['b']))),
     lambda n: n['a'] * n['b'], [d for d in D652 if d['w'] == 0], 'نموذج المساحة بأربع مناطق', fact_mul)


def four(n):
    a, b = n['a'], n['b']
    p = [a // 10 * 10 * (b // 10 * 10), a % 10 * (b // 10 * 10), a // 10 * 10 * (b % 10), a % 10 * (b % 10)]
    return p if n['w'] == 0 else p[:3]                      # الخطأ: نسيان ناتج الآحاد في الآحاد


perf('judge_four', lambda n: judge('%d %s %d = %s' % (n['a'], TIMES, n['b'], ' + '.join(map(str, four(n)))), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', D652, 'بلا نموذج', fact_mul, cards='yesno')
D661 = [dict(q=q, k=k) for k in range(3, 10) for q in range(12, 100) if q % 10 and q * k < 1000 and q * k >= 100]
perf('strip_div', lambda n: ('%s قسمنا الشريط جزأين يقبل كلٌّ منهما القسمة على %d. كم الخارج؟' % (
    eq('%d %s %d' % (n['q'] * n['k'], DIV, n['k'])), n['k']),
    '%s The strip is split into two parts that both divide by %d. What is the quotient?' % (
    eq('%d %s %d' % (n['q'] * n['k'], DIV, n['k'])), n['k']),
    n['q'], dict(kind='strip', parts=[n['q'] // 10 * 10 * n['k'], n['q'] % 10 * n['k']], by=n['k'])),
     lambda n: n['q'], D661, 'شريط مقسوم إلى جزأين', lambda n: ['÷', n['q'] * n['k'], n['k']])
perf('split_div_step', lambda n: plain('%d %s %d = %d + %s' % (n['q'] * n['k'], DIV, n['k'], n['q'] // 10 * 10, BOX), n['q'] % 10),
     lambda n: n['q'] % 10, D661, 'بلا نموذج', lambda n: ['÷', n['q'] * n['k'], n['k']])
perf('split_div', lambda n: plain('%d %s %d = %s' % (n['q'] * n['k'], DIV, n['k'], BOX), n['q']), lambda n: n['q'], D661,
     'بلا نموذج', lambda n: ['÷', n['q'] * n['k'], n['k']])
perf('ctx_split_div', lambda n: ctx(CTX_DIV, n, n['q'], n=n['q'] * n['k'], k=n['k']), lambda n: n['q'],
     [dict(d, c=c) for d in D661 for c in range(2)], 'صورة الموقف، والنص منطوق', lambda n: ['÷', n['q'] * n['k'], n['k']])
D662 = ([dict(q=q, d=8) for q in range(11, 125) if q % 2] + [dict(q=q, d=5) for q in range(21, 200, 3)]
        + [dict(q=q, d=25) for q in range(3, 40)])


def halving_step(n):
    """في 432 ÷ 8 ثلاثة تنصيفات: الأولان مكتوبان والثالث مجهول. وفي القسمة على 5: الضعف على 10."""
    q, d = n['q'], n['d']
    if d == 8:
        parts = ['%d %s 2 = %d' % (q * 8, DIV, q * 4), '%d %s 2 = %d' % (q * 4, DIV, q * 2), '%d %s 2 = %s' % (q * 2, DIV, BOX)]
        head = eq('%d %s 8' % (q * 8, DIV))
        return ('%s: %s' % (head, '، ثم '.join(eq(x) for x in parts)), '%s: %s' % (head, ', then '.join(eq(x) for x in parts)), q, None)
    return plain('%d %s 5 = %d %s 10 = %s' % (q * 5, DIV, q * 10, DIV, BOX), q)


perf('halving_step', halving_step, lambda n: n['q'], [d for d in D662 if d['d'] != 25], 'شريط يُقصّ',
     lambda n: ['÷', n['q'] * n['d'], n['d']])
perf('halving_div', lambda n: plain('%d %s %d = %s' % (n['q'] * n['d'], DIV, n['d'], BOX), n['q']), lambda n: n['q'], D662,
     'بلا نموذج', lambda n: ['÷', n['q'] * n['d'], n['d']])
D663 = [dict(k=k, q=q, r=r) for k in range(3, 10) for q in range(12, 60, 3) for r in range(1, k) if q * k + r < 600]
perf('divr_big', lambda n: ('%s الخارج؟ والباقي؟' % eq('%d %s %d = %s' % (n['k'] * n['q'] + n['r'], DIV, n['k'], BOX)),
                            '%s Quotient? Remainder?' % eq('%d %s %d = %s' % (n['k'] * n['q'] + n['r'], DIV, n['k'], BOX)),
                            qr(n['q'], n['r']), None),
     lambda n: qr(n['q'], n['r']), D663, 'شريط مع ما يبقى', lambda n: ['÷', n['k'] * n['q'] + n['r'], n['k']])
perf('ctx_divr_big', lambda n: ctx(CTX_DIVR, n, qr(n['q'], n['r']), n=n['k'] * n['q'] + n['r'], k=n['k']),
     lambda n: qr(n['q'], n['r']), [dict(d, c=c) for d in D663 for c in range(2)], 'صورة الموقف، والنص منطوق',
     lambda n: ['÷', n['k'] * n['q'] + n['r'], n['k']])


# قابلية القسمة (ج11): «هل يقبل العدد القسمة على d؟»، والحكم في ف5 على تعليل معروض
def divisible_q(n):
    return ('هل يقبل العدد %d القسمة على %d؟' % (n['v'], n['d']), 'Is %d divisible by %d?' % (n['v'], n['d']),
            'yes' if n['v'] % n['d'] == 0 else 'no', None)


def div_dom(ds, lo, hi, step):
    """أعداد بخطوة ثابتة، ومعها مضاعفات كل قاسم بالخطوة نفسها: نصف الخانات «يقبل»."""
    return ([dict(v=v, d=d) for d in ds for v in range(lo, hi, step)]
            + [dict(v=d * m, d=d) for d in ds for m in range(lo // d + 1, hi // d, max(step // d, 1)) if d * m % 10 or d == 10])


REASON = {2: ('آخر رقم فيه %d', 'its last digit is %d'), 5: ('آخر رقم فيه %d', 'its last digit is %d'),
          10: ('آخر رقم فيه %d', 'its last digit is %d'), 4: ('آخر رقمين فيه %d', 'its last two digits are %d'),
          8: ('آخر ثلاثة أرقام فيه %d', 'its last three digits are %d'), 3: ('مجموع أرقامه %d', 'its digit sum is %d'),
          9: ('مجموع أرقامه %d', 'its digit sum is %d'), 11: ('فرق مجموعي منازله المتناوبة %d', 'its alternating digit sum difference is %d')}


def reason_val(v, d):
    if d in (2, 5, 10):
        return v % 10
    if d == 4:
        return v % 100
    if d == 8:
        return v % 1000
    if d in (3, 9):
        return sum(map(int, str(v)))
    s = str(v)
    return abs(sum(int(c) for c in s[::-2]) - sum(int(c) for c in s[-2::-2]))


def judge_div(n):
    """العدد يقبل القسمة على d لأن (تعليل)؟ w=1: التعليل صحيح القيمة والعدد لا يقبل، أو العكس: الحكم على النتيجة."""
    v, d = n['v'], n['d']
    ar, en = REASON[d]
    ok = v % d == 0
    return ('العدد %d يقبل القسمة على %d لأن %s. هل هذا صحيح؟' % (v, d, ar % reason_val(v, d)),
            '%d is divisible by %d because %s. Is this true?' % (v, d, en % reason_val(v, d)), 'yes' if ok else 'no', None)


for name, ds, lo, hi, step in (('div2510', (2, 5, 10), 101, 1000, 13), ('div48', (4, 8), 104, 2000, 17),
                               ('div396', (3, 9, 6), 102, 1000, 11), ('div11', (11,), 121, 9999, 37)):
    dd = div_dom(ds, lo, hi, step)
    perf(name, divisible_q, lambda n: 'yes' if n['v'] % n['d'] == 0 else 'no', dd, 'جدول المنازل',
         lambda n: ['|', n['v'], n['d']], cards='yesno')
    perf('judge_' + name, judge_div, lambda n: 'yes' if n['v'] % n['d'] == 0 else 'no',
         [x for x in dd if x['d'] != 6], 'بلا نموذج', lambda n: ['|', n['v'], n['d'], 'r'], cards='yesno')
perf('digit_sum', lambda n: ('ما مجموع أرقام العدد %d؟' % n['v'], 'What is the digit sum of %d?' % n['v'],
                             sum(map(int, str(n['v']))), dict(kind='places', digits=[int(c) for c in str(n['v'])], value=n['v'])),
     lambda n: sum(map(int, str(n['v']))), div_dom((3, 9), 102, 1000, 11), 'مكعبات تُفكّ كل عشرة فيها إلى 9 و1',
     lambda n: ['s', n['v']])
YES = lambda n: n['v'] % n['d'] == 0
SKILLS.update({
    '6-1-1': S(['ف1', 'ف2', 'ف3', 'ف4'], {'ف1': 'grid_mul', 'ف2': 'dist_step', 'ف3': 'mul21', 'ف4': 'ctx_mul2', 'solve': 'mul21'},
               [(5, 'المضروب حتى 50', lambda n: n['a'] < 50), (5, 'المضروب فوق 50', lambda n: n['a'] > 50)]),
    '6-1-2': S(['ف2', 'ف3'], {'ف2': 'dist3_step', 'ف3': 'mul31', 'solve': 'mul31'},
               [(5, 'في رقم حتى 5', lambda n: n['b'] <= 5), (5, 'في رقم فوق 5', lambda n: n['b'] > 5)]),
    '6-2-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'comp_model', 'ف2': 'comp_step', 'ف3': 'comp_mul', 'solve': 'comp_mul'},
               [(5, 'ينتهي بـ 9', lambda n: n['a'] % 10 == 9), (5, 'ينتهي بـ 8', lambda n: n['a'] % 10 == 8)]),
    '6-2-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'comp_step', 'ف3': 'comp_mul', 'ف5': 'judge_comp', 'solve': 'comp_mul'},
               [(5, 'ينتهي بـ 1', lambda n: n['a'] % 10 == 1), (5, 'ينتهي بـ 2', lambda n: n['a'] % 10 == 2)]),
    '6-3-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'halve_model', 'ف2': 'halve_step', 'ف3': 'halve_mul', 'solve': 'halve_mul'},
               [(5, 'المضاعف 15 أو 25', lambda n: n['b'] <= 25), (5, 'المضاعف 35 أو 45', lambda n: n['b'] > 25)]),
    '6-3-2': S(['ف2', 'ف3'], {'ف2': 'five_step', 'ف3': 'five_mul', 'solve': 'five_mul'},
               [(5, 'في 5', lambda n: n['f'] == 5), (5, 'في 50', lambda n: n['f'] == 50)]),
    '6-3-3': S(['ف2', 'ف3', 'ف5'], {'ف2': 'q25_step', 'ف3': 'q25_mul', 'ف5': 'judge_q25', 'solve': 'q25_mul'},
               [(5, 'المضروب حتى 48', lambda n: n['a'] <= 48), (5, 'المضروب فوق 48', lambda n: n['a'] > 48)]),
    '6-4-1': S(['ف2', 'ف3'], {'ف2': 'factor_step', 'ف3': 'factor_mul', 'solve': 'factor_mul'},
               [(5, 'تفكيك 2', lambda n: n['f'] == 2), (5, 'تفكيك 4', lambda n: n['f'] == 4)]),
    '6-4-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'e11_step', 'ف3': 'e11', 'ف5': 'judge_e11', 'solve': 'e11'},
               [(4, 'بلا حمل', lambda n: n['a'] // 10 + n['a'] % 10 < 10), (6, 'مع حمل', lambda n: n['a'] // 10 + n['a'] % 10 >= 10)]),
    '6-4-3': S(['ف2', 'ف3'], {'ف2': 'e1215_step', 'ف3': 'e1215', 'solve': 'e1215'},
               [(5, 'في 12', lambda n: n['f'] == 12), (5, 'في 15', lambda n: n['f'] == 15)]),
    '6-5-1': S(['ف2', 'ف3', 'ف4'], {'ف2': 'm22_step', 'ف3': 'm22', 'ف4': 'ctx_m22', 'solve': 'm22'},
               [(5, 'المضروب حتى 30', lambda n: n['a'] <= 30), (5, 'المضروب فوق 30', lambda n: n['a'] > 30)]),
    '6-5-2': S(['ف1', 'ف5'], {'ف1': 'grid4', 'ف5': 'judge_four', 'solve': 'grid4'},
               [(5, 'المضروب حتى 30', lambda n: n['a'] <= 30), (5, 'المضروب فوق 30', lambda n: n['a'] > 30)]),
    '6-6-1': S(['ف1', 'ف2', 'ف3', 'ف4'], {'ف1': 'strip_div', 'ف2': 'split_div_step', 'ف3': 'split_div', 'ف4': 'ctx_split_div',
                                          'solve': 'split_div'},
               [(5, 'القاسم حتى 5', lambda n: n['k'] <= 5), (5, 'القاسم فوق 5', lambda n: n['k'] > 5)]),
    '6-6-2': S(['ف2', 'ف3'], {'ف2': 'halving_step', 'ف3': 'halving_div', 'solve': 'halving_div'},
               [(4, 'على 8 بثلاثة تنصيفات', lambda n: n['d'] == 8), (3, 'على 5', lambda n: n['d'] == 5),
                (3, 'على 25', lambda n: n['d'] == 25)]),
    '6-6-3': S(['ف3', 'ف4'], {'ف3': 'divr_big', 'ف4': 'ctx_divr_big', 'solve': 'divr_big'},
               [(5, 'القاسم حتى 5', lambda n: n['k'] <= 5), (5, 'القاسم فوق 5', lambda n: n['k'] > 5)]),
    '6-7-1': S(['ف3', 'ف5'], {'ف3': 'div2510', 'ف5': 'judge_div2510', 'solve': 'div2510'},
               [(5, 'يقبل', YES), (5, 'لا يقبل', lambda n: not YES(n))]),
    '6-7-2': S(['ف3', 'ف5'], {'ف3': 'div48', 'ف5': 'judge_div48', 'solve': 'div48'},
               [(5, 'يقبل', YES), (5, 'لا يقبل', lambda n: not YES(n))]),
    '6-7-3': S(['ف1', 'ف3', 'ف5'], {'ف1': 'digit_sum', 'ف3': 'div396', 'ف5': 'judge_div396', 'solve': 'div396'},
               [(5, 'يقبل', YES), (5, 'لا يقبل', lambda n: not YES(n))]),
    '6-7-4': S(['ف3', 'ف5'], {'ف3': 'div11', 'ف5': 'judge_div11', 'solve': 'div11'},
               [(5, 'يقبل', YES), (5, 'لا يقبل', lambda n: not YES(n))]),
})


# ---------------------------------------------------------------- المرحلة 7: الكسور والأعداد العشرية والنسبة المئوية
# الرسم: fstrip شريط مقسوم d أجزاء، الملوّن منها n (وشريط ثانٍ d2 للمكافئ، و whole قيمة الشريط كله إن كانت كمية).
# grid100 شبكة المئة، الملوّن منها n. الجواب العشري dec (n، s)، والكسر frac، والنقود money بالقروش
def dec(v_hund, s=2):
    """عدد عشري من قيمته بأجزاء 10^s، في أبسط منازل (3.70 = 3.7)."""
    while s and v_hund % 10 == 0:
        v_hund, s = v_hund // 10, s - 1
    return dict(t='dec', n=v_hund, s=s)


def dtext(n, s):                                            # 375، 2 إلى «3.75»
    t = str(n).rjust(s + 1, '0')
    return t[:-s] + '.' + t[-s:] if s else t


def frac(n, d, simplest=False):
    return dict(t='frac', n=n, d=d, **({'simplest': True} if simplest else {}))


MODEL_OK['fstrip'] = lambda m, n, ans: 0 <= m['n'] <= m['d'] and (
    (isinstance(ans, dict) and ans.get('t') == 'frac' and ans['n'] * m['d'] == m['n'] * ans['d'])
    or (isinstance(ans, int) and (m.get('whole') is not None and m['whole'] % m['d'] == 0
                                  and ans == m['whole'] // m['d'] * m['n'] or m.get('d2') and ans * m['d'] == m['n'] * m['d2']))
    or (isinstance(ans, int) and m.get('times') is not None and ans == m['times'] * m['d'])
    or ans in ('yes', 'no', 'A', 'B', 'C'))
MODEL_OK['grid100'] = lambda m, n, ans: (
    isinstance(ans, dict) and ans['t'] == 'dec' and ans['n'] * 10 ** (2 - ans['s']) == m['n']
    or ans == 'A' and 'd' in n and m['n'] * n['d'] == 100 * n['n'])
MODEL_OK['grids'] = lambda m, n, ans: sorted(m['cells']) == sorted([n['a'] * 10, n['b']]) and \
    (m['cells'][0] > m['cells'][1]) == (ans == 'A') and m['labels'] == cmp_cards(n)[1]
WORDS = {(1, 2): ('نصف', 'one half'), (1, 3): ('ثلث', 'one third'), (2, 3): ('ثلثان', 'two thirds'),
         (1, 4): ('ربع', 'one quarter'), (3, 4): ('ثلاثة أرباع', 'three quarters'), (1, 5): ('خُمس', 'one fifth'),
         (2, 5): ('خُمسان', 'two fifths'), (3, 5): ('ثلاثة أخماس', 'three fifths'), (4, 5): ('أربعة أخماس', 'four fifths'),
         (1, 6): ('سُدس', 'one sixth'), (5, 6): ('خمسة أسداس', 'five sixths'), (1, 8): ('ثُمن', 'one eighth'),
         (3, 8): ('ثلاثة أثمان', 'three eighths'), (5, 8): ('خمسة أثمان', 'five eighths'), (7, 8): ('سبعة أثمان', 'seven eighths'),
         (1, 10): ('عُشر', 'one tenth'), (3, 10): ('ثلاثة أعشار', 'three tenths'), (7, 10): ('سبعة أعشار', 'seven tenths')}
OF = {(2, 3): 'ثلثا', (2, 5): 'خُمسا'}                        # المثنى مضافًا تسقط نونه: «ثلثا 36»


def of(a, b):
    return OF.get((a, b), WORDS[(a, b)][0])


D711 = [dict(n=a, d=b, w=0) for (a, b) in WORDS]
perf('frac_strip', lambda n: ('ما الكسر الملوّن من الشريط؟', 'What fraction of the strip is coloured?', frac(n['n'], n['d']),
                              dict(kind='fstrip', n=n['n'], d=n['d'])),
     lambda n: frac(n['n'], n['d']), D711, 'شريط مقسّم', lambda n: ['f', n['n'], n['d']])
perf('frac_words', lambda n: ('اكتب الكسر: %s' % WORDS[(n['n'], n['d'])][0], 'Write the fraction: %s' % WORDS[(n['n'], n['d'])][1],
                              frac(n['n'], n['d']), None),
     lambda n: frac(n['n'], n['d']), D711, 'بلا نموذج', lambda n: ['f', n['n'], n['d']])
perf('judge_frac_strip', lambda n: ('هل الملوّن %s الشريط؟' % WORDS[(n['n'], n['d'])][0] if n['w'] == 0 else
                                    'هل الملوّن %s الشريط؟' % WORDS[(n['n'], n['d'])][0],
                                    'Is the coloured part %s of the strip?' % WORDS[(n['n'], n['d'])][1],
                                    'yes' if n['w'] == 0 else 'no',
                                    dict(kind='fstrip', n=n['n'] if n['w'] == 0 else n['d'] - n['n'], d=n['d'])),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D711 for w in (0, 1) if not (w and 2 * d['n'] == d['d'])],
     'شريط مقسّم', lambda n: ['f', n['n'], n['d']], cards='yesno')
D712 = [dict(n=a, d=b, k=k) for (a, b) in [(1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (1, 5), (2, 5)] for k in (2, 3, 4)
        if b * k <= 12]
perf('equiv_strip', lambda n: ('%s الشريطان متطابقان.' % eq('%d/%d = %s/%d' % (n['n'], n['d'], BOX, n['d'] * n['k'])),
                               '%s The two strips are the same length.' % eq('%d/%d = %s/%d' % (n['n'], n['d'], BOX, n['d'] * n['k'])),
                               n['n'] * n['k'], dict(kind='fstrip', n=n['n'], d=n['d'], d2=n['d'] * n['k'])),
     lambda n: n['n'] * n['k'], D712, 'شريطان متطابقان', lambda n: ['q', n['n'], n['d'], n['k']])
perf('equiv', lambda n: plain('%d/%d = %s/%d' % (n['n'], n['d'], BOX, n['d'] * n['k']), n['n'] * n['k']),
     lambda n: n['n'] * n['k'], D712, 'بلا نموذج', lambda n: ['q', n['n'], n['d'], n['k']])
perf('judge_equiv', lambda n: judge('%d/%d = %d/%d' % (n['n'], n['d'], n['n'] * n['k'] + n['w'], n['d'] * n['k']), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D712 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['q', n['n'], n['d'], n['k']], cards='yesno')
D713 = [dict(d=d, q=q) for d in (2, 3, 4, 5, 6, 8, 10) for q in range(2, 13)]
UNITW = {2: ('نصف', 'half'), 3: ('ثلث', 'a third'), 4: ('ربع', 'a quarter'), 5: ('خُمس', 'a fifth'), 6: ('سُدس', 'a sixth'),
         8: ('ثُمن', 'an eighth'), 10: ('عُشر', 'a tenth')}
perf('unit_frac_strip', lambda n: ('%s %d؟ الشريط كله %d.' % (UNITW[n['d']][0], n['d'] * n['q'], n['d'] * n['q']),
                                   'What is %s of %d? The whole strip is %d.' % (UNITW[n['d']][1], n['d'] * n['q'], n['d'] * n['q']),
                                   n['q'], dict(kind='fstrip', n=1, d=n['d'], whole=n['d'] * n['q'])),
     lambda n: n['q'], D713, 'شريط مقسّم', lambda n: ['u', n['d'], n['q']])
perf('unit_frac', lambda n: ('%s %d = %s' % (UNITW[n['d']][0], n['d'] * n['q'], BOX), '%s of %d = %s' % (UNITW[n['d']][1], n['d'] * n['q'], BOX),
                             n['q'], None),
     lambda n: n['q'], D713, 'بلا نموذج', lambda n: ['u', n['d'], n['q']])
CTX_FRAC = [('عدد الطلاب {w}، ذهب {f} منهم في الرحلة. كم طالبًا ذهب؟',
             'There are {w} students and {fe} of them went on the trip. How many went?'),
            ('في العلبة {w} قلمًا، {f} منها أحمر. كم قلمًا أحمر؟',
             'A box has {w} pencils and {fe} of them are red. How many are red?')]
perf('ctx_unit_frac', lambda n: ctx(CTX_FRAC, n, n['q'], w=n['d'] * n['q'], f=UNITW[n['d']][0], fe=UNITW[n['d']][1]),
     lambda n: n['q'], [dict(d, c=c) for d in D713 for c in range(2) if 11 <= d['d'] * d['q'] % 100], 'صورة الموقف، والنص منطوق',
     lambda n: ['u', n['d'], n['q']])
D714 = [dict(n=a, d=b, q=q) for (a, b) in [(2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (3, 8), (5, 8), (3, 10), (7, 10), (5, 6)]
        for q in range(2, 13) if b * q <= 120]
perf('frac_of_step', lambda n: ('%s %d: %s %d = %d، فـ%s %d = %s' % (
    of(n['n'], n['d']), n['d'] * n['q'], UNITW[n['d']][0], n['d'] * n['q'], n['q'], of(n['n'], n['d']),
    n['d'] * n['q'], BOX),
    '%s of %d: %s of %d = %d, so %s of %d = %s' % (
    WORDS[(n['n'], n['d'])][1], n['d'] * n['q'], UNITW[n['d']][1], n['d'] * n['q'], n['q'], WORDS[(n['n'], n['d'])][1],
    n['d'] * n['q'], BOX), n['n'] * n['q'], None),
     lambda n: n['n'] * n['q'], D714, 'شريط مقسّم', lambda n: ['F', n['n'], n['d'], n['q']])
perf('frac_of', lambda n: ('%s %d = %s' % (of(n['n'], n['d']), n['d'] * n['q'], BOX),
                           '%s of %d = %s' % (WORDS[(n['n'], n['d'])][1], n['d'] * n['q'], BOX), n['n'] * n['q'], None),
     lambda n: n['n'] * n['q'], D714, 'بلا نموذج', lambda n: ['F', n['n'], n['d'], n['q']])
perf('ctx_frac_of', lambda n: ctx(CTX_FRAC, n, n['n'] * n['q'], w=n['d'] * n['q'], f=WORDS[(n['n'], n['d'])][0],
                                  fe=WORDS[(n['n'], n['d'])][1]),
     lambda n: n['n'] * n['q'], [dict(d, c=c) for d in D714 for c in range(2) if 11 <= d['d'] * d['q'] % 100],
     'صورة الموقف، والنص منطوق', lambda n: ['F', n['n'], n['d'], n['q']])


def reduce_(a, b):
    g = gcd(a, b)
    return a // g, b // g


D715 = ([dict(a=a, b=b, c=c, e=e, op=1) for b in (2, 4, 8) for e in (4, 8) if e > b for a in range(1, b) for c in range(1, e)
         if a * e // b + c < e and gcd(a, b) == 1 and gcd(c, e) == 1]
        + [dict(a=0, b=1, c=c, e=e, op=-1) for e in (2, 3, 4, 5, 8, 10) for c in range(1, e) if gcd(c, e) == 1])


def f715(n):
    if n['op'] < 0:
        return reduce_(n['e'] - n['c'], n['e'])
    return reduce_(n['a'] * n['e'] // n['b'] + n['c'], n['e'])


def t715(n):
    return ('%d/%d + %d/%d = %s' % (n['a'], n['b'], n['c'], n['e'], BOX) if n['op'] > 0
            else '1 %s %d/%d = %s' % (MINUS, n['c'], n['e'], BOX))


perf('frac_add_strip', lambda n: ('%s اكتب الناتج كسرًا.' % eq(t715(n)), '%s Write the answer as a fraction.' % eq(t715(n)),
                                  frac(*f715(n)), dict(kind='fstrip', n=f715(n)[0] * (n['e'] // f715(n)[1]), d=n['e'])),
     lambda n: frac(*f715(n)), D715, 'شريط، وجه الساعة', lambda n: ['A', n['a'], n['b'], n['c'], n['e'], n['op']])
perf('frac_add', lambda n: ('%s اكتب الناتج كسرًا.' % eq(t715(n)), '%s Write the answer as a fraction.' % eq(t715(n)),
                            frac(*f715(n)), None),
     lambda n: frac(*f715(n)), D715, 'بلا نموذج', lambda n: ['A', n['a'], n['b'], n['c'], n['e'], n['op']])
D721 = [dict(v=v) for v in range(101, 1000, 7) if v % 10]
perf('grid100', lambda n: ('ما العدد العشري الذي يمثله الملوّن؟ (الشبكة كلها واحد)', 'What decimal does the coloured part show? (the whole grid is one)',
                           dec(n['v'] % 100), dict(kind='grid100', n=n['v'] % 100)),
     lambda n: dec(n['v'] % 100), [d for d in D721 if d['v'] % 100 > 9], 'شبكة المئة', lambda n: ['d', n['v'] % 100])
perf('pounds_dec', lambda n: ('%d جنيهات و%d قرشًا = %s جنيه' % (n['v'] // 100, n['v'] % 100, BOX) if 3 <= n['v'] // 100 <= 10
                              else '%d جنيه و%d قرشًا = %s جنيه' % (n['v'] // 100, n['v'] % 100, BOX),
                              '%d pounds and %d piastres = %s pounds' % (n['v'] // 100, n['v'] % 100, BOX), dec(n['v']), None),
     lambda n: dec(n['v']), [d for d in D721 if d['v'] % 100 > 10 and d['v'] // 100 >= 3], 'جنيه وقرش',
     lambda n: ['d', n['v']])
D722 = [dict(a=a, b=b, s=s) for a in range(1, 10) for b in range(10, 100, 3) if b % 10 and a * 10 != b and abs(a * 10 - b) > 3 for s in (0, 1)]


def cmp_cards(n):
    x, y = '0.%d' % n['a'], '0.%d' % n['b']
    pair = (x, y) if n['s'] == 0 else (y, x)
    return ['A', 'B'], {'A': pair[0], 'B': pair[1]}


def cmp_ans(n):
    first_big = (n['a'] * 10 > n['b']) == (n['s'] == 0)
    return 'A' if first_big else 'B'


def cmp_cells(n):
    """خلايا شبكتي المئة بترتيب البطاقتين: الأعشار عشر خلايا لكل عُشر، والأجزاء من مئة خلية لكلٍّ."""
    x, y = n['a'] * 10, n['b']
    return [x, y] if n['s'] == 0 else [y, x]


perf('dec_compare_grid', lambda n: ('أيهما أكبر؟ كل شبكة واحد.', 'Which is greater? Each grid is one whole.', cmp_ans(n),
                                    dict(kind='grids', cells=cmp_cells(n), labels=cmp_cards(n)[1])),
     cmp_ans, D722, 'شبكة المئة', lambda n: ['c', n['a'], n['b']], cards=cmp_cards)
perf('dec_compare', lambda n: ('أيهما أكبر؟', 'Which is greater?', cmp_ans(n), None), cmp_ans, D722, 'بلا نموذج',
     lambda n: ['c', n['a'], n['b']], cards=cmp_cards)
D723 = ([dict(v=v, s=1, z=z, op=op) for v in range(11, 1000, 7) if v % 10 for z in (1, 2) for op in (1, -1)
         if not (op > 0 and v * 10 ** z >= 10 ** 4)])


def shift_dec(n):
    v, z, op = n['v'], n['z'], n['op']                       # العدد v ÷ 10 (منزلة عشرية)
    x = dtext(v, 1)
    if op > 0:
        return '%s %s %d = %s' % (x, TIMES, 10 ** z, BOX), dec(v * 10 ** z, 1)
    return '%s %s %d = %s' % (x, DIV, 10 ** z, BOX), dec(v, 1 + z)


# منزلق المنازل: العدد في جدول بمنازله العشرية، والسهم يحرك أرقامه z منزلة: يسارًا للضرب ويمينًا للقسمة. الناتج لا يُرسم
def shift_model(n):
    return dict(kind='places', digits=[int(c) for c in str(n['v'])], value=n['v'], point=1, shift=n['op'] * n['z'])


perf('shift_dec_model', lambda n: ('%s كم يصير العدد بعد أن ينتقل في جدول المنازل؟' % eq(shift_dec(n)[0].replace(' = ' + BOX, '')),
                                   '%s What does the number become after it moves in the place value table?' % eq(shift_dec(n)[0].replace(' = ' + BOX, '')),
                                   shift_dec(n)[1], shift_model(n)),
     lambda n: shift_dec(n)[1], D723, 'منزلق المنازل', lambda n: ['S', n['v'], n['z'], n['op']])
perf('shift_dec', lambda n: plain(*shift_dec(n)), lambda n: shift_dec(n)[1], D723, 'بلا نموذج',
     lambda n: ['S', n['v'], n['z'], n['op']])
D724 = [dict(v=v, k=k) for v in range(101, 1000, 11) if v % 10 and v // 10 % 10 for k in range(3)]


def thou_text(n):
    v, k = n['v'], n['k']
    parts = [dtext(*[(d['n'], d['s']) for d in [dec(int(c) * 10 ** (2 - j), 3)]][0]) for j, c in enumerate(str(v).rjust(3, '0'))]
    shown = [p if j != k else BOX for j, p in enumerate(parts)]
    return '%s = %s' % (dtext(v, 3), ' + '.join(shown)), dec(int(str(v).rjust(3, '0')[k]) * 10 ** (2 - k), 3)


perf('thou_read', lambda n: ('ما العدد العشري؟ %s جزءًا من ألف' % n['v'] if 11 <= n['v'] % 100 <= 99 else 'ما العدد العشري؟ %d من ألف' % n['v'],
                             'What decimal is %d thousandths?' % n['v'], dec(n['v'], 3), None),
     lambda n: dec(n['v'], 3), [d for d in D724 if d['k'] == 0], 'مكعب الألف، جدول المنازل', lambda n: ['T', n['v']])
perf('thou_decomp', lambda n: plain(*thou_text(n)), lambda n: thou_text(n)[1], D724, 'بلا نموذج', lambda n: ['T', n['v'], n['k']])
D731 = [dict(a=a, b=b) for a in range(12, 100, 3) for b in range(11, 100, 4) if a % 10 + b % 10 > 10 and a % 10 and b % 10 and a + b < 1000]


def dsum_step(n):
    a, b = n['a'], n['b']
    c = 10 - a % 10
    return '%s + %s = %s + %s + %s' % (dtext(a, 1), dtext(b, 1), dtext(a, 1), dtext(c, 1), BOX), dec(b - c, 1)


perf('dadd_step', lambda n: plain(*dsum_step(n)), lambda n: dsum_step(n)[1], D731, 'خط أعداد بالأعشار',
     lambda n: ['D', min(n['a'], n['b']), max(n['a'], n['b'])])
perf('dadd', lambda n: plain('%s + %s = %s' % (dtext(n['a'], 1), dtext(n['b'], 1), BOX), dec(n['a'] + n['b'], 1)),
     lambda n: dec(n['a'] + n['b'], 1), D731, 'بلا نموذج', lambda n: ['D', min(n['a'], n['b']), max(n['a'], n['b'])])
CTX_DADD = [('طول الحبل الأول {a} متر، والثاني {b} متر. كم طولهما معًا بالمتر؟',
             'One rope is {a} m long and another is {b} m. How long are they together?')]
perf('ctx_dadd', lambda n: ctx(CTX_DADD, dict(n, c=0), dec(n['a'] + n['b'], 1), a=dtext(n['a'], 1), b=dtext(n['b'], 1)),
     lambda n: dec(n['a'] + n['b'], 1), D731, 'صورة الموقف، والنص منطوق', lambda n: ['D', min(n['a'], n['b']), max(n['a'], n['b'])])
D732 = [dict(a=a, b=b) for a in range(21, 100, 2) for b in range(9, a - 5, 10) if b % 10 == 9]


def dsub_step(n):
    a, b = n['a'], n['b']
    return '%s %s %s = %s %s %d + %s' % (dtext(a, 1), MINUS, dtext(b, 1), dtext(a, 1), MINUS, (b + 1) // 10, BOX), dec(1, 1)


perf('dsub_step', lambda n: plain(*dsub_step(n)), lambda n: dec(1, 1), D732, 'خط أعداد بالأعشار', lambda n: ['-D', n['a'], n['b']])
perf('dsub', lambda n: plain('%s %s %s = %s' % (dtext(n['a'], 1), MINUS, dtext(n['b'], 1), BOX), dec(n['a'] - n['b'], 1)),
     lambda n: dec(n['a'] - n['b'], 1), D732, 'بلا نموذج', lambda n: ['-D', n['a'], n['b']])
CTX_DSUB = [('كان مع منى {a} لتر من العصير، فشربوا {b} لتر. كم لترًا بقي؟',
             'Mona had {a} litres of juice and they drank {b}. How many litres are left?')]
perf('ctx_dsub', lambda n: ctx(CTX_DSUB, dict(n, c=0), dec(n['a'] - n['b'], 1), a=dtext(n['a'], 1), b=dtext(n['b'], 1)),
     lambda n: dec(n['a'] - n['b'], 1), D732, 'صورة الموقف، والنص منطوق', lambda n: ['-D', n['a'], n['b']])
D733 = [dict(p=p, m=m) for m in (5, 10, 20) for p in range(105, m * 100, 37) if p % 5 == 0 and p % 100]


def money(p):
    return dict(t='money', p=p)


perf('change_step', lambda n: ('من %s جنيه إلى %s: كم قرشًا؟' % (dtext(n['p'], 2), cnt(n['p'] // 100 + 1, 'جنيه', 'جنيهين', 'جنيهات', 'جنيهًا')),
                               'From %s pounds to %d pounds: how many piastres?' % (dtext(n['p'], 2), n['p'] // 100 + 1),
                               100 - n['p'] % 100, None),
     lambda n: 100 - n['p'] % 100, D733, 'النقود', lambda n: ['$', n['p'], n['m']])
perf('change_money', lambda n: ('%s اكتب الباقي جنيهات وقروشًا.' % eq('%d %s %s = %s' % (n['m'], MINUS, dtext(n['p'], 2), BOX)),
                                '%s Write the change in pounds and piastres.' % eq('%d %s %s = %s' % (n['m'], MINUS, dtext(n['p'], 2), BOX)),
                                money(n['m'] * 100 - n['p']), None),
     lambda n: money(n['m'] * 100 - n['p']), D733, 'بلا نموذج', lambda n: ['$', n['p'], n['m']])
CTX_CHANGE7 = [('ثمن العصير {p} جنيه، ودفعنا {m} جنيهات. كم الباقي؟', 'Juice costs {p} pounds and we pay {m} pounds. How much change?'),
               ('ثمن الكراسة {p} جنيه، ومعنا ورقة {m} جنيهات. كم يعيد البائع؟', 'A notebook costs {p} pounds and we pay with {m} pounds. How much change?')]
perf('ctx_change_money', lambda n: ctx(CTX_CHANGE7, dict(n, c=n['p'] % 2), money(n['m'] * 100 - n['p']), p=dtext(n['p'], 2), m=n['m']),
     lambda n: money(n['m'] * 100 - n['p']), [d for d in D733 if d['m'] == 5 or d['m'] == 10], 'صورة الموقف، والنص منطوق',
     lambda n: ['$', n['p'], n['m']])
EQUIV = {(1, 2): (50, '50%'), (1, 4): (25, '25%'), (3, 4): (75, '75%'), (1, 10): (10, '10%'), (1, 5): (20, '20%'),
         (2, 5): (40, '40%'), (1, 8): (125, '12.5%'), (3, 8): (375, '37.5%'), (3, 10): (30, '30%')}
D741 = [dict(n=a, d=b, f=f) for (a, b) in [(1, 2), (1, 4), (3, 4), (1, 10)] for f in range(3)]
D742 = [dict(n=a, d=b, f=f) for (a, b) in [(1, 5), (2, 5), (1, 8), (3, 8), (3, 4)] for f in range(3)]


def eq_forms(a, b):
    """صيغ الكسر الثلاث: الكسر، والعشري، والنسبة المئوية."""
    v, pct = EQUIV[(a, b)]
    s = 3 if (a, b) in ((1, 8), (3, 8)) else 2
    return ['%d/%d' % (a, b), dtext(v, s).rstrip('0').rstrip('.') if '.' in dtext(v, s) else dtext(v, s), pct]


def eq_cards(n):
    """البطاقات: الصيغة المطلوبة للكسر، ومشتّتان من صيغ كسور أخرى بالنوع نفسه."""
    forms = eq_forms(n['n'], n['d'])
    want = (n['f'] + 1) % 3
    others = [k for k in EQUIV if k != (n['n'], n['d'])]
    picks = [others[(n['n'] * 3 + n['d'] + j * 2) % len(others)] for j in range(2)]
    if picks[0] == picks[1]:
        picks[1] = others[(others.index(picks[0]) + 1) % len(others)]
    labels = {'A': forms[want], 'B': eq_forms(*picks[0])[want], 'C': eq_forms(*picks[1])[want]}
    order = ['A', 'B', 'C'][n['f']:] + ['A', 'B', 'C'][:n['f']]
    return order, labels


def eq_cells(a, b):
    """خلايا شبكة المئة الملوّنة للكسر: نسبته المئوية، ونصف خلية للثُمن (12.5)."""
    v, pct = EQUIV[(a, b)]
    return float(pct[:-1]) if '.' in pct else int(pct[:-1])


perf('equiv_forms_grid', lambda n: ('الملوّن %s من الشبكة. أي البطاقات تساويه؟' % eq(eq_forms(n['n'], n['d'])[n['f']]),
                                    'The coloured part is %s of the grid. Which card equals it?' % eq(eq_forms(n['n'], n['d'])[n['f']]),
                                    'A', dict(kind='grid100', n=eq_cells(n['n'], n['d']))),
     lambda n: 'A', lambda skill: D741 if skill == '7-4-1' else D742, 'شبكة المئة',
     lambda n: ['=', n['n'], n['d'], n['f']], cards=eq_cards)
perf('equiv_forms', lambda n: ('أي البطاقات تساوي %s؟' % eq(eq_forms(n['n'], n['d'])[n['f']]),
                               'Which card equals %s?' % eq(eq_forms(n['n'], n['d'])[n['f']]), 'A', None),
     lambda n: 'A', lambda skill: D741 if skill == '7-4-1' else D742, 'بلا نموذج',
     lambda n: ['=', n['n'], n['d'], n['f']], cards=eq_cards)
D743 = [dict(a=a, d=d, w=d * q) for (a, d) in [(1, 2), (1, 4), (3, 4), (1, 5), (2, 5), (1, 10), (3, 10)] for q in range(2, 21) if d * q <= 200]


def dec_of(a, d):
    v, _p = EQUIV[(a, d)]
    return dtext(v, 3 if (a, d) in ((1, 8), (3, 8)) else 2).rstrip('0').rstrip('.')


perf('use_equiv_step', lambda n: ('%s هي %s، فـ%s = %s %d = %s' % (eq(dec_of(n['a'], n['d'])), WORDS[(n['a'], n['d'])][0],
                                                                eq('%s %s %d' % (dec_of(n['a'], n['d']), TIMES, n['w'])), of(n['a'], n['d']), n['w'], BOX),
                                  '%s is %s, so %s = %s of %d = %s' % (eq(dec_of(n['a'], n['d'])), WORDS[(n['a'], n['d'])][1],
                                                                     eq('%s %s %d' % (dec_of(n['a'], n['d']), TIMES, n['w'])), WORDS[(n['a'], n['d'])][1], n['w'], BOX),
                                  n['w'] // n['d'] * n['a'], None),
     lambda n: n['w'] // n['d'] * n['a'], D743, 'شريط مقسّم', lambda n: ['U', n['a'], n['d'], n['w']])
perf('use_equiv', lambda n: plain('%s %s %d = %s' % (dec_of(n['a'], n['d']), TIMES, n['w'], BOX), n['w'] // n['d'] * n['a']),
     lambda n: n['w'] // n['d'] * n['a'], D743, 'بلا نموذج', lambda n: ['U', n['a'], n['d'], n['w']])
D751 = [dict(p=p, w=w) for p in (10, 1, 5) for w in range(20, 1000, 20) if w * p % 100 == 0]
perf('pct_strip', lambda n: ('%s من %d = %s' % ('%d%%' % n['p'], n['w'], BOX), '%d%% of %d = %s' % (n['p'], n['w'], BOX),
                             n['w'] * n['p'] // 100, None),
     lambda n: n['w'] * n['p'] // 100, D751, 'شريط بلبنات', lambda n: ['%', n['p'], n['w']])
D752 = [dict(p=p, w=w) for p in (15, 20, 25, 30, 35, 45, 60, 75) for w in range(20, 1000, 20) if w * p % 100 == 0 and w % 10 == 0]


def pct_step(n):
    p, w = n['p'], n['w']
    ten = w // 10
    if p % 10 == 5:                                         # 15% = 10% + 5%
        return '%d%% من %d = %d + %s' % (p, w, ten * (p // 10), BOX), ten // 2
    return '%d%% من %d = %d %s %s' % (p, w, ten, TIMES, BOX), p // 10


perf('pct_step', lambda n: (eq(pct_step(n)[0]), eq(pct_step(n)[0].replace('من', 'of')), pct_step(n)[1], None),
     lambda n: pct_step(n)[1], [d for d in D752 if (d['w'] // 10) % 2 == 0 or d['p'] % 10 == 0], 'شريط بلبنات',
     lambda n: ['%', n['p'], n['w']])
perf('pct', lambda n: ('%d%% من %d = %s' % (n['p'], n['w'], BOX), '%d%% of %d = %s' % (n['p'], n['w'], BOX), n['w'] * n['p'] // 100, None),
     lambda n: n['w'] * n['p'] // 100, D752, 'بلا نموذج', lambda n: ['%', n['p'], n['w']])
CTX_PCT = [('في المدرسة {w} طالبًا، {p}% منهم يلعبون الكرة. كم طالبًا يلعب الكرة؟',
            'A school has {w} students and {p}% play football. How many play football?')]
perf('ctx_pct', lambda n: ctx(CTX_PCT, dict(n, c=0), n['w'] * n['p'] // 100, w=n['w'], p=n['p']), lambda n: n['w'] * n['p'] // 100,
     [d for d in D752 if d['w'] >= 100 and d['w'] % 100 >= 11], 'صورة الموقف، والنص منطوق', lambda n: ['%', n['p'], n['w']])
D761 = [dict(p=p, w=w, op=op) for p in (10, 20, 25, 50) for w in range(40, 1000, 30) if w * p % 100 == 0 for op in (1, -1)]


def disc(n):
    return n['w'] + n['op'] * n['w'] * n['p'] // 100


perf('disc_step', lambda n: (('خصم %d%% من %d: الخصم %s' if n['op'] < 0 else 'زيادة %d%% على %d: الزيادة %s') % (n['p'], n['w'], BOX),
                             ('%d%% off %d: the discount is %s' if n['op'] < 0 else '%d%% more on %d: the increase is %s') % (n['p'], n['w'], BOX),
                             n['w'] * n['p'] // 100, None),
     lambda n: n['w'] * n['p'] // 100, D761, 'شريط قبل وبعد', lambda n: ['$%', n['p'], n['w'], n['op']])
perf('disc', lambda n: (('ثمن قبل الخصم %d، والخصم %d%%. كم الثمن بعده؟' if n['op'] < 0 else 'ثمن %d زاد %d%%. كم صار؟') % (n['w'], n['p']),
                        ('Price %d with %d%% off. What is the new price?' if n['op'] < 0 else 'Price %d goes up by %d%%. What is it now?') % (n['w'], n['p']),
                        disc(n), None),
     disc, D761, 'بلا نموذج', lambda n: ['$%', n['p'], n['w'], n['op']])
CTX_DISC = [('ثمن القميص بالجنيه {w}، وعليه خصم {p}%. كم جنيهًا ندفع؟', 'A shirt costs {w} pounds with {p}% off. How much do we pay?')]
perf('ctx_disc', lambda n: ctx(CTX_DISC, dict(n, c=0), disc(n), w=n['w'], p=n['p']), disc,
     [d for d in D761 if d['op'] < 0 and d['w'] >= 100 and (d['w'] - d['w'] * d['p'] // 100) % 100 >= 11], 'صورة الموقف، والنص منطوق', lambda n: ['$%', n['p'], n['w'], n['op']])
D762 = [dict(a=a, b=b) for a in (4, 8, 12, 16, 20, 24, 28, 32, 36, 44, 48) for b in (25, 50) if a != b]
perf('pct_swap', lambda n: ('%d%% من %d = %s' % (n['a'], n['b'], BOX), '%d%% of %d = %s' % (n['a'], n['b'], BOX), n['a'] * n['b'] // 100, None),
     lambda n: n['a'] * n['b'] // 100, D762, 'شبكة المئة', lambda n: ['%s', n['a'], n['b']])
perf('judge_pct_swap', lambda n: ('هل هذا صحيح؟ ' + eq('%d%% من %d = %d%% من %d' % (n['a'], n['b'], n['b'], n['a'] + n['w'])),
                                    'Is this true? ' + eq('%d%% of %d = %d%% of %d' % (n['a'], n['b'], n['b'], n['a'] + n['w'])),
                                    'yes' if n['w'] == 0 else 'no', None),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D762 for w in (0, 2)], 'بلا نموذج',
     lambda n: ['%s', n['a'], n['b']], cards='yesno')
D763 = ([dict(a=a, b=b, f=0) for a in range(1, 10) for b in range(1, 10)] + [dict(a=a, b=b, f=1) for a in (15, 25, 5) for b in range(2, 50, 2)])


def dmul(n):
    if n['f'] == 0:
        return '0.%d %s 0.%d = %s' % (n['a'], TIMES, n['b'], BOX), dec(n['a'] * n['b'], 2)
    return '%s %s %d = %s' % (dtext(n['a'], 1), TIMES, n['b'], BOX), dec(n['a'] * n['b'], 1)


perf('dmul_model', lambda n: ('%s مربع الوحدة: كم الجزء المظلّل؟' % eq(dmul(n)[0].replace(' = ' + BOX, '')),
                              '%s In the unit square, how much is shaded?' % eq(dmul(n)[0].replace(' = ' + BOX, '')),
                              dmul(n)[1], dict(kind='grid100', n=n['a'] * n['b'], ra=n['a'], rb=n['b'])),
     lambda n: dmul(n)[1], [d for d in D763 if d['f'] == 0], 'مربع الوحدة', lambda n: ['M', n['a'], n['b'], n['f']])
perf('dmul', lambda n: plain(*dmul(n)), lambda n: dmul(n)[1], D763, 'بلا نموذج', lambda n: ['M', n['a'], n['b'], n['f']])
perf('judge_dmul', lambda n: judge('0.%d %s 0.%d = %s' % (n['a'], TIMES, n['b'], dtext(n['a'] * n['b'], 2) if n['w'] == 0 else dtext(n['a'] * n['b'], 1)),
                                   n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D763 if d['f'] == 0 and d['a'] * d['b'] % 10 for w in (0, 1)],
     'بلا نموذج', lambda n: ['M', n['a'], n['b'], 0], cards='yesno')
D764 = [dict(a=a, h=h) for a in range(3, 60) for h in (2, 4) if a * h < 200]
perf('div_half_strip', lambda n: ('%s في كل واحد %s. كم؟' % (eq('%d %s %s' % (n['a'], DIV, '0.5' if n['h'] == 2 else '0.25')),
                                                              'نصفان' if n['h'] == 2 else 'أربعة أرباع'),
                                  '%s Each one has %s. How many?' % (eq('%d %s %s' % (n['a'], DIV, '0.5' if n['h'] == 2 else '0.25')),
                                                                     'two halves' if n['h'] == 2 else 'four quarters'),
                                  n['a'] * n['h'], dict(kind='fstrip', n=n['h'], d=n['h'], times=n['a'])),
     lambda n: n['a'] * n['h'], D764, 'شريط مقسّم', lambda n: ['H', n['a'], n['h']])
perf('div_half', lambda n: plain('%d %s %s = %s' % (n['a'], DIV, '0.5' if n['h'] == 2 else '0.25', BOX), n['a'] * n['h']),
     lambda n: n['a'] * n['h'], D764, 'بلا نموذج', lambda n: ['H', n['a'], n['h']])
perf('judge_div_half', lambda n: judge('%d %s %s = %d' % (n['a'], DIV, '0.5' if n['h'] == 2 else '0.25',
                                                         n['a'] * n['h'] if n['w'] == 0 else (n['a'] // n['h'] if n['a'] % n['h'] == 0 else n['a'] * n['h'] + 1)),
                                       n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D764 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['H', n['a'], n['h']], cards='yesno')
NOTSIMP = lambda n: True
SKILLS.update({
    '7-1-1': S(['ف1', 'ف5'], {'ف1': 'frac_strip', 'ف5': 'judge_frac_strip', 'solve': 'frac_words'},
               [(5, 'كسر الواحد', lambda n: n['n'] == 1), (5, 'بسط أكبر من 1', lambda n: n['n'] > 1)]),
    '7-1-2': S(['ف1', 'ف5'], {'ف1': 'equiv_strip', 'ف5': 'judge_equiv', 'solve': 'equiv'},
               [(5, 'المقام يتضاعف', lambda n: n['k'] == 2), (5, 'المقام ثلاثة أمثاله أو أربعة', lambda n: n['k'] > 2)]),
    '7-1-3': S(['ف1', 'ف3', 'ف4'], {'ف1': 'unit_frac_strip', 'ف3': 'unit_frac', 'ف4': 'ctx_unit_frac', 'solve': 'unit_frac'},
               [(5, 'النصف والربع والثمن', lambda n: n['d'] in (2, 4, 8)), (5, 'الثلث والخمس والسدس والعشر', lambda n: n['d'] in (3, 5, 6, 10))]),
    '7-1-4': S(['ف2', 'ف3', 'ف4'], {'ف2': 'frac_of_step', 'ف3': 'frac_of', 'ف4': 'ctx_frac_of', 'solve': 'frac_of'},
               [(5, 'المقام حتى 5', lambda n: n['d'] <= 5), (5, 'المقام فوق 5', lambda n: n['d'] > 5)]),
    '7-1-5': S(['ف1', 'ف3'], {'ف1': 'frac_add_strip', 'ف3': 'frac_add', 'solve': 'frac_add'},
               [(6, 'جمع بمقامات مترابطة', lambda n: n['op'] > 0), (4, 'المتمم إلى الواحد', lambda n: n['op'] < 0)]),
    '7-2-1': S(['ف1', 'ف3'], {'ف1': 'grid100', 'ف3': 'pounds_dec', 'solve': 'pounds_dec'},
               [(5, 'القروش حتى 50', lambda n: n['v'] % 100 <= 50), (5, 'القروش فوق 50', lambda n: n['v'] % 100 > 50)]),
    '7-2-2': S(['ف1', 'ف5'], {'ف1': 'dec_compare_grid', 'ف5': 'dec_compare', 'solve': 'dec_compare'},
               [(5, 'الأعشار أكبر رغم قصر الرقم', lambda n: n['a'] * 10 > n['b']), (5, 'الأجزاء من مئة أكبر', lambda n: n['a'] * 10 < n['b'])]),
    '7-2-3': S(['ف1', 'ف3'], {'ف1': 'shift_dec_model', 'ف3': 'shift_dec', 'solve': 'shift_dec'},
               [(5, 'ضرب', lambda n: n['op'] > 0), (5, 'قسمة', lambda n: n['op'] < 0)]),
    '7-2-4': S(['ف1', 'ف3'], {'ف1': 'thou_read', 'ف3': 'thou_decomp', 'solve': 'thou_decomp'},
               [(4, 'الأعشار', lambda n: n['k'] == 0), (3, 'الأجزاء من مئة', lambda n: n['k'] == 1), (3, 'الأجزاء من ألف', lambda n: n['k'] == 2)]),
    '7-3-1': S(['ف2', 'ف3', 'ف4'], {'ف2': 'dadd_step', 'ف3': 'dadd', 'ف4': 'ctx_dadd', 'solve': 'dadd'},
               [(5, 'المجموع أقل من 10', lambda n: n['a'] + n['b'] < 100), (5, 'المجموع 10 فأكثر', lambda n: n['a'] + n['b'] >= 100)]),
    '7-3-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'dsub_step', 'ف3': 'dsub', 'ف4': 'ctx_dsub', 'solve': 'dsub'},
               [(5, 'يطرح 0.9 أو 1.9', lambda n: n['b'] <= 19), (5, 'يطرح 2.9 فأكثر', lambda n: n['b'] > 19)]),
    '7-3-3': S(['ف2', 'ف3', 'ف4'], {'ف2': 'change_step', 'ف3': 'change_money', 'ف4': 'ctx_change_money', 'solve': 'change_money'},
               [(3, 'من 5 جنيهات', lambda n: n['m'] == 5), (4, 'من 10 جنيهات', lambda n: n['m'] == 10), (3, 'من 20 جنيهًا', lambda n: n['m'] == 20)]),
    '7-4-1': S(['ف1', 'ف3'], {'ف1': 'equiv_forms_grid', 'ف3': 'equiv_forms', 'solve': 'equiv_forms'},
               [(4, 'من الكسر', lambda n: n['f'] == 0), (3, 'من العشري', lambda n: n['f'] == 1), (3, 'من النسبة المئوية', lambda n: n['f'] == 2)]),
    '7-4-2': S(['ف1', 'ف3'], {'ف1': 'equiv_forms_grid', 'ف3': 'equiv_forms', 'solve': 'equiv_forms'},
               [(4, 'من الكسر', lambda n: n['f'] == 0), (3, 'من العشري', lambda n: n['f'] == 1), (3, 'من النسبة المئوية', lambda n: n['f'] == 2)]),
    '7-4-3': S(['ف2', 'ف3'], {'ف2': 'use_equiv_step', 'ف3': 'use_equiv', 'solve': 'use_equiv'},
               [(5, 'النصف والربع وثلاثة الأرباع', lambda n: n['d'] in (2, 4)), (5, 'الخمس والعشر', lambda n: n['d'] in (5, 10))]),
    '7-5-1': S(['ف1', 'ف3'], {'ف1': 'pct_strip', 'ف3': 'pct_strip', 'solve': 'pct_strip'},
               [(4, '10%', lambda n: n['p'] == 10), (3, '5%', lambda n: n['p'] == 5), (3, '1%', lambda n: n['p'] == 1)]),
    '7-5-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'pct_step', 'ف3': 'pct', 'ف4': 'ctx_pct', 'solve': 'pct'},
               [(5, 'مضاعف 10%', lambda n: n['p'] % 10 == 0), (5, 'فيها 5%', lambda n: n['p'] % 10 == 5)]),
    '7-6-1': S(['ف2', 'ف3', 'ف4'], {'ف2': 'disc_step', 'ف3': 'disc', 'ف4': 'ctx_disc', 'solve': 'disc'},
               [(6, 'خصم', lambda n: n['op'] < 0), (4, 'زيادة', lambda n: n['op'] > 0)]),
    '7-6-2': S(['ف3', 'ف5'], {'ف3': 'pct_swap', 'ف5': 'judge_pct_swap', 'solve': 'pct_swap'},
               [(5, 'من 25', lambda n: n['b'] == 25), (5, 'من 50', lambda n: n['b'] == 50)]),
    '7-6-3': S(['ف1', 'ف3', 'ف5'], {'ف1': 'dmul_model', 'ف3': 'dmul', 'ف5': 'judge_dmul', 'solve': 'dmul'},
               [(5, 'عشري في عشري', lambda n: n['f'] == 0), (5, 'عشري في عدد', lambda n: n['f'] == 1)]),
    '7-6-4': S(['ف1', 'ف3', 'ف5'], {'ف1': 'div_half_strip', 'ف3': 'div_half', 'ف5': 'judge_div_half', 'solve': 'div_half'},
               [(5, 'على نصف', lambda n: n['h'] == 2), (5, 'على ربع', lambda n: n['h'] == 4)]),
})


# ---------------------------------------------------------------- المرحلة 8: المستوى المتقدم والتحقق
# كل اختصار يُعلَّم بعد نموذجه (صدر المرحلة في الخريطة): ف1 مستطيل grid بأجزاء أضلاعه، والمجهول ناتجه
D811 = [dict(t=t) for t in range(1, 10)]
perf('sq5_model', lambda n: ('%s كم مساحة المربع؟' % eq('%d5 %s %d5' % (n['t'], TIMES, n['t'])),
                             '%s What is the area of the square?' % eq('%d5 %s %d5' % (n['t'], TIMES, n['t'])),
                             (10 * n['t'] + 5) ** 2, dict(kind='grid', top=[10 * n['t'], 5], side=[10 * n['t'], 5])),
     lambda n: (10 * n['t'] + 5) ** 2, D811, 'مربع بأربع مناطق ينتقل منه شريط', lambda n: ['²', 10 * n['t'] + 5, 1])
perf('sq5_step', lambda n: plain('%d5 %s %d5 = %d %s %d + %s' % (n['t'], TIMES, n['t'], 10 * n['t'], TIMES, 10 * n['t'] + 10, BOX), 25),
     lambda n: 25, D811, 'بلا نموذج', lambda n: ['²', 10 * n['t'] + 5, 2])
perf('sq5', lambda n: plain('%d5 %s %d5 = %s' % (n['t'], TIMES, n['t'], BOX), (10 * n['t'] + 5) ** 2),
     lambda n: (10 * n['t'] + 5) ** 2, D811, 'بلا نموذج', lambda n: ['²', 10 * n['t'] + 5, 3])
D812 = [dict(t=t, s=s) for t in range(2, 10) for s in (1, -1)]


def nb_sq(n):
    t, s = n['t'], n['s']
    a = 10 * t + s
    if s > 0:                                               # ⁦ 31 × 31 = 900 + 30 + 31 ⁩
        return '%d %s %d = %d + %d + %s' % (a, TIMES, a, 100 * t * t, 10 * t, BOX), a
    return '%d %s %d = %d %s %d %s %s' % (a, TIMES, a, 100 * t * t, MINUS, 10 * t, MINUS, BOX), a   # ⁦ 29 × 29 = 900 − 30 − 29 ⁩


perf('nb_sq_step', lambda n: plain(*nb_sq(n)), lambda n: 10 * n['t'] + n['s'], D812, 'مربع وشريطان', lambda n: ['²', 10 * n['t'] + n['s'], 2])
perf('nb_sq', lambda n: plain('%d %s %d = %s' % (10 * n['t'] + n['s'], TIMES, 10 * n['t'] + n['s'], BOX), (10 * n['t'] + n['s']) ** 2),
     lambda n: (10 * n['t'] + n['s']) ** 2, D812, 'بلا نموذج', lambda n: ['²', 10 * n['t'] + n['s'], 3])
D813 = [dict(a=a) for a in range(12, 100) if a % 10 not in (0, 5)]
perf('sq_step', lambda n: plain('%d %s %d = %d + %d + %s' % (n['a'], TIMES, n['a'], (n['a'] // 10 * 10) ** 2, 2 * (n['a'] // 10 * 10) * (n['a'] % 10), BOX),
                                (n['a'] % 10) ** 2),
     lambda n: (n['a'] % 10) ** 2, D813, 'مربع بأربع مناطق', lambda n: ['²', n['a'], 2])
perf('sq_gen', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['a'], BOX), n['a'] ** 2), lambda n: n['a'] ** 2, D813,
     'بلا نموذج', lambda n: ['²', n['a'], 3])
perf('judge_sq', lambda n: judge('%d %s %d = %d + %d' % (n['a'], TIMES, n['a'], (n['a'] // 10 * 10) ** 2, (n['a'] % 10) ** 2)
                                 if n['w'] else '%d %s %d = %d' % (n['a'], TIMES, n['a'], n['a'] ** 2), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D813 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['²', n['a'], 3], cards='yesno')
D821 = [dict(m=m, d=d) for m in range(20, 100, 10) for d in range(1, 6) if m - d > 10]
perf('dsq_model', lambda n: ('%s نقصّ شريطًا وننقله فيصير مربعًا ينقصه ركن. كم المساحة؟' % eq('%d %s %d' % (n['m'] - n['d'], TIMES, n['m'] + n['d'])),
                             '%s Cut a strip and move it: a square missing a corner. What is the area?' % eq('%d %s %d' % (n['m'] - n['d'], TIMES, n['m'] + n['d'])),
                             n['m'] ** 2 - n['d'] ** 2, dict(kind='grid', top=[n['m']], side=[n['m']], corner=n['d'])),
     lambda n: n['m'] ** 2 - n['d'] ** 2, D821, 'مربع يُقصّ منه شريط ويُنقل', lambda n: ['D²', n['m'], n['d']])
perf('dsq_step', lambda n: plain('%d %s %d = %d %s %d %s %s' % (n['m'] - n['d'], TIMES, n['m'] + n['d'], n['m'], TIMES, n['m'], MINUS, BOX),
                                 n['d'] ** 2),
     lambda n: n['d'] ** 2, D821, 'بلا نموذج', lambda n: ['D²', n['m'], n['d']])
perf('dsq', lambda n: plain('%d %s %d = %s' % (n['m'] - n['d'], TIMES, n['m'] + n['d'], BOX), n['m'] ** 2 - n['d'] ** 2),
     lambda n: n['m'] ** 2 - n['d'] ** 2, D821, 'بلا نموذج', lambda n: ['D²', n['m'], n['d']])
perf('judge_dsq', lambda n: judge('%d %s %d = %d' % (n['m'] - n['d'], TIMES, n['m'] + n['d'], n['m'] ** 2 - n['d'] ** 2 * (1 if n['w'] == 0 else -1)),
                                  n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D821 for w in (0, 1)], 'بلا نموذج',
     lambda n: ['D²', n['m'], n['d']], cards='yesno')
MODEL_OK['grid'] = (lambda old: lambda m, n, ans: (sum(m['top']) * sum(m['side']) - m['corner'] ** 2 == ans) if m.get('corner')
                    else old(m, n, ans))(MODEL_OK['grid'])
D831 = [dict(a=a, b=b) for a in range(90, 100) for b in range(90, 100) if a <= b and (100 - a) * (100 - b) < 100]
D832 = [dict(a=a, b=b) for a in range(80, 95) for b in range(80, 95) if a <= b and (100 - a) * (100 - b) >= 100]


def near100(n):
    a, b = n['a'], n['b']
    da, db = a - 100, b - 100
    base = a + db
    if da * db >= 0:
        return '%d %s %d = 100 %s %d + %s' % (a, TIMES, b, TIMES, base, BOX), da * db
    return '%d %s %d = 100 %s %d %s %s' % (a, TIMES, b, TIMES, base, MINUS, BOX), -da * db


perf('n100_model', lambda n: ('%s مساحة مئة في مئة يُنزع منها شريطان ويُعاد الركن. كم المساحة؟' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                              '%s A 100 by 100 square with two strips removed and the corner put back. What is the area?' % eq('%d %s %d' % (n['a'], TIMES, n['b'])),
                              n['a'] * n['b'], dict(kind='grid', top=[n['a'], 100 - n['a']], side=[n['b'], 100 - n['b']], keep=1)),
     lambda n: n['a'] * n['b'], D831, 'مساحة مئة في مئة يُنزع منها شريطان ويُعاد الركن', fact_mul)
MODEL_OK['grid'] = (lambda old: lambda m, n, ans: (m['top'][0] * m['side'][0] == ans) if m.get('keep') else old(m, n, ans))(MODEL_OK['grid'])
perf('n100_step', lambda n: plain(*near100(n)), lambda n: abs((n['a'] - 100) * (n['b'] - 100)),
     lambda skill: {'8-3-1': D831, '8-3-2': D832}.get(skill, D833), 'بلا نموذج', fact_mul)
perf('n100', lambda n: plain('%d %s %d = %s' % (n['a'], TIMES, n['b'], BOX), n['a'] * n['b']), lambda n: n['a'] * n['b'],
     lambda skill: {'8-3-1': D831, '8-3-2': D832}.get(skill, D833), 'بلا نموذج', fact_mul)
D833 = ([dict(a=a, b=b) for a in range(101, 110) for b in range(101, 110) if a <= b]
        + [dict(a=a, b=b) for a in range(101, 109) for b in range(91, 100)])
perf('judge_n100', lambda n: judge(near100(n)[0].replace(BOX, str(near100(n)[1] + (0 if n['w'] == 0 else 10))), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in D833 for w in (0, 1)], 'بلا نموذج', fact_mul, cards='yesno')
# 8-4: التحقق. ف5: هل يمكن أن يكون الناتج المعروض صحيحًا؟ يُرفض إن خالف الرقم الأخير أو التقدير
D841 = [dict(a=a, b=b, w=w) for a in range(112, 999, 37) for b in range(12, 99, 7) if a % 10 and b % 10 for w in range(3)]


def shown841(n):
    p = n['a'] * n['b']
    return [p, p + (1 if p % 10 != 9 else -1), p * 10 + p % 10][n['w']]   # صحيح، رقم أخير خاطئ، تقدير بعيد


perf('check_last', lambda n: ('هل يمكن أن يكون %s؟' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], shown841(n))),
                              'Could %s be right?' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], shown841(n))),
                              'yes' if n['w'] == 0 else 'no', None),
     lambda n: 'yes' if n['w'] == 0 else 'no', D841, 'بلا نموذج', lambda n: ['?', n['a'], n['b'], n['w']], cards='yesno')
perf('judge_check_last', lambda n: ('%s يُرفض لأن رقمه الأخير لا يوافق. هل هذا صحيح؟' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], shown841(n))),
                                    '%s is rejected because its last digit does not match. Is this true?' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], shown841(n))),
                                    'yes' if n['w'] == 1 else 'no', None),
     lambda n: 'yes' if n['w'] == 1 else 'no', D841, 'بلا نموذج', lambda n: ['?', n['a'], n['b'], n['w'], 'r'], cards='yesno')
D842 = [dict(a=a, b=b, w=w) for a in range(112, 999, 41) for b in range(12, 99, 9) if a % 10 and b % 10 for w in (0, 1)]
perf('nine_rem', lambda n: ('ما باقي قسمة %d على 9؟' % n['a'], 'What is the remainder of %d divided by 9?' % n['a'], n['a'] % 9, None),
     lambda n: n['a'] % 9, [d for d in D842 if d['w'] == 0], 'مكعبات تُفكّ إلى 9 و1', lambda n: ['9', n['a']])
perf('nine_check', lambda n: ('هل يجتاز %s فحص التسعة؟' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], n['a'] * n['b'] + (0 if n['w'] == 0 else 1))),
                              'Does %s pass the nines check?' % eq('%d %s %d = %d' % (n['a'], TIMES, n['b'], n['a'] * n['b'] + (0 if n['w'] == 0 else 1))),
                              'yes' if n['w'] == 0 else 'no', None),
     lambda n: 'yes' if n['w'] == 0 else 'no', D842, 'بلا نموذج', lambda n: ['9?', n['a'], n['b'], n['w']], cards='yesno')
D843 = [dict(a=a, b=b, w=w) for a in range(112, 999, 53) for b in range(12, 99, 11) if a % 10 and b % 10 for w in (0, 90, 180)]
perf('check_limits', lambda n: ('الناتج %d عن %s يجتاز فحص الرقم الأخير وفحص التسعة. هل هو الناتج الصحيح؟' % (
    n['a'] * n['b'] + n['w'], eq('%d %s %d' % (n['a'], TIMES, n['b']))),
    'The answer %d to %s passes the last digit check and the nines check. Is it the correct answer?' % (
    n['a'] * n['b'] + n['w'], eq('%d %s %d' % (n['a'], TIMES, n['b']))), 'yes' if n['w'] == 0 else 'no', None),
     lambda n: 'yes' if n['w'] == 0 else 'no', D843, 'بلا نموذج', lambda n: ['L', n['a'], n['b'], n['w']], cards='yesno')
# 8-5: الحساب في الحياة
D851 = [dict(k=k, u=u, c=c) for k in range(2, 10) for u in range(12, 60) if k * u < 500 and (k * u) % 100 >= 11 for c in range(2)]
CTX_UNIT = [('سعر {k} كيلو من البرتقال بالجنيه {t}. كم سعر الكيلو؟', '{k} kg of oranges cost {t} pounds. What is the price of one kg?'),
            ('ثمن {k} كراسات بالجنيه {t}. كم ثمن الكراسة؟', '{k} notebooks cost {t} pounds. How much is one notebook?')]
perf('unit_price', lambda n: ctx(CTX_UNIT, n, n['u'], k=n['k'], t=n['k'] * n['u']), lambda n: n['u'], D851, 'خط مزدوج: كيلو وجنيه',
     lambda n: ['/', n['k'] * n['u'], n['k']])
D852 = [dict(h1=h1, m1=m1, h2=h2, m2=m2) for h1 in range(0, 4) for m1 in range(5, 60, 5) for h2 in range(1, 4) for m2 in range(5, 60, 10)
        if m1 + m2 >= 60 and h1 + h2 <= 6]


def dur_text(h, m, en=False):
    if en:
        return '%d h %d min' % (h, m)
    # منصوبة أو مجرورة في مواضعها كلها («نجمع ساعتين»، «سارت ساعتين»)
    return ' و'.join(x for x in (('ساعة' if h == 1 else cnt(h, 'ساعة', 'ساعتين', 'ساعات', 'ساعة', True)) if h else '',
                                 cnt(m, 'دقيقة', 'دقيقتين', 'دقائق', 'دقيقة', True)) if x)


perf('dur_add', lambda n: ('نجمع %s و%s. كم المدة كلها؟' % (dur_text(n['h1'], n['m1']), dur_text(n['h2'], n['m2'])),
                           '%s plus %s. What is the total time?' % (dur_text(n['h1'], n['m1'], True), dur_text(n['h2'], n['m2'], True)),
                           dict(t='dur', m=60 * (n['h1'] + n['h2']) + n['m1'] + n['m2']), None),
     lambda n: dict(t='dur', m=60 * (n['h1'] + n['h2']) + n['m1'] + n['m2']), D852, 'وجه الساعة', lambda n: ['t', n['h1'], n['m1'], n['h2'], n['m2']])
CTX_DUR = [('بدأت الرحلة وسارت {a}، ثم {b}. كم دامت؟', 'The trip lasted {ae}, then {be} more. How long in total?')]
perf('ctx_dur', lambda n: ctx(CTX_DUR, dict(n, c=0), dict(t='dur', m=60 * (n['h1'] + n['h2']) + n['m1'] + n['m2']),
                              a=dur_text(n['h1'], n['m1']), b=dur_text(n['h2'], n['m2']), ae=dur_text(n['h1'], n['m1'], True),
                              be=dur_text(n['h2'], n['m2'], True)),
     lambda n: dict(t='dur', m=60 * (n['h1'] + n['h2']) + n['m1'] + n['m2']), D852, 'صورة الموقف، والنص منطوق',
     lambda n: ['t', n['h1'], n['m1'], n['h2'], n['m2']])
D853 = [dict(v=v, t=t) for v in range(30, 130, 6) for t in (10, 15, 20, 30, 40, 45, 50) if v * t % 60 == 0]
CTX_RATE = [('سيارة سرعتها {v} كيلومترًا في الساعة سارت {t} دقيقة. كم كيلومترًا قطعت؟',
             'A car goes {v} km per hour for {t} minutes. How many km does it go?')]
perf('rate', lambda n: ctx(CTX_RATE, dict(n, c=0), n['v'] * n['t'] // 60, v=n['v'], t=n['t']), lambda n: n['v'] * n['t'] // 60,
     [d for d in D853 if d['v'] % 100 >= 11 and d['t'] >= 11], 'خط مزدوج: دقائق وكيلومترات', lambda n: ['v', n['v'], n['t']])
D854 = [dict(a=a, b=b) for a in range(12, 99) for b in range(21, 99, 4) if a % 10 and a // 10 % 10 for _ in [0] if b % 10]


def est854(n):
    return est(n['a'] * n['b'] // 10, rnd(n['a'], 10) // 10 * rnd(n['b'], 10), 15)


CTX_EST8 = [('ثمن العلبة {p} جنيه، واشترينا علبًا عددها {b}. كم جنيهًا ندفع تقريبًا؟',
             'A box costs {p} pounds and we buy {b} boxes. About how much do we pay?')]
perf('est_buy', lambda n: ctx(CTX_EST8, dict(n, c=0), est854(n), p=dtext(n['a'], 1), b=n['b']), est854, D854, 'بلا نموذج',
     lambda n: ['$e', n['a'], n['b']])
perf('judge_est_buy', lambda n: ('ثمن العلبة %s جنيه، وعددها %d. قال أحمد: ندفع نحو %s. هل تقديره معقول؟' % (
    dtext(n['a'], 1), n['b'], cnt(est854(n)['ref'] * (10 if n['w'] else 1), 'جنيه', 'جنيهين', 'جنيهات', 'جنيهًا')),
    'A box costs %s pounds and we buy %d. Ahmed says we pay about %d pounds. Is that reasonable?' % (
    dtext(n['a'], 1), n['b'], est854(n)['ref'] * (10 if n['w'] else 1)), 'no' if n['w'] else 'yes', None),
     lambda n: 'no' if n['w'] else 'yes', [dict(d, w=w) for d in D854[::3] for w in (0, 1)], 'بلا نموذج',
     lambda n: ['$e', n['a'], n['b'], 'j'], cards='yesno')
# 8-6: اختيار الطريقة
MIX = ([dict(k='q25', a=a, b=4 * m) for a in (125, 25) for m in range(2, 12) if a * 4 * m < 20000]
       + [dict(k='near', a=1000 + d, b=1000 - e) for d in (1, 2, 3) for e in (2, 3, 4)]
       + [dict(k='dsq', a=50 - d, b=50 + d) for d in range(1, 6)] + [dict(k='n100', a=a, b=b) for a in (96, 97, 98) for b in (95, 97, 99)])


def mix(n):
    a, b, k = n['a'], n['b'], n['k']
    if k == 'near':
        return '%d %s %d = %s' % (a, MINUS, b, BOX), a - b
    return '%d %s %d = %s' % (a, TIMES, b, BOX), a * b


perf('mixed_any', lambda n: plain(*mix(n)), lambda n: mix(n)[1], MIX, 'بلا نموذج', lambda n: ['x', n['a'], n['b'], n['k']])
perf('judge_mixed', lambda n: judge('%s %s %d = %d' % (n['a'], TIMES if n['k'] != 'near' else MINUS, n['b'],
                                                      mix(n)[1] + (0 if n['w'] == 0 else 10)), n['w'] == 0),
     lambda n: 'yes' if n['w'] == 0 else 'no', [dict(d, w=w) for d in MIX for w in (0, 1)], 'حلّان لمسألة واحدة',
     lambda n: ['x', n['a'], n['b'], n['k']], cards='yesno')
METHODS = {'dsq': ('فرق المربعين', 'difference of squares'), 'dist': ('التوزيع', 'distribution'),
           'comp': ('التعويض', 'compensation'), 'half': ('التنصيف والمضاعفة', 'halving and doubling')}
D862 = ([dict(m='dsq', a=50 - d, b=50 + d) for d in range(1, 6)] + [dict(m='dist', a=a, b=b) for a in (23, 34, 42) for b in (6, 7)]
        + [dict(m='comp', a=a, b=b) for a in (49, 59, 99) for b in (6, 7)] + [dict(m='half', a=a, b=35) for a in (14, 16, 18)])


def way(n):
    a, b, m = n['a'], n['b'], n['m']
    if m == 'dsq':
        return '%d %s %d = 50 %s 50 %s %d %s %d = %d' % (a, TIMES, b, TIMES, MINUS, 50 - a, TIMES, 50 - a, a * b)
    if m == 'dist':
        return '%d %s %d = %d + %d = %d' % (a, TIMES, b, a // 10 * 10 * b, a % 10 * b, a * b)
    if m == 'comp':
        return '%d %s %d = %d %s %d = %d' % (a, TIMES, b, (a + 1) * b, MINUS, b, a * b)
    return '%d %s %d = %d %s %d = %d' % (a, TIMES, b, a // 2, TIMES, 2 * b, a * b)


def way_cards(n):
    order = ['dsq', 'dist', 'comp', 'half']
    return order, {k: {'ar': METHODS[k][0], 'en': METHODS[k][1]} for k in order}


perf('which_way', lambda n: ('بأي طريقة حُسبت؟ %s' % eq(way(n)), 'Which method was used? %s' % eq(way(n)), n['m'], None),
     lambda n: n['m'], D862, 'حلّان لمسألة واحدة', lambda n: ['w', n['a'], n['b'], n['m']], cards=way_cards)

SKILLS.update({
    '8-1-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'sq5_model', 'ف2': 'sq5_step', 'ف3': 'sq5', 'solve': 'sq5'},
               [(5, 'حتى 45', lambda n: n['t'] <= 4), (5, 'من 55', lambda n: n['t'] >= 5)]),
    '8-1-2': S(['ف2', 'ف3'], {'ف2': 'nb_sq_step', 'ف3': 'nb_sq', 'solve': 'nb_sq'},
               [(5, 'بعد مضاعف العشرة', lambda n: n['s'] > 0), (5, 'قبله', lambda n: n['s'] < 0)]),
    '8-1-3': S(['ف2', 'ف3', 'ف5'], {'ف2': 'sq_step', 'ف3': 'sq_gen', 'ف5': 'judge_sq', 'solve': 'sq_gen'},
               [(5, 'حتى 50', lambda n: n['a'] < 50), (5, 'فوق 50', lambda n: n['a'] > 50)]),
    '8-2-1': S(['ف1', 'ف2', 'ف3', 'ف5'], {'ف1': 'dsq_model', 'ف2': 'dsq_step', 'ف3': 'dsq', 'ف5': 'judge_dsq', 'solve': 'dsq'},
               [(5, 'الفرق عن الوسط 1 أو 2', lambda n: n['d'] <= 2), (5, 'الفرق 3 فأكثر', lambda n: n['d'] > 2)]),
    '8-3-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'n100_model', 'ف2': 'n100_step', 'ف3': 'n100', 'solve': 'n100'},
               [(5, 'الركن حتى 20', lambda n: (100 - n['a']) * (100 - n['b']) <= 20), (5, 'الركن فوق 20', lambda n: (100 - n['a']) * (100 - n['b']) > 20)]),
    '8-3-2': S(['ف2', 'ف3'], {'ف2': 'n100_step', 'ف3': 'n100', 'solve': 'n100'},
               [(5, 'كلاهما فوق 85', lambda n: n['a'] > 85), (5, 'أحدهما 85 أو أقل', lambda n: n['a'] <= 85)]),
    '8-3-3': S(['ف2', 'ف3', 'ف5'], {'ف2': 'n100_step', 'ف3': 'n100', 'ف5': 'judge_n100', 'solve': 'n100'},
               [(5, 'كلاهما فوق 100', lambda n: n['b'] > 100), (5, 'أحدهما تحت 100', lambda n: n['b'] < 100)]),
    '8-4-1': S(['ف3', 'ف5'], {'ف3': 'check_last', 'ف5': 'judge_check_last', 'solve': 'check_last'},
               [(4, 'صحيح', lambda n: n['w'] == 0), (3, 'رقمه الأخير خاطئ', lambda n: n['w'] == 1), (3, 'تقديره بعيد', lambda n: n['w'] == 2)]),
    '8-4-2': S(['ف2', 'ف3'], {'ف2': 'nine_rem', 'ف3': 'nine_check', 'solve': 'nine_check'},
               [(5, 'يجتاز', lambda n: n['w'] == 0), (5, 'لا يجتاز', lambda n: n['w'] == 1)]),
    '8-4-3': S(['ف5'], {'ف5': 'check_limits', 'solve': 'check_limits'},
               [(4, 'صحيح', lambda n: n['w'] == 0), (6, 'خاطئ يجتاز الفحصين', lambda n: n['w'] > 0)]),
    '8-5-1': S(['ف4'], {'ف4': 'unit_price', 'solve': 'unit_price'},
               [(5, 'كيلو', lambda n: n['c'] == 0), (5, 'كراسات', lambda n: n['c'] == 1)]),
    '8-5-2': S(['ف3', 'ف4'], {'ف3': 'dur_add', 'ف4': 'ctx_dur', 'solve': 'dur_add'},
               [(5, 'المجموع حتى 3 ساعات', lambda n: n['h1'] + n['h2'] <= 2), (5, 'أكثر', lambda n: n['h1'] + n['h2'] > 2)]),
    '8-5-3': S(['ف4'], {'ف4': 'rate', 'solve': 'rate'},
               [(5, 'نصف ساعة أو أقل', lambda n: n['t'] <= 30), (5, 'أكثر من نصف ساعة', lambda n: n['t'] > 30)]),
    '8-5-4': S(['ف4', 'ف5'], {'ف4': 'est_buy', 'ف5': 'judge_est_buy', 'solve': 'est_buy'},
               [(5, 'العدد حتى 50', lambda n: n['b'] <= 50), (5, 'العدد فوق 50', lambda n: n['b'] > 50)]),
    '8-6-1': S(['ف3', 'ف5'], {'ف3': 'mixed_any', 'ف5': 'judge_mixed', 'solve': 'mixed_any'},
               [(3, 'في 25 أو 125', lambda n: n['k'] == 'q25'), (2, 'طرح قرب 1000', lambda n: n['k'] == 'near'),
                (3, 'فرق المربعين', lambda n: n['k'] == 'dsq'), (2, 'قرب 100', lambda n: n['k'] == 'n100')]),
    '8-6-2': S(['ف5'], {'ف5': 'which_way', 'solve': 'which_way'},
               [(3, 'فرق المربعين', lambda n: n['m'] == 'dsq'), (3, 'التوزيع', lambda n: n['m'] == 'dist'),
                (2, 'التعويض', lambda n: n['m'] == 'comp'), (2, 'التنصيف والمضاعفة', lambda n: n['m'] == 'half')]),
})

# ---------------------------------------------------------------- بوابة الجاهزية للمتطلب الخارجي (5.1)
# «قراءة الساعة» لـ 8-5-2 (قرار الأب، 26 نوفمبر: بوابة جاهزية من 3 بنود أو قرار المعلم). البندان الأولان قراءة وجه الساعة
# بالبطاقات، والثالث أن الساعة 60 دقيقة. المشتّتات أخطاء القراءة المعروفة: العقرب القصير يُقرأ للساعة التالية قبل
# بلوغها، والعقرب الطويل يُقرأ بالرقم الذي يشير إليه لا بدقائقه، والعقربان يُبدَّلان
D_CLOCK = [dict(h=h, m=m) for h in range(1, 13) for m in (10, 15, 20, 30, 40, 45, 50)]


def hm(h, m):
    return '%d:%02d' % ((h - 1) % 12 + 1, m)


def clock_cards(n):
    h, m = n['h'], n['m']
    wrong = [hm(h + 1, m) if m >= 30 else hm(h - 1, m),     # الساعة المجاورة
             hm(h, m // 5),                                 # الرقم الذي يشير إليه العقرب الطويل
             hm(m // 5 or 12, (h % 12) * 5)]                # العقربان مبدَّلان
    labels = {'A': hm(h, m)}
    for k, w in zip('BCD', [w for j, w in enumerate(wrong) if w != hm(h, m) and w not in wrong[:j]]):
        labels[k] = w
    ids = sorted(labels)
    r = (h + m // 5) % len(ids)
    return ids[r:] + ids[:r], {k: {'ar': LRI + v + PDI, 'en': v} for k, v in labels.items()}


perf('clock_read', lambda n: ('كم الساعة؟', 'What time is it?', 'A', dict(kind='clock', h=n['h'], m=n['m'])),
     lambda n: 'A', D_CLOCK, 'وجه الساعة', lambda n: ['t', n['h'], n['m']], cards=clock_cards)
perf('hour_minutes', lambda n: ('كم دقيقة في الساعة الواحدة؟', 'How many minutes are in one hour?', 60, None),
     lambda n: 60, [dict(k=1)], 'بلا نموذج', lambda n: ['h', 60])
MODEL_OK['clock'] = lambda m, n, ans: m['h'] == n['h'] and m['m'] == n['m'] and 1 <= m['h'] <= 12 and m['m'] % 5 == 0

# المتطلب الخارجي لكل مهارة: أداءات بنود بوابة جاهزيته بترتيب عرضها (3 بنود، READY_ITEMS في المحرك)
READY = {'8-5-2': ('clock_read', 'clock_read', 'hour_minutes')}
