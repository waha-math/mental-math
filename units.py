"""مولّد المحتوى العام لوحدات المراحل 1 إلى 3 خارج الشريحة (UNITS-PLAN.md).

لكل مهارة مواصفة: أنواع دليلها من صفها في الخريطة، والأداء المطلوب لكل نوع، ومجال كل أداء، وعائلات خانات فحصها العشر،
وحقيقتها الحسابية. ويُنتج المولّد بنود المهارة بالأدوار والأعداد التي ينتجها slice_content.build_big لمهارات الشريحة،
فلا يحتاج المجدول ولا مصدر البنود تغييرًا لمهارة جديدة.

الجواب يُحسب مرتين: في render عند التوليد، وفي truth مستقلًا (check). والرسم يُتحقق منه بإعادة حسابه من الأعداد.
خانات الفحص: الخريطة لا تحددها إلا لمهارات الشريحة (10.2). الشروط هنا مكتوبة من صف المهارة ومن قاعدة 3.6، وتُذكر في
slice-content.md، وهي اختيار يُراجع.
"""
import random

from item_layer import gate_plan, short_types, opening_types

LRI, PDI, MINUS, BOX = '⁦', '⁩', '−', '▢'


def eq(s):
    return LRI + ' ' + s + ' ' + PDI


def op_s(a, op, b):
    return '%d %s %d' % (a, '+' if op > 0 else MINUS, b)


# ---------------------------------------------------------------- القصص (ف4): العملية يختارها الطفل
# القصص بصيغة «عدد ...» تصح مع أي عدد: في العربية يتغير المعدود بين 1 و2 و3-10 و11-99، فـ«5 تفاحات» و«15 تفاحة»
CTX_ADD = [('كان عدد التفاح في السلة {a}، ثم وضعت أمي فيها {b} أخرى. كم صار عدد التفاح في السلة؟',
            'There were {a} apples in the basket. Mum put in {b} more. How many apples are in the basket now?'),
           ('كان عدد العصافير على الشجرة {a}، ثم جاء {b} آخرون. كم صار عدد العصافير؟',
            'There were {a} birds on the tree. {b} more came. How many birds are on the tree now?'),
           ('كان عدد السيارات مع كريم {a}، ثم أعطاه أخوه {b} أخرى. كم صار عددها؟',
            'Karim had {a} cars. His brother gave him {b} more. How many cars does Karim have now?'),
           ('كان عدد الأطفال في الحديقة {a}، ثم دخل {b} آخرون. كم صار عددهم؟',
            'There were {a} children in the garden. {b} more came in. How many children are in the garden now?')]
CTX_SUB = [('كان عدد البالونات مع ليلى {a}، فطار منها {b}. كم بقي منها؟',
            'Laila had {a} balloons. {b} flew away. How many balloons does she have left?'),
           ('كان عدد حبات التمر في الصحن {a}، فأكلنا منها {b}. كم بقي منها؟',
            'There were {a} dates on the plate. We ate {b}. How many are left?'),
           ('كان عدد السيارات في الموقف {a}، فخرج منها {b}. كم بقي منها؟',
            'There were {a} cars in the car park. {b} drove away. How many cars are left?'),
           ('كان عدد الكتب على الرف {a}، فأخذنا منها {b}. كم بقي منها؟',
            'There were {a} books on the shelf. We took {b}. How many books are left on the shelf?')]


# ---------------------------------------------------------------- الأداءات: (نص عربي، إنجليزي، جواب، رسم)
def p_dots_flash(n):
    return ('كم نقطة رأيت؟', 'How many dots did you see?', n['n'],
            dict(kind='dots', n=n['n'], layout=n['v'], flash=True))


def p_frame_flash(n, size):
    return ('كم قرصًا رأيت على الإطار؟', 'How many counters did you see on the frame?', n['n'],
            dict(kind='frame', size=size, n=n['n'], flash=True))


def p_five_plus(n):
    return ('%s' % eq('5 + %d = %s' % (n['n'] - 5, BOX)), '%s' % eq('5 + %d = %s' % (n['n'] - 5, BOX)), n['n'], None)


def p_path_gap(n):
    s, d, k = n['s'], n['d'], n['k']
    return ('ما العدد الناقص على المسار؟', 'Which number is missing on the path?', s + k * d,
            dict(kind='path', start=s, step=d, len=5, hide=k))


def p_count_next(n):
    a, d = n['a'], n['d']
    if d > 0:
        return ('ما العدد الذي يأتي بعد %d؟' % a, 'Which number comes after %d?' % a, a + 1, None)
    return ('ما العدد الذي يأتي قبل %d؟' % a, 'Which number comes before %d?' % a, a - 1, None)


def p_path_jump(n):
    a, b, op = n['a'], n['b'], n['op']
    ar = ('نبدأ من %d ونتقدم %d. أين نصل؟' if op > 0 else 'نبدأ من %d ونرجع %d. أين نصل؟') % (a, b)
    en = ('Start at %d and move forward %d. Where do we land?' if op > 0 else
          'Start at %d and move back %d. Where do we land?') % (a, b)
    return ar, en, a + op * b, dict(kind='path', start=0, step=1, len=11, mark=a, jump=op * b)


def p_addsub(n):
    s = eq('%s = %s' % (op_s(n['a'], n['op'], n['b']), BOX))
    return s, s, n['a'] + n['op'] * n['b'], None


def p_discs(n):
    w, a = n['w'], n['a']
    return ('عدد الأقراص %d، منها %d حمراء والباقي زرقاء. كم عدد الزرقاء؟' % (w, a),
            '%d counters: %d are red and the rest are blue. How many are blue?' % (w, a), w - a,
            dict(kind='discs', red=a, blue=w - a))


def p_decomp(n):
    s = eq('%d = %d + %s' % (n['w'], n['a'], BOX))
    return s, s, n['w'] - n['a'], None


def p_bond(n):
    w, a = n['w'], n['a']
    return ('في المخطط: الكل %d وأحد الجزأين %d. ما الجزء الآخر؟' % (w, a),
            'In the diagram the whole is %d and one part is %d. What is the other part?' % (w, a), w - a,
            dict(kind='bond', whole=w, part=a))


def p_cup(n):
    w, a = n['w'], n['a']
    return ('عدد الأقراص %d، بعضها تحت الكوب. نرى منها %d. كم عدد ما تحت الكوب؟' % (w, a),
            'We have %d counters and some are under the cup. We can see %d. How many are under the cup?' % (w, a),
            w - a, dict(kind='cup', total=w, shown=a))


def p_missing_add(n):
    s = eq('%d + %s = %d' % (n['a'], BOX, n['w']))
    return s, s, n['w'] - n['a'], None


def p_path_add(n):
    big, small = n['big'], n['small']
    return ('%s نبدأ من الأكبر: من %d نتقدم %d. أين نصل؟' % (eq('%d + %d' % (small, big)), big, small),
            '%s Start from the bigger number: from %d move forward %d. Where do we land?' % (
                eq('%d + %d' % (small, big)), big, small),
            big + small, dict(kind='path', start=0, step=1, len=11, mark=big, jump=small))


def p_add_small_first(n):
    s = eq('%d + %d = %s' % (n['small'], n['big'], BOX))
    return s, s, n['small'] + n['big'], None


def p_ctx(n, table):
    ar, en = table[n['c'] % len(table)]
    return ar.format(**n), en.format(**n), (n['a'] + n['b'] if table is CTX_ADD else n['a'] - n['b']), None


def p_bond_sub(n):
    a, b = n['a'], n['b']
    s = eq('%d %s %d = %s' % (a, MINUS, b, BOX))
    return ('%s في المخطط: الكل %d وأحد الجزأين %d. ما الجزء الآخر؟' % (s, a, b),
            '%s In the diagram the whole is %d and one part is %d. What is the other part?' % (s, a, b), a - b,
            dict(kind='bond', whole=a, part=b))


def p_sub(n):
    s = eq('%d %s %d = %s' % (n['a'], MINUS, n['b'], BOX))
    return s, s, n['a'] - n['b'], None


def p_equal_missing(n):
    w, a, f = n['w'], n['a'], n['f']
    if f == 0:
        s, ans = '%d = %s + %d' % (w, BOX, a), w - a
    elif f == 1:
        s, ans = '%d = %d + %s' % (w, a, BOX), w - a
    else:                                                   # الميزان: مجموعان متساويان
        c = n['c']
        s, ans = '%d + %d = %d + %s' % (a, w - a, c, BOX), w - c
    s = eq(s)
    return s, s, ans, None


def p_judge(n):
    a, b, c, d = n['a'], n['b'], n['c'], n['d']
    s = eq('%d + %d = %d + %d' % (a, b, c, d))
    return ('هل هذا صحيح؟ %s' % s, 'Is this true? %s' % s, 'yes' if a + b == c + d else 'no', None)


# ---------------------------------------------------------------- المرحلة 2 (حتى 20)
def plain_eq(text, ans):
    s = eq(text)
    return s, s, ans, None


def p_frames2(n):
    k = n['n']
    return ('كم قرصًا على الإطارين؟', 'How many counters are on the two frames?', k, dict(kind='frames2', n=k))


def p_frames2_op(n):
    a, b, op = n['a'], n['b'], n['op']
    if op > 0:
        ar, en = ('عدد الأقراص على الإطارين %d، ونضيف %d. كم يصير عددها؟' % (a, b),
                  'There are %d counters on the frames and we add %d. How many will there be?' % (a, b))
    else:
        ar, en = ('عدد الأقراص على الإطارين %d، ونأخذ منها %d. كم يبقى منها؟' % (a, b),
                  'There are %d counters on the frames and we take away %d. How many will be left?' % (a, b))
    return ar, en, a + op * b, dict(kind='frames2', n=a)


def p_beads_double(n):
    k = n['k']
    return ('صفّان متماثلان، عدد الخرز في كل صف %d. كم عدد الخرز في الصفين؟' % k,
            'Two equal rows with %d beads in each row. How many beads in both rows?' % k, 2 * k,
            dict(kind='beads', rows=[k, k], hide=None))


def p_beads_half(n):
    k = n['k']
    return ('عدد الخرز في صفين متماثلين %d. كم عدده في كل صف؟' % (2 * k),
            '%d beads in two equal rows. How many beads are in each row?' % (2 * k), k,
            dict(kind='beads', rows=[k, k], hide=1))


def p_half(n):
    k = n['k']
    return ('نصف %d = %s' % (2 * k, BOX), 'Half of %d = %s' % (2 * k, BOX), k, None)


CTX_HALF = [('عدد حبات التمر %d، نقسمها بالتساوي بين طفلين. كم يأخذ كل طفل؟',
             '%d dates are shared equally between two children. How many does each child get?'),
            ('عدد الأقلام %d، نضعها في علبتين بالتساوي. كم في كل علبة؟',
             '%d pencils go equally into two boxes. How many pencils are in each box?')]


def p_ctx_half(n):
    ar, en = CTX_HALF[n['c'] % len(CTX_HALF)]
    return ar % (2 * n['k']), en % (2 * n['k']), n['k'], None


def p_near_step(n):
    a, d = n['a'], n['d']                                   # a + (a + d): الضعف ثم التعديل
    if d == 1:
        return plain_eq('%d + %d = %s + 1' % (a, a + 1, BOX), 2 * a)
    return plain_eq('%d + %d = %d + %s' % (a, a + 2, a + 1, BOX), a + 1)


def p_near(n):
    a, d = n['a'], n['d']
    return plain_eq('%d + %d = %s' % (a, a + d, BOX), 2 * a + d)


def p_judge_near(n):
    a, c = n['a'], n['c']                                   # هل a + (a+2) = c + c ؟
    s = eq('%d + %d = %d + %d' % (a, a + 2, c, c))
    return 'هل هذا صحيح؟ %s' % s, 'Is this true? %s' % s, 'yes' if c == a + 1 else 'no', None


def p_ten_step(n):
    a, b = n['a'], n['b']
    return plain_eq('%d + %d = 10 + %s' % (a, b, BOX), a + b - 10)


def p_add20(n):
    return plain_eq('%d + %d = %s' % (n['a'], n['b'], BOX), n['a'] + n['b'])


def p_sub20(n):
    return plain_eq('%d %s %d = %s' % (n['a'], MINUS, n['b'], BOX), n['a'] - n['b'])


def p_line_down(n):
    a, b = n['a'], n['b']
    j1 = a - 10
    s = eq('%d %s %d' % (a, MINUS, b))
    return ('%s ننزل إلى 10 أولًا، ثم نكمل. أين نصل؟' % s, '%s First go down to 10, then carry on. Where do we land?' % s,
            a - b, dict(kind='jumps', line='back', start=a, jumps=[j1, b - j1], stations=[10, a - b], hide=['station', 1]))


def p_down_step(n):
    a, b = n['a'], n['b']
    return plain_eq('%d %s %d = 10 %s %s' % (a, MINUS, b, MINUS, BOX), b - (a - 10))


def p_line_up_sum(n):
    a, b = n['a'], n['b']
    s = eq('%d %s %d' % (a, MINUS, b))
    return ('%s نكمل من %d إلى %d. كم مجموع القفزتين؟' % (s, b, a),
            '%s Count up from %d to %d. What do the two jumps add up to?' % (s, b, a), a - b,
            dict(kind='jumps', line='up', start=b, jumps=[10 - b, a - 10], stations=[10, a], hide=None))


def p_up_step(n):
    a, b = n['a'], n['b']
    s = eq('%d %s %d' % (a, MINUS, b))
    return ('%s: من %d إلى 10 قفزة %d، ومن 10 إلى %d قفزة %s' % (s, b, 10 - b, a, BOX),
            '%s: from %d to 10 is a jump of %d, and from 10 to %d is a jump of %s' % (s, b, 10 - b, a, BOX), a - 10, None)


def p_nine_step(n):
    b = n['b']
    return plain_eq('9 + %d = %s %s 1' % (b, BOX, MINUS), 10 + b)


def p_three(n):
    a, b, c = n['a'], n['b'], n['c']
    return plain_eq('%d + %d + %d = %s' % (a, b, c, BOX), a + b + c)


def p_judge_three(n):
    a, b, c, w = n['a'], n['b'], n['c'], n['w']
    s = eq('%d + %d + %d = %d + %d + %d' % (a, b, c, a, c, b + w))
    return 'هل هذا صحيح؟ %s' % s, 'Is this true? %s' % s, 'yes' if w == 0 else 'no', None


# ---------------------------------------------------------------- المرحلة 3 (حتى 100)
def p_tens_model(n):
    t, o = n['t'], n['o']
    return ('كم عدد الأقراص؟ (كل حزمة عشرة)', 'How many counters? (each bundle is ten)', 10 * t + o,
            dict(kind='tens', tens=t, ones=o))


def p_tens_eq(n):
    return plain_eq('%d + %d = %s' % (10 * n['t'], n['o'], BOX), 10 * n['t'] + n['o'])


def p_jump10_line(n):
    a, k, op = n['a'], n['k'], n['op']
    end = a + op * 10 * k
    s_ = eq('%s' % op_s(a, op, 10 * k))
    return ('%s أين نصل؟' % s_, '%s Where do we land?' % s_, end,
            dict(kind='jumps', line='up' if op > 0 else 'back', start=a, jumps=[10 * k], stations=[end], hide=['station', 0],
                 ten=False))


def p_jump10(n):
    return plain_eq('%s = %s' % (op_s(n['a'], n['op'], 10 * n['k']), BOX), n['a'] + n['op'] * 10 * n['k'])


def p_wholetens_model(n):
    a, b, op = n['a'], n['b'], n['op']
    s_ = eq(op_s(10 * a, op, 10 * b))
    return ('%s كم حزمة عشرة تصير؟ وكم العدد؟' % s_ if op > 0 else '%s كم حزمة عشرة تبقى؟ وكم العدد؟' % s_,
            '%s How many tens, and what is the number?' % s_, 10 * (a + op * b),
            dict(kind='tens', tens=a, ones=0, plus=b if op > 0 else 0, minus=b if op < 0 else 0))


def p_wholetens(n):
    return plain_eq('%s = %s' % (op_s(10 * n['a'], n['op'], 10 * n['b']), BOX), 10 * (n['a'] + n['op'] * n['b']))


# التقريب (قرار الأب، 25 نوفمبر): ما آحاده 5 يبعد 5 عن العشرتين، فيُقرَّب إلى العشرة الأكبر. يُعلَّم في الدرس بأمثلة
# متجاورة (24 ثم 25 ثم 26) والمسافتان مرسومتان، ولا يُسأل عنه قبل الدرس (البوابة والافتتاح والتحقق القصير)
def p_round_line(n):
    v = n['v']
    lo = v // 10 * 10
    ans = lo + 10 if v % 10 >= 5 else lo
    model = dict(kind='round', lo=lo, hi=lo + 10, v=v)
    if n.get('dist'):
        model['dist'] = True                                # المسافتان إلى العشرتين مكتوبتان على الخط
    if n.get('explain'):
        return ('%d يبعد %d عن %d، ويبعد %d عن %d: المسافتان متساويتان. حين تتساوى المسافتان نختار هنا العشرة الأكبر. '
                'إلى أي عشرة نقرّب %d؟' % (v, v - lo, lo, lo + 10 - v, lo + 10, v),
                '%d is %d away from %d and %d away from %d: the distances are equal. When the distances are equal, '
                'we choose the greater ten. Which ten do we round %d to?' % (v, v - lo, lo, lo + 10 - v, lo + 10, v), ans, model)
    return ('إلى أي عشرة نقرّب %d؟' % v, 'Which ten do we round %d to?' % v, ans, model)


def p_round(n):
    v = n['v']
    lo = v // 10 * 10
    return ('%d مقرَّبًا إلى أقرب عشرة = %s' % (v, BOX), '%d rounded to the nearest ten = %s' % (v, BOX),
            lo + 10 if v % 10 >= 5 else lo, None)


def p_comp_line(n):
    a = n['a']
    c = 10 - a % 10
    return ('من %d إلى العشرة التالية. كم القفزة؟' % a, 'From %d to the next ten. How big is the jump?' % a, c,
            dict(kind='jumps', line='up', start=a, jumps=[c], stations=[a + c], hide=['jump', 0], ten=False))


def p_comp(n):
    a = n['a']
    return plain_eq('%d + %s = %d' % (a, BOX, (a // 10 + 1) * 10), 10 - a % 10)


def p_bridge_step(n):
    a, b, op = n['a'], n['b'], n['op']
    ten = (a // 10 + 1) * 10 if op > 0 else a // 10 * 10
    if op > 0:
        return plain_eq('%d + %d = %d + %s' % (a, b, ten, BOX), a + b - ten)
    return plain_eq('%d %s %d = %d %s %s' % (a, MINUS, b, ten, MINUS, BOX), ten - (a - b))


def p_two_digit(n):
    return plain_eq('%s = %s' % (op_s(n['a'], n['op'], n['b']), BOX), n['a'] + n['op'] * n['b'])


def p_ctx_big(n):
    return p_ctx(n, CTX_ADD if n['op'] > 0 else CTX_SUB)


def p_jumps_add(n):
    a, b = n['a'], n['b']
    t, o = b // 10 * 10, b % 10
    mid = a + t
    if (mid % 10) + o >= 10 and o:                          # مع عبور: إلى العشرة التالية ثم الباقي
        c = 10 - mid % 10
        jumps, stations = [t, c, o - c], [mid, mid + c, a + b]
    else:
        jumps, stations = [t, o], [mid, a + b]
    jumps = [j for j in jumps if j]
    stations = stations[-len(jumps):] if len(jumps) < len(stations) else stations
    s_ = eq('%d + %d' % (a, b))
    return ('%s أين نصل؟' % s_, '%s Where do we land?' % s_, a + b,
            dict(kind='jumps', line='up', start=a, jumps=jumps, stations=stations, hide=['station', len(jumps) - 1], ten=False))


def p_jump_step(n):
    a, b = n['a'], n['b']
    t = b // 10 * 10
    return plain_eq('%d + %d = %d + %s' % (a, b, a + t, BOX), b % 10)


def p_tens2_model(n):
    # خطوة التجزئة (قرار الأب، 25 نوفمبر: دليل على الطريقة لا على الناتج وحده): العشرات معًا أولًا
    a, b = n['a'], n['b']
    s_ = eq('%d + %d' % (a, b))
    return ('%s نجمع العشرات أولًا. كم تصير العشرات معًا؟' % s_, '%s First add the tens. What do the tens make together?' % s_,
            a // 10 * 10 + b // 10 * 10, dict(kind='tens2', a=[a // 10, a % 10], b=[b // 10, b % 10]))


def p_partition_step(n):
    a, b = n['a'], n['b']
    return plain_eq('%d + %d = %d + %s' % (a, b, a // 10 * 10 + b // 10 * 10, BOX), a % 10 + b % 10)


def p_judge_partition(n):
    a, b, w = n['a'], n['b'], n['w']
    t, o = a // 10 * 10 + b // 10 * 10, a % 10 + b % 10
    s_ = eq('%d + %d = %d + %d' % (a, b, t, o + w))
    return 'هل هذا صحيح؟ %s' % s_, 'Is this true? %s' % s_, 'yes' if w == 0 else 'no', None


def p_adjust_step(n):
    a, b, op = n['a'], n['b'], n['op']                      # b ينتهي بـ 9: يُقرَّب إلى b + 1 ثم يُعدَّل
    if op > 0:
        return plain_eq('%d + %d = %s %s 1' % (a, b, BOX, MINUS), a + b + 1)
    return plain_eq('%d %s %d = %s + 1' % (a, MINUS, b, BOX), a - b - 1)


def p_judge_adjust(n):
    a, b, w = n['a'], n['b'], n['w']
    s_ = eq('%d %s %d = %d %s %d %s 1' % (a, MINUS, b, a, MINUS, b + 1, '+' if w == 0 else MINUS))
    return 'هل هذا صحيح؟ %s' % s_, 'Is this true? %s' % s_, 'yes' if w == 0 else 'no', None


def p_transfer_model(n):
    a, b = n['a'], n['b']
    c = 10 - a % 10
    return ('%s ننقل %d من العدد الثاني إلى الأول. كم يصير الأول؟' % (eq('%d + %d' % (a, b)), c),
            '%s Move %d from the second number to the first. What does the first number become?' % (eq('%d + %d' % (a, b)), c),
            a + c, dict(kind='tens2', a=[a // 10, a % 10], b=[b // 10, b % 10]))


def p_transfer_step(n):
    a, b = n['a'], n['b']
    c = 10 - a % 10
    return plain_eq('%d + %d = %d + %s' % (a, b, a + c, BOX), b - c)


def p_slide_model(n):
    a, b = n['a'], n['b']
    d = 10 - b % 10
    return ('%s نزيد كلًّا من العددين %d فيصيران %d و%d. كم الفرق؟' % (eq('%d %s %d' % (a, MINUS, b)), d, a + d, b + d),
            '%s Add %d to both numbers: they become %d and %d. What is the difference?' % (eq('%d %s %d' % (a, MINUS, b)), d, a + d, b + d),
            a - b, dict(kind='slide', a=a, b=b, d=d))


def p_slide_step(n):
    a, b = n['a'], n['b']
    d = 10 - b % 10
    return plain_eq('%d %s %d = %d %s %s' % (a, MINUS, b, a + d, MINUS, BOX), b + d)


def p_hundred_line(n):
    a = n['a']
    ten = (a // 10 + 1) * 10
    return ('من %d إلى 100. كم مجموع القفزتين؟' % a, 'From %d to 100. What do the two jumps add up to?' % a, 100 - a,
            dict(kind='jumps', line='up', start=a, jumps=[ten - a, 100 - ten], stations=[ten, 100], hide=None, ten=False))


def p_hundred_step(n):
    a = n['a']
    ten = (a // 10 + 1) * 10
    return ('من %d إلى %d قفزة %d، ومن %d إلى 100 قفزة %s' % (a, ten, ten - a, ten, BOX),
            'From %d to %d is a jump of %d, and from %d to 100 is a jump of %s' % (a, ten, ten - a, ten, BOX), 100 - ten, None)


def p_hundred(n):
    return plain_eq('%d + %s = 100' % (n['a'], BOX), 100 - n['a'])


CTX_CHANGE = [('اشترينا لعبة بـ%d جنيهًا، ودفعنا 100 جنيه. كم جنيهًا الباقي؟',
               'We buy a toy for %d pounds and pay with 100 pounds. How much change do we get?'),
              ('ثمن الكتاب %d جنيهًا، ومعنا ورقة 100 جنيه. كم يعيد البائع؟',
               'The book costs %d pounds and we pay with a note of 100 pounds. How much does the seller give back?')]


def p_change(n):
    ar, en = CTX_CHANGE[n['c'] % 2]
    return ar % n['a'], en % n['a'], 100 - n['a'], None


def p_double_step(n):
    a = n['a']
    return plain_eq('%d + %d = %d + %s' % (a, a, 2 * (a // 10 * 10), BOX), 2 * (a % 10))


def p_double2(n):
    return plain_eq('%d + %d = %s' % (n['a'], n['a'], BOX), 2 * n['a'])


def p_half_step(n):
    w = n['w']
    return ('نصف %d: نصف %d هو %d، ونصف %d هو %d. فنصف %d = %s' % (w, w // 10 * 10, w // 10 * 5, w % 10, w % 10 // 2, w, BOX),
            'Half of %d: half of %d is %d and half of %d is %d. So half of %d = %s' % (
                w, w // 10 * 10, w // 10 * 5, w % 10, w % 10 // 2, w, BOX), w // 2, None)


def p_half2(n):
    return ('نصف %d = %s' % (n['w'], BOX), 'Half of %d = %s' % (n['w'], BOX), n['w'] // 2, None)


def p_ctx_half2(n):
    ar, en = CTX_HALF[n['c'] % len(CTX_HALF)]
    return ar % n['w'], en % n['w'], n['w'] // 2, None


def p_bar(n):
    w = n['w']
    return ('شريط طوله %d نقصّه نصفين متساويين. كم طول كل نصف؟' % w,
            'A strip %d long is cut into two equal halves. How long is each half?' % w, w // 2, dict(kind='bar', whole=w))


PERFS = {
    'dots_flash': p_dots_flash, 'five_flash': lambda n: p_frame_flash(n, 5), 'ten_flash': lambda n: p_frame_flash(n, 10),
    'five_plus': p_five_plus, 'path_gap': p_path_gap, 'count_next': p_count_next, 'path_jump': p_path_jump,
    'addsub': p_addsub, 'discs': p_discs, 'decomp': p_decomp, 'bond': p_bond, 'cup': p_cup,
    'missing_add': p_missing_add, 'path_add': p_path_add, 'add_small_first': p_add_small_first,
    'ctx_add': lambda n: p_ctx(n, CTX_ADD), 'ctx_sub10': lambda n: p_ctx(n, CTX_SUB), 'bond_sub': p_bond_sub,
    'sub': p_sub, 'equal_missing': p_equal_missing, 'judge': p_judge,
    'frames2': p_frames2, 'tens_ones': lambda n: plain_eq('10 + %d = %s' % (n['n'] - 10, BOX), n['n']),
    'frames2_op': p_frames2_op, 'addsub20': lambda n: plain_eq('%s = %s' % (op_s(n['a'], n['op'], n['b']), BOX),
                                                                  n['a'] + n['op'] * n['b']),
    'beads_double': p_beads_double, 'double': lambda n: plain_eq('%d + %d = %s' % (n['k'], n['k'], BOX), 2 * n['k']),
    'beads_half': p_beads_half, 'half': p_half, 'ctx_half': p_ctx_half, 'near_step': p_near_step, 'near': p_near,
    'judge_near': p_judge_near, 'frames2_add': lambda n: p_frames2_op(dict(n, op=1)), 'ten_step': p_ten_step,
    'add20': p_add20, 'ctx_add20': lambda n: p_ctx(n, CTX_ADD), 'line_down': p_line_down, 'down_step': p_down_step,
    'sub20': p_sub20, 'line_up_sum': p_line_up_sum, 'up_step': p_up_step, 'nine_step': p_nine_step,
    'three': p_three, 'judge_three': p_judge_three, 'ctx_sub20': lambda n: p_ctx(n, CTX_SUB),
    'tens_model': p_tens_model, 'tens_eq': p_tens_eq, 'jump10_line': p_jump10_line, 'jump10': p_jump10,
    'wholetens_model': p_wholetens_model, 'wholetens': p_wholetens, 'round_line': p_round_line, 'round': p_round,
    'comp_line': p_comp_line, 'comp': p_comp, 'bridge_step': p_bridge_step, 'two_digit': p_two_digit,
    'ctx_big': p_ctx_big, 'jumps_add': p_jumps_add, 'jump_step': p_jump_step, 'tens2_model': p_tens2_model,
    'partition_step': p_partition_step, 'judge_partition': p_judge_partition, 'adjust_step': p_adjust_step,
    'judge_adjust': p_judge_adjust, 'transfer_model': p_transfer_model, 'transfer_step': p_transfer_step,
    'slide_model': p_slide_model, 'slide_step': p_slide_step, 'hundred_line': p_hundred_line,
    'hundred_step': p_hundred_step, 'hundred': p_hundred, 'change': p_change, 'double_step': p_double_step,
    'double2': p_double2, 'half_step': p_half_step, 'half2': p_half2, 'ctx_half2': p_ctx_half2, 'bar': p_bar,
    'half_tens': lambda n: ('نصف %d = %s' % (n['w'], BOX), 'Half of %d = %s' % (n['w'], BOX), n['w'] // 2, None),
}
RESOURCE = {'dots_flash': 'نقاط النرد، بومضة', 'five_flash': 'إطار الخمسة، بومضة', 'ten_flash': 'إطار العشرة، بومضة',
            'five_plus': 'بلا نموذج', 'path_gap': 'مسار الأعداد', 'count_next': 'بلا نموذج', 'path_jump': 'مسار الأعداد',
            'addsub': 'بلا نموذج', 'discs': 'أقراص بلونين', 'decomp': 'بلا نموذج', 'bond': 'مخطط الرابطة',
            'cup': 'الكوب المخفي', 'missing_add': 'بلا نموذج', 'path_add': 'مسار الأعداد',
            'add_small_first': 'بلا نموذج', 'ctx_add': 'صورة الموقف، والنص منطوق', 'ctx_sub10': 'صورة الموقف، والنص منطوق',
            'bond_sub': 'مخطط الرابطة', 'sub': 'بلا نموذج', 'equal_missing': 'بلا نموذج', 'judge': 'بلا نموذج'}
CARD_PERFS = {'judge': 'yesno', 'judge_near': 'yesno', 'judge_three': 'yesno', 'judge_partition': 'yesno',
              'judge_adjust': 'yesno'}
RESOURCE.update({'tens_model': 'حزم العشرات', 'tens_eq': 'بلا نموذج', 'jump10_line': 'خط الأعداد (بدل لوحة المئة)',
                 'jump10': 'بلا نموذج', 'wholetens_model': 'حزم العشرات', 'wholetens': 'بلا نموذج', 'round_line': 'خط الأعداد',
                 'round': 'بلا نموذج', 'comp_line': 'خط الأعداد', 'comp': 'بلا نموذج', 'bridge_step': 'بلا نموذج',
                 'two_digit': 'بلا نموذج', 'ctx_big': 'صورة الموقف، والنص منطوق', 'jumps_add': 'خط الأعداد الفارغ',
                 'jump_step': 'بلا نموذج', 'tens2_model': 'مكعبات العشرات والآحاد، والسؤال عن العشرات معًا', 'partition_step': 'بلا نموذج',
                 'judge_partition': 'بلا نموذج', 'adjust_step': 'بلا نموذج', 'judge_adjust': 'بلا نموذج',
                 'transfer_model': 'مكعبات العشرات والآحاد (بدل الأقراص المنتقلة)', 'transfer_step': 'بلا نموذج',
                 'slide_model': 'نقطتان تنزلقان معًا على خط الأعداد', 'slide_step': 'بلا نموذج',
                 'hundred_line': 'خط الأعداد', 'hundred_step': 'بلا نموذج', 'hundred': 'بلا نموذج',
                 'change': 'صورة الموقف، والنص منطوق', 'double_step': 'بلا نموذج', 'double2': 'بلا نموذج',
                 'half_step': 'بلا نموذج', 'half2': 'بلا نموذج', 'ctx_half2': 'صورة الموقف، والنص منطوق',
                 'bar': 'شريط يُقصّ نصفين', 'half_tens': 'بلا نموذج'})
RESOURCE.update({'frames2': 'إطارا عشرة', 'tens_ones': 'بلا نموذج', 'frames2_op': 'إطارا عشرة', 'addsub20': 'بلا نموذج',
                 'beads_double': 'صفّا خرز متماثلان', 'double': 'بلا نموذج', 'beads_half': 'صفّا خرز', 'half': 'بلا نموذج',
                 'ctx_half': 'صورة الموقف، والنص منطوق', 'near_step': 'بلا نموذج', 'near': 'بلا نموذج',
                 'judge_near': 'بلا نموذج', 'frames2_add': 'إطارا عشرة', 'ten_step': 'بلا نموذج', 'add20': 'بلا نموذج',
                 'ctx_add20': 'صورة الموقف، والنص منطوق', 'line_down': 'خط الأعداد', 'down_step': 'بلا نموذج',
                 'sub20': 'بلا نموذج', 'line_up_sum': 'خط الأعداد: المحطات فوقه والقفزات تحته', 'up_step': 'بلا نموذج',
                 'nine_step': 'بلا نموذج', 'three': 'بلا نموذج', 'judge_three': 'بلا نموذج',
                 'ctx_sub20': 'صورة الموقف، والنص منطوق'})


# ---------------------------------------------------------------- مجال كل أداء: قائمة أعداد البنود الممكنة
def dom(perf):
    if perf == 'dots_flash':
        return [dict(n=n, v=v) for n in range(1, 6) for v in range(3)]
    if perf == 'five_flash':
        return [dict(n=n) for n in range(1, 6)]
    if perf in ('ten_flash', 'five_plus'):
        return [dict(n=n) for n in range(6, 11)]
    if perf == 'path_gap':
        return [dict(s=s, d=d, k=k) for d in (1, -1) for s in range(0, 21) for k in (1, 2, 3)
                if 0 <= s + 4 * d <= 20]
    if perf == 'count_next':
        return [dict(a=a, d=d) for a in range(1, 20) for d in (1, -1)]
    if perf in ('path_jump', 'addsub'):
        return [dict(a=a, b=b, op=op) for a in range(0, 11) for b in (1, 2) for op in (1, -1) if 0 <= a + op * b <= 10]
    if perf in ('discs', 'decomp'):
        return 'w'                                          # يُحدَّد بالمهارة (WHOLE)
    if perf in ('bond', 'cup', 'missing_add'):
        return 'w'
    if perf in ('path_add', 'add_small_first'):
        return [dict(small=s, big=b) for s in range(1, 10) for b in range(s + 1, 10) if s + b <= 10]
    if perf in ('ctx_add',):
        return [dict(a=a, b=b, c=c) for a in range(1, 10) for b in range(1, 10) if a + b <= 10 for c in range(4)]
    if perf in ('ctx_sub10', 'bond_sub', 'sub'):
        return [dict(a=a, b=b, c=c) for a in range(2, 11) for b in range(1, a) for c in range(4 if perf == 'ctx_sub10' else 1)]
    if perf == 'equal_missing':
        out = [dict(w=w, a=a, f=f) for w in range(2, 11) for a in range(1, w) for f in (0, 1)]
        out += [dict(w=w, a=a, f=2, c=c) for w in range(3, 11) for a in range(1, w) for c in range(1, w) if c != a and c != w - a]
        return out
    if perf == 'judge':
        out = []
        for w in range(3, 11):
            for a in range(1, w):
                for c in range(1, w):
                    if c not in (a, w - a):
                        out.append(dict(a=a, b=w - a, c=c, d=w - c))          # صحيح: مجموعان متساويان
                        out.append(dict(a=a, b=w - a, c=c, d=w - c + 1))      # خطأ بفارق 1
        return out
    # المرحلة 2
    if perf in ('frames2', 'tens_ones'):
        return [dict(n=n) for n in range(11, 21)]
    if perf in ('frames2_op', 'addsub20'):
        return [dict(a=a, b=b, op=op) for a in range(11, 20) for b in range(1, 9) for op in (1, -1)
                if (op > 0 and (a % 10) + b <= 9) or (op < 0 and b <= a % 10)]
    if perf in ('beads_double', 'double', 'beads_half', 'half'):
        return [dict(k=k) for k in range(1, 11)]
    if perf == 'ctx_half':
        return [dict(k=k, c=c) for k in range(2, 11) for c in range(2)]
    if perf in ('near_step', 'near'):
        return 'near'
    if perf == 'judge_near':
        return [dict(a=a, c=c) for a in range(1, 9) for c in (a + 1, a, a + 2)]
    if perf in ('frames2_add', 'ten_step', 'add20', 'ctx_add20'):
        return 'ten'
    if perf in ('line_down', 'down_step', 'sub20', 'line_up_sum', 'up_step', 'ctx_sub20'):
        return 'cross'
    if perf == 'nine_step':
        return [dict(b=b) for b in range(2, 10)]
    if perf == 'three':
        # العشرة في الأول والثالث (تُقدَّم بإعادة الترتيب)، أو في الثاني والثالث (يُبدأ من آخرها). لا يساوي الأول الثاني:
        # فيه العشرة في الموضعين معًا
        return ([dict(a=a, b=b, c=10 - a) for a in range(1, 10) for b in range(1, 10) if b != 10 - a and a != b]
                + [dict(a=a, b=b, c=10 - b) for a in range(1, 10) for b in range(1, 10) if a != 10 - b and a != b])
    if perf == 'judge_three':
        return [dict(a=a, b=b, c=10 - a, w=w) for a in range(1, 10) for b in range(1, 9) for w in (0, 1) if b != 10 - a]
    # المرحلة 3
    if perf in ('tens_model', 'tens_eq'):
        # «20 + 0 = ▢» ليس قراءة عدد من رقمين: المعادلة بلا آحاد. العشرات الكاملة تبقى في النموذج (30 حزمة بلا آحاد)
        return [dict(t=t, o=o) for t in range(1, 10) for o in range(0, 10)
                if (o or t > 1) and (o or perf == 'tens_model')]
    if perf in ('jump10_line', 'jump10'):
        return [dict(a=a, k=k, op=op) for a in range(11, 90) if a % 10 for k in (1, 2, 3) for op in (1, -1)
                if 10 < a + op * 10 * k < 100]
    if perf in ('wholetens_model', 'wholetens'):
        return [dict(a=a, b=b, op=op) for a in range(1, 10) for b in range(1, 10) for op in (1, -1)
                if 0 < a + op * b <= 10 and not (op < 0 and a == b)]
    if perf in ('round_line', 'round'):
        return [dict(v=v) for v in range(11, 100) if v % 10]
    if perf in ('comp_line', 'comp'):
        return [dict(a=a) for a in range(11, 100) if a % 10 and a < 90 or (a > 90 and a % 10)]
    if perf in ('hundred_line', 'hundred_step', 'hundred'):
        return [dict(a=a) for a in range(11, 90) if a % 10]
    if perf == 'change':
        return [dict(a=a, c=c) for a in range(11, 100) if a % 10 for c in range(2)]
    if perf in ('double_step', 'double2'):
        return [dict(a=a) for a in range(11, 50) if a % 10]
    if perf in ('half_step', 'half2', 'ctx_half2'):
        out = [dict(w=w) for w in range(22, 99, 2) if w % 10]
        return [dict(n, c=c) for n in out for c in range(2)] if perf == 'ctx_half2' else out
    if perf in ('bar', 'half_tens'):
        return [dict(w=w) for w in (10, 30, 50, 70, 90)]
    if perf in ('bridge_step', 'two_digit', 'ctx_big', 'jumps_add', 'jump_step', 'tens2_model', 'partition_step',
                'judge_partition', 'adjust_step', 'judge_adjust', 'transfer_model', 'transfer_step', 'slide_model',
                'slide_step'):
        return 'big'
    raise KeyError(perf)


# المرحلة 3: أزواج الأعداد لكل مهارة (العملية والعبور من صف المهارة)
def big_pairs(skill, perf):
    out = []
    if skill in ('3-2-2', '3-2-3'):
        op = 1 if skill == '3-2-2' else -1
        for a in range(12, 98):
            for b in range(2, 10):
                if a % 10 == 0:
                    continue
                if op > 0 and a % 10 + b > 10 and a + b < 100:
                    out.append(dict(a=a, b=b, op=1))
                if op < 0 and b > a % 10 and a - b > 10:
                    out.append(dict(a=a, b=b, op=-1))
    elif skill in ('3-3-1', '3-4-1'):
        out = [dict(a=a, b=b, op=1) for a in range(11, 90) for b in range(11, 90)
               if a % 10 and b % 10 and a % 10 + b % 10 <= 9 and a + b < 100]
    elif skill in ('3-3-2', '3-4-2'):
        out = [dict(a=a, b=b, op=1) for a in range(11, 90) for b in range(11, 90)
               if a % 10 and b % 10 and a % 10 + b % 10 >= 10 and a + b < 100]
    elif skill == '3-6-1':
        out = [dict(a=a, b=b, op=1) for a in range(11, 80) for b in (19, 29, 39, 49, 59) if a % 10 and a + b < 100]
    elif skill == '3-6-2':
        out = [dict(a=a, b=b, op=-1) for a in range(31, 100) for b in (19, 29, 39, 49) if a % 10 and a - b > 10]
    elif skill == '3-6-3':
        out = [dict(a=a, b=b, op=1) for a in range(11, 90) for b in range(11, 90)
               if a % 10 >= 7 and b % 10 > 10 - a % 10 and a + b < 100]
    elif skill == '3-6-4':
        out = [dict(a=a, b=b, op=-1) for a in range(31, 100) for b in range(18, 90)
               if b % 10 >= 7 and a % 10 and a - b > 3 and a + 10 - b % 10 < 100]
    if perf == 'ctx_big':
        out = [dict(n, c=c) for n in out for c in range(4)]
    if perf in ('judge_partition', 'judge_adjust'):
        out = [dict(n, w=w) for n in out for w in (0, 1)]
    return out


# المرحلة 2: مجالات تتوقف على المهارة
ADD_FIRST = {'2-4-1': (8, 9), '2-4-2': range(2, 10), '2-6-3': range(1, 11), '2-6-1': (9,)}
SUB_CROSS = {'2-5-1': True, '2-5-2': True, '2-5-3': True, '2-6-4': False}
NEAR = {'2-3-1': 1, '2-3-2': 2}


def dom2(skill, kind, perf):
    if kind == 'near':
        return [dict(a=a, d=NEAR[skill]) for a in range(1, 10 - NEAR[skill] + 1)]
    if kind == 'ten':
        cross = skill != '2-6-3'
        out = [dict(a=a, b=b) for a in ADD_FIRST[skill] for b in range(1, 11)
               if (a + b > 10 and b < 10 if cross else a + b <= 20)]
        if perf == 'ctx_add20':
            out = [dict(n, c=c) for n in out for c in range(4)]
        return out
    if kind == 'cross':
        cross = SUB_CROSS[skill]
        out = [dict(a=a, b=b) for a in range(11, 21) for b in range(1, 11)
               if a - b >= 1 and (not cross or (a - 10 < b < 10 and a < 20))]
        if skill == '2-5-2':                                # الإكمال للأعداد المتقاربة: المطروح 6 فأكثر (مثال الخريطة 13 − 9)
            out = [n for n in out if n['b'] >= 6]
        if perf == 'ctx_sub20':
            out = [dict(n, c=c) for n in out for c in range(4)]
        return out
    raise KeyError(kind)


WHOLE = {'1-3-1': range(2, 6), '1-3-2': range(6, 10), '1-3-3': range(3, 11)}


def domain(skill, perf):
    d = dom(perf)
    if d == 'w':
        return [dict(w=w, a=a) for w in WHOLE[skill] for a in range(1, w)]
    if d == 'big':
        return big_pairs(skill, perf)
    if isinstance(d, str):
        return dom2(skill, d, perf)
    return d


def fact(skill, perf, n):
    """الحقيقة الحسابية للبند (3.5): بها يُفحص ألا تتجاور حقيقتان متماثلتان."""
    if 'n' in n:
        # المجال الصغير (1-1، خمس كميات): الكمية نفسها تتكرر بصيغة مختلفة (3.5)، فالصيغة جزء من الحقيقة: ترتيب النقاط،
        # أو الإطار، أو المعادلة
        return [n['n'], {'dots_flash': 10 + n.get('v', 0), 'five_flash': 1, 'ten_flash': 1, 'five_plus': 2,
                         'frames2': 1, 'tens_ones': 2}[perf]]
    if perf in ('path_gap', 'count_next'):
        return [PERFS[perf](n)[2], 1]
    # المرحلة 3 أولًا: مفاتيحها تتداخل مع فروع المرحلة 2 أدناه
    if 't' in n:
        return [n['t'], n['o']]
    if 'v' in n:
        return [n['v']]
    if perf in ('bar', 'half_tens'):                       # المجال الصغير: الصيغة جزء من الحقيقة (3.5)
        return [n['w'], 1 if perf == 'bar' else 2]
    if 'w' in n and 'a' not in n:
        return [n['w']]
    if 'op' in n and 'k' in n:
        return [n['a'], 10 * n['k'], n['op']]
    if 'op' in n:
        return [n['a'], n['b'], n['op']]
    if 'big' in n:
        return [n['small'], n['big']]
    if 'w' in n:
        return [n['w'], min(n['a'], n['w'] - n['a'])]
    if perf == 'judge':
        return [n['a'] + n['b'], n['c']]
    if 'k' in n:                                            # الضعف والنصف: الحقيقة k + k = 2k
        return [n['k'], n['k']]
    if perf in ('near_step', 'near'):
        return [n['a'], n['a'] + n['d']]
    if perf == 'judge_near':
        return [n['a'], n['a'] + 2, n['c']]
    if perf == 'nine_step':
        return [9, n['b']]
    if perf in ('three', 'judge_three'):
        return [n['a'], n['b'], n['c']]
    if 'b' not in n and 'a' in n:                         # المرحلة 3: عدد واحد (المتمم، إلى 100، الباقي، الضعف)
        return [n['a']]
    return [n['a'], n['b']]


# ---------------------------------------------------------------- المهارات
def S(types, perf, slots):
    """types: أنواع الدليل من صف الخريطة. perf: الأداء لكل نوع، ومعه 'solve' لبنود الحساب بلا نموذج والفحص."""
    return dict(types=types, perf=perf, slots=slots)


SKILLS = {
    '1-1-1': S(['ف1', 'ف3'], {'ف1': 'dots_flash', 'ف3': 'five_flash', 'solve': 'five_flash'},
               [(3, 'العدد 1 أو 2', lambda n: n['n'] <= 2), (4, 'العدد 3 أو 4', lambda n: n['n'] in (3, 4)),
                (3, 'العدد 5', lambda n: n['n'] == 5)]),
    '1-1-2': S(['ف1', 'ف3'], {'ف1': 'ten_flash', 'ف3': 'five_plus', 'solve': 'five_plus'},
               [(4, 'العدد 6 أو 7', lambda n: n['n'] <= 7), (4, 'العدد 8 أو 9', lambda n: n['n'] in (8, 9)),
                (2, 'العدد 10', lambda n: n['n'] == 10)]),
    '1-2-1': S(['ف2', 'ف3'], {'ف2': 'path_gap', 'ف3': 'count_next', 'solve': 'count_next'},
               [(3, 'التالي حتى 10', lambda n: n['d'] > 0 and n['a'] < 10), (3, 'التالي من 10 إلى 19', lambda n: n['d'] > 0 and n['a'] >= 10),
                (2, 'السابق حتى 10', lambda n: n['d'] < 0 and n['a'] <= 10), (2, 'السابق من 11 إلى 19', lambda n: n['d'] < 0 and n['a'] > 10)]),
    '1-2-2': S(['ف1', 'ف3'], {'ف1': 'path_jump', 'ف3': 'addsub', 'solve': 'addsub'},
               [(3, 'زائد 1', lambda n: n['op'] > 0 and n['b'] == 1), (3, 'زائد 2', lambda n: n['op'] > 0 and n['b'] == 2),
                (2, 'ناقص 1', lambda n: n['op'] < 0 and n['b'] == 1), (2, 'ناقص 2', lambda n: n['op'] < 0 and n['b'] == 2)]),
    '1-3-1': S(['ف1', 'ف3'], {'ف1': 'discs', 'ف3': 'decomp', 'solve': 'decomp'},
               [(2, 'الكل 2 أو 3', lambda n: n['w'] <= 3), (4, 'الكل 4', lambda n: n['w'] == 4), (4, 'الكل 5', lambda n: n['w'] == 5)]),
    '1-3-2': S(['ف1', 'ف3'], {'ف1': 'bond', 'ف3': 'decomp', 'solve': 'decomp'},
               [(2, 'الكل 6', lambda n: n['w'] == 6), (3, 'الكل 7', lambda n: n['w'] == 7), (3, 'الكل 8', lambda n: n['w'] == 8),
                (2, 'الكل 9', lambda n: n['w'] == 9)]),
    '1-3-3': S(['ف1', 'ف2', 'ف3'], {'ف1': 'cup', 'ف2': 'bond', 'ف3': 'missing_add', 'solve': 'missing_add'},
               [(3, 'الكل حتى 6', lambda n: n['w'] <= 6), (4, 'الكل 7 أو 8', lambda n: n['w'] in (7, 8)),
                (3, 'الكل 9 أو 10', lambda n: n['w'] >= 9)]),
    '1-5-1': S(['ف1', 'ف3', 'ف4'], {'ف1': 'path_add', 'ف3': 'add_small_first', 'ف4': 'ctx_add', 'solve': 'add_small_first'},
               [(3, 'الأصغر 1', lambda n: n['small'] == 1), (4, 'الأصغر 2', lambda n: n['small'] == 2),
                (3, 'الأصغر 3 أو 4', lambda n: n['small'] in (3, 4))]),
    '1-5-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'bond_sub', 'ف3': 'sub', 'ف4': 'ctx_sub10', 'solve': 'sub'},
               [(3, 'الناتج 1 أو 2', lambda n: n['a'] - n['b'] <= 2), (4, 'الناتج من 3 إلى 5', lambda n: 3 <= n['a'] - n['b'] <= 5),
                (3, 'الناتج 6 فأكثر', lambda n: n['a'] - n['b'] >= 6)]),
    '1-5-3': S(['ف2', 'ف5'], {'ف2': 'equal_missing', 'ف5': 'judge', 'solve': 'equal_missing'},
               [(3, 'الناقص أولًا بعد =', lambda n: n['f'] == 0), (3, 'الناقص ثانيًا بعد =', lambda n: n['f'] == 1),
                (4, 'الميزان: مجموعان متساويان', lambda n: n['f'] == 2)]),
    # المرحلة 2
    '2-1-1': S(['ف1', 'ف3'], {'ف1': 'frames2', 'ف3': 'tens_ones', 'solve': 'tens_ones'},
               [(3, 'من 11 إلى 13', lambda n: n['n'] <= 13), (4, 'من 14 إلى 17', lambda n: 14 <= n['n'] <= 17),
                (3, 'من 18 إلى 20', lambda n: n['n'] >= 18)]),
    '2-1-2': S(['ف1', 'ف3'], {'ف1': 'frames2_op', 'ف3': 'addsub20', 'solve': 'addsub20'},
               [(5, 'جمع داخل الآحاد', lambda n: n['op'] > 0), (5, 'طرح داخل الآحاد', lambda n: n['op'] < 0)]),
    '2-2-1': S(['ف1', 'ف3'], {'ف1': 'beads_double', 'ف3': 'double', 'solve': 'double'},
               [(3, 'ضعف 1 إلى 4', lambda n: n['k'] <= 4), (4, 'ضعف 5 إلى 8', lambda n: 5 <= n['k'] <= 8),
                (3, 'ضعف 9 و10', lambda n: n['k'] >= 9)]),
    '2-2-2': S(['ف1', 'ف3', 'ف4'], {'ف1': 'beads_half', 'ف3': 'half', 'ف4': 'ctx_half', 'solve': 'half'},
               [(3, 'نصف 2 إلى 8', lambda n: n['k'] <= 4), (4, 'نصف 10 إلى 16', lambda n: 5 <= n['k'] <= 8),
                (3, 'نصف 18 و20', lambda n: n['k'] >= 9)]),
    '2-3-1': S(['ف2', 'ف3'], {'ف2': 'near_step', 'ف3': 'near', 'solve': 'near'},
               [(3, 'الأصغر حتى 3', lambda n: n['a'] <= 3), (4, 'الأصغر 4 إلى 6', lambda n: 4 <= n['a'] <= 6),
                (3, 'الأصغر 7 فأكثر', lambda n: n['a'] >= 7)]),
    '2-3-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'near_step', 'ف3': 'near', 'ف5': 'judge_near', 'solve': 'near'},
               [(3, 'الأصغر حتى 3', lambda n: n['a'] <= 3), (4, 'الأصغر 4 إلى 6', lambda n: 4 <= n['a'] <= 6),
                (3, 'الأصغر 7 و8', lambda n: n['a'] >= 7)]),
    '2-4-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'frames2_add', 'ف2': 'ten_step', 'ف3': 'add20', 'solve': 'add20'},
               [(5, 'مع 9', lambda n: n['a'] == 9), (5, 'مع 8', lambda n: n['a'] == 8)]),
    '2-4-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'ten_step', 'ف3': 'add20', 'ف4': 'ctx_add20', 'solve': 'add20'},
               [(4, 'الأول 6 أو 7', lambda n: n['a'] in (6, 7)), (3, 'الأول 2 إلى 5', lambda n: n['a'] <= 5),
                (3, 'الأول 8 أو 9', lambda n: n['a'] >= 8)]),
    '2-5-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'line_down', 'ف2': 'down_step', 'ف3': 'sub20', 'solve': 'sub20'},
               [(3, 'من 11 إلى 13', lambda n: n['a'] <= 13), (4, 'من 14 إلى 16', lambda n: 14 <= n['a'] <= 16),
                (3, 'من 17 إلى 19', lambda n: n['a'] >= 17)]),
    '2-5-2': S(['ف1', 'ف2', 'ف3'], {'ف1': 'line_up_sum', 'ف2': 'up_step', 'ف3': 'sub20', 'solve': 'sub20'},
               [(4, 'المطروح 8 أو 9', lambda n: n['b'] >= 8), (3, 'المطروح 7', lambda n: n['b'] == 7),
                (3, 'المطروح 6', lambda n: n['b'] == 6)]),
    '2-5-3': S(['ف3'], {'ف3': 'sub20', 'solve': 'sub20'},
               [(4, 'المطروح قريب من المطروح منه', lambda n: n['a'] - n['b'] <= 4),
                (3, 'الناتج من 5 إلى 7', lambda n: 5 <= n['a'] - n['b'] <= 7), (3, 'الناتج 8 فأكثر', lambda n: n['a'] - n['b'] >= 8)]),
    '2-6-1': S(['ف2', 'ف3'], {'ف2': 'nine_step', 'ف3': 'add20', 'solve': 'add20'},
               [(4, '9 مع 2 إلى 5', lambda n: n['a'] == 9 and n['b'] <= 5), (6, '9 مع 6 إلى 9', lambda n: n['a'] == 9 and n['b'] >= 6)]),
    '2-6-2': S(['ف3', 'ف5'], {'ف3': 'three', 'ف5': 'judge_three', 'solve': 'three'},
               [(6, 'العشرة في الأول والثالث: يُعاد الترتيب', lambda n: n['a'] + n['c'] == 10),
                (4, 'العشرة في الثاني والثالث: يُبدأ منهما', lambda n: n['b'] + n['c'] == 10)]),
    '2-6-3': S(['ف3', 'ف4'], {'ف3': 'add20', 'ف4': 'ctx_add20', 'solve': 'add20'},
               [(4, 'المجموع حتى 10', lambda n: n['a'] + n['b'] <= 10), (6, 'المجموع من 11 إلى 20', lambda n: n['a'] + n['b'] > 10)]),
    '2-6-4': S(['ف3', 'ف4'], {'ف3': 'sub20', 'ف4': 'ctx_sub20', 'solve': 'sub20'},
               [(4, 'بلا عبور', lambda n: n['b'] <= n['a'] - 10 or n['a'] <= 10), (6, 'بعبور', lambda n: 10 < n['a'] and n['b'] > n['a'] - 10)]),
    # المرحلة 3
    '3-1-1': S(['ف1', 'ف3'], {'ف1': 'tens_model', 'ف3': 'tens_eq', 'solve': 'tens_eq'},
               [(3, 'العشرات حتى 3', lambda n: n['t'] <= 3), (4, 'العشرات 4 إلى 6', lambda n: 4 <= n['t'] <= 6),
                (3, 'العشرات 7 فأكثر', lambda n: n['t'] >= 7)]),
    '3-1-2': S(['ف1', 'ف3'], {'ف1': 'jump10_line', 'ف3': 'jump10', 'solve': 'jump10'},
               [(3, 'زائد 10', lambda n: n['op'] > 0 and n['k'] == 1), (3, 'زائد عشرات', lambda n: n['op'] > 0 and n['k'] > 1),
                (2, 'ناقص 10', lambda n: n['op'] < 0 and n['k'] == 1), (2, 'ناقص عشرات', lambda n: n['op'] < 0 and n['k'] > 1)]),
    '3-1-3': S(['ف1', 'ف3'], {'ف1': 'wholetens_model', 'ف3': 'wholetens', 'solve': 'wholetens'},
               [(5, 'جمع عشرات', lambda n: n['op'] > 0), (5, 'طرح عشرات', lambda n: n['op'] < 0)]),
    '3-1-4': S(['ف1', 'ف3'], {'ف1': 'round_line', 'ف3': 'round', 'solve': 'round'},
               [(4, 'يُقرَّب إلى الأقل', lambda n: n['v'] % 10 < 5),
                (2, 'الآحاد 5: المسافتان متساويتان، فإلى العشرة الأكبر', lambda n: n['v'] % 10 == 5),
                (4, 'يُقرَّب إلى الأكثر', lambda n: n['v'] % 10 > 5)]),
    '3-2-1': S(['ف1', 'ف3'], {'ف1': 'comp_line', 'ف3': 'comp', 'solve': 'comp'},
               [(3, 'المتمم 1 إلى 3', lambda n: 10 - n['a'] % 10 <= 3), (4, 'المتمم 4 إلى 6', lambda n: 4 <= 10 - n['a'] % 10 <= 6),
                (3, 'المتمم 7 إلى 9', lambda n: 10 - n['a'] % 10 >= 7)]),
    '3-2-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'bridge_step', 'ف3': 'two_digit', 'ف4': 'ctx_big', 'solve': 'two_digit'},
               [(4, 'يزيد 2 إلى 5', lambda n: n['b'] <= 5), (6, 'يزيد 6 إلى 9', lambda n: n['b'] >= 6)]),
    '3-2-3': S(['ف2', 'ف3', 'ف4'], {'ف2': 'bridge_step', 'ف3': 'two_digit', 'ف4': 'ctx_big', 'solve': 'two_digit'},
               [(4, 'ينقص 2 إلى 5', lambda n: n['b'] <= 5), (6, 'ينقص 6 إلى 9', lambda n: n['b'] >= 6)]),
    '3-3-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'jumps_add', 'ف2': 'jump_step', 'ف3': 'two_digit', 'solve': 'two_digit'},
               [(5, 'المجموع حتى 60', lambda n: n['a'] + n['b'] <= 60), (5, 'المجموع فوق 60', lambda n: n['a'] + n['b'] > 60)]),
    '3-3-2': S(['ف1', 'ف2', 'ف3', 'ف4'], {'ف1': 'jumps_add', 'ف2': 'jump_step', 'ف3': 'two_digit', 'ف4': 'ctx_big',
                                          'solve': 'two_digit'},
               [(5, 'آحاد المجموع حتى 3', lambda n: (n['a'] + n['b']) % 10 <= 3), (5, 'آحاد المجموع 4 فأكثر', lambda n: (n['a'] + n['b']) % 10 >= 4)]),
    '3-4-1': S(['ف1', 'ف3'], {'ف1': 'tens2_model', 'ف3': 'two_digit', 'solve': 'two_digit'},
               [(5, 'المجموع حتى 60', lambda n: n['a'] + n['b'] <= 60), (5, 'المجموع فوق 60', lambda n: n['a'] + n['b'] > 60)]),
    '3-4-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'partition_step', 'ف3': 'two_digit', 'ف5': 'judge_partition', 'solve': 'two_digit'},
               [(5, 'آحاد المجموع حتى 3', lambda n: (n['a'] + n['b']) % 10 <= 3), (5, 'آحاد المجموع 4 فأكثر', lambda n: (n['a'] + n['b']) % 10 >= 4)]),
    '3-6-1': S(['ف2', 'ف3'], {'ف2': 'adjust_step', 'ف3': 'two_digit', 'solve': 'two_digit'},
               [(5, 'زائد 19 أو 29', lambda n: n['b'] <= 29), (5, 'زائد 39 فأكثر', lambda n: n['b'] >= 39)]),
    '3-6-2': S(['ف2', 'ف3', 'ف5'], {'ف2': 'adjust_step', 'ف3': 'two_digit', 'ف5': 'judge_adjust', 'solve': 'two_digit'},
               [(5, 'ناقص 19 أو 29', lambda n: n['b'] <= 29), (5, 'ناقص 39 أو 49', lambda n: n['b'] >= 39)]),
    '3-6-3': S(['ف1', 'ف2', 'ف3'], {'ف1': 'transfer_model', 'ف2': 'transfer_step', 'ف3': 'two_digit', 'solve': 'two_digit'},
               [(5, 'آحاد الأول 8 أو 9', lambda n: n['a'] % 10 >= 8), (5, 'آحاد الأول 7', lambda n: n['a'] % 10 == 7)]),
    '3-6-4': S(['ف1', 'ف2', 'ف3'], {'ف1': 'slide_model', 'ف2': 'slide_step', 'ف3': 'two_digit', 'solve': 'two_digit'},
               [(5, 'آحاد المطروح 8 أو 9', lambda n: n['b'] % 10 >= 8), (5, 'آحاد المطروح 7', lambda n: n['b'] % 10 == 7)]),
    '3-7-1': S(['ف1', 'ف2', 'ف3'], {'ف1': 'hundred_line', 'ف2': 'hundred_step', 'ف3': 'hundred', 'solve': 'hundred'},
               [(3, 'من أقل من 40', lambda n: n['a'] < 40), (4, 'من 40 إلى 69', lambda n: 40 <= n['a'] < 70),
                (3, 'من 70 فأكثر', lambda n: n['a'] >= 70)]),
    '3-7-2': S(['ف4'], {'ف4': 'change', 'solve': 'change'},
               [(3, 'الثمن أقل من 40', lambda n: n['a'] < 40), (4, 'الثمن 40 إلى 69', lambda n: 40 <= n['a'] < 70),
                (3, 'الثمن 70 فأكثر', lambda n: n['a'] >= 70)]),
    '3-8-1': S(['ف2', 'ف3'], {'ف2': 'double_step', 'ف3': 'double2', 'solve': 'double2'},
               [(5, 'آحاد 1 إلى 4', lambda n: n['a'] % 10 <= 4), (5, 'آحاد 5 إلى 9', lambda n: n['a'] % 10 >= 5)]),
    '3-8-2': S(['ف2', 'ف3', 'ف4'], {'ف2': 'half_step', 'ف3': 'half2', 'ف4': 'ctx_half2', 'solve': 'half2'},
               [(5, 'عشرات زوجية', lambda n: (n['w'] // 10) % 2 == 0), (5, 'عشرات فردية', lambda n: (n['w'] // 10) % 2 == 1)]),
    '3-8-3': S(['ف1', 'ف3'], {'ف1': 'bar', 'ف3': 'half_tens', 'solve': 'half_tens'},
               [(4, '10 أو 30', lambda n: n['w'] <= 30), (3, '50', lambda n: n['w'] == 50), (3, '70 أو 90', lambda n: n['w'] >= 70)]),
}
MORE_PRACTICE = 12
PRE_TEACH = ('gate', 'regate', 'opening', 'short', 'tryfirst')
UNTAUGHT = {'3-1-4': lambda n: n['v'] % 10 != 5}            # التساوي يُعلَّم في الدرس (قرار الأب، 25 نوفمبر)
LESSON_FIXED = {'3-1-4': [('lesson.watch', 'round_line', dict(v=24, dist=True)),
                          ('lesson.model', 'round_line', dict(v=25, dist=True, explain=True)),
                          ('lesson.model', 'round_line', dict(v=26, dist=True))]}


def slot_order(skill):
    """خانات الفحص العشر بترتيب عرضها: العائلات متداخلة لا متتابعة، فلا تتجاور خانتان من عائلة واحدة ما أمكن، ولا تتجاور
    حقيقتان متماثلتان في المجال الصغير. يعيد [(الوصف، الشرط)] بطول 10."""
    left = [[c, d, p] for c, d, p in SKILLS[skill]['slots']]
    out, prev = [], None
    while any(x[0] for x in left):
        cand = sorted((x for x in left if x[0] and x[1] != prev), key=lambda x: -x[0]) or [x for x in left if x[0]]
        x = cand[0]
        x[0] -= 1
        out.append((x[1], x[2]))
        prev = x[1]
    return out


# ---------------------------------------------------------------- البناء
class Picker:
    """يأخذ أعداد البنود بالدور من مجال كل أداء بعد خلطه: البنود المتتالية من أداء واحد مختلفة الأعداد."""

    def __init__(self, rng):
        self.rng, self.lists, self.pos = rng, {}, {}

    def take(self, skill, perf, pred=lambda n: True, avoid=None):
        key = (skill, perf)
        if key not in self.lists:
            lst = list(domain(skill, perf))
            self.rng.shuffle(lst)
            self.lists[key], self.pos[key] = lst, 0
        lst = self.lists[key]
        for k in range(len(lst)):
            n = lst[(self.pos[key] + k) % len(lst)]
            if pred(n) and (avoid is None or fact(skill, perf, n) != avoid):
                self.pos[key] = (self.pos[key] + k + 1) % len(lst)
                return dict(n)
        if avoid is not None:                               # المجال الصغير: لا بديل غيره (بديل خانة الفحص مثلًا)
            return self.take(skill, perf, pred)
        raise RuntimeError('لا أعداد تحقق الشرط: %s %s' % (skill, perf))


def make(skill, group, role, ev, perf, n, count, slot=None, alt_of=None):
    count[(skill, group)] = count.get((skill, group), 0) + 1
    ar, en, ans, model = PERFS[perf](n)
    it = dict(id='%s/%s/%02d' % (skill, group, count[(skill, group)]), skill=skill, group=group, role=role, evidence=ev,
              performance=perf, numbers=n, resource=RESOURCE[perf],
              answer_type='ج8' if perf in CARD_PERFS else 'ج1', answer=ans, text_ar=ar, text_en=en, audio_ar=ar,
              audio_en=en, wrong={}, slot=slot, alt_of=alt_of, graded=True, fact=fact(skill, perf, n))
    if perf in CARD_PERFS:
        it['card_set'] = CARD_PERFS[perf]
        it['cards'] = ['yes', 'no']
    if model is not None:
        if role in ('lesson.watch', 'lesson.model') and model.get('flash'):
            model = dict(model, flash=False)                # في الشرح يبقى النموذج ظاهرًا، والومضة بعده
        it['model'] = model
    return it


def build(seed=20261119):
    rng = random.Random(seed)
    pick, count, items = Picker(rng), {}, []
    last = {}

    def put(skill, group, role, ev, perf, pred=lambda n: True, **kw):
        if group in PRE_TEACH and skill in UNTAUGHT:        # ما يُعلَّم في الدرس لا يُسأل عنه قبله
            pred = (lambda p0, u: lambda n: p0(n) and u(n))(pred, UNTAUGHT[skill])
        n = pick.take(skill, perf, pred, avoid=last.get((skill, group)))
        it = make(skill, group, role, ev, perf, n, count, **kw)
        last[(skill, group)] = it['fact']
        items.append(it)
        return it

    for skill, sp in SKILLS.items():
        P, types = sp['perf'], sp['types']
        solve = P['solve']
        main, step = P.get('ف1', solve), P.get('ف2', solve)
        if skill in LESSON_FIXED:                           # درس بأمثلة مختارة (التقريب: 24 ثم 25 ثم 26)
            for role, perf, n in LESSON_FIXED[skill]:
                items.append(make(skill, 'lesson', role, None, perf, dict(n), count))
                last[(skill, 'lesson')] = items[-1]['fact']
        else:
            put(skill, 'lesson', 'lesson.watch', None, main)
            for _ in range(2):
                put(skill, 'lesson', 'lesson.model', None, main)
        for _ in range(2):
            put(skill, 'lesson', 'lesson.fade', None, step)
        for k in range(2):                                  # ودرس التقريب: أول بند بلا نموذج حالة تساوٍ
            put(skill, 'lesson', 'lesson.nomodel', None, solve,
                (lambda n: n['v'] % 10 == 5) if skill == '3-1-4' and k == 0 else (lambda n: True))
        tries, guided = opening_types(types)               # بأنواع طبقة البنود نفسها، فلا يخالف المحتوى ما تطلبه
        for t in tries:
            put(skill, 'opening', 'opening.try', t, P.get(t, solve))
        for t in guided:
            put(skill, 'opening', 'opening.guided', t, P[t])
        for _ in range(6):
            put(skill, 'practice', 'practice', None, solve)
        for rnd in (1, 2):
            for t in types:
                for i in range(4):
                    put(skill, 'evidence', 'evidence' if i < 2 else 'evidence.reserve', t, P[t])['round'] = rnd
        plan = gate_plan(types)
        for g in ('gate', 'regate'):
            for t in plan:
                put(skill, g, 'gate', t, P.get(t, solve))
            for t in types:
                for _ in range(2):
                    put(skill, g, 'gate.compensation', t, P[t])
            for t in types:
                for _ in range(2):
                    put(skill, g, 'gate.alternate', t, P[t])
        for t in short_types(types):
            put(skill, 'short', 'short_check', t, P.get(t, solve))
        for attempt in ('A', 'B', 'C'):
            for k, (_d, pred) in enumerate(slot_order(skill), 1):
                m = put(skill, 'check' + attempt, 'check', 'ف3', solve, pred, slot=k)
                put(skill, 'check' + attempt, 'check.alternate', 'ف3', solve, pred, slot=k, alt_of=m['id'])
        for rnd in (1, 2, 3):
            for _ in range(5):
                put(skill, 'deferred', 'deferred_check', 'ف3', solve, slot=rnd)
            for _ in range(5):
                put(skill, 'deferred', 'deferred_check.alternate', 'ف3', solve, slot=rnd)['set'] = 1
        for t in types:
            for _ in range(2):
                put(skill, 'tryfirst', 'opening.try', t, P[t])
        for rnd in (1, 2):
            for t in types:
                put(skill, 'evidence', 'evidence.alternate', t, P[t])['round'] = rnd
        forms = [solve] + [P[t] for t in types if P[t] != solve]
        for k in range(MORE_PRACTICE):
            put(skill, 'more', 'practice.more', None, forms[k % len(forms)] if k % 2 else solve)
    for _ in range(4):                                      # التأخير والتتابع معًا: إصلاح أحدهما قد يمسّ الآخر
        left, stuck = repair(items), unstick(items)
        if not left and not stuck:
            break
    if left or stuck:
        raise RuntimeError('بقي ما لا يُصلح: تتابع %d، وبلا موضع تأخير %r' % (len(left), stuck[:5]))
    path = ['lesson', 'opening', 'practice', 'evidence', 'checkA', 'checkB', 'checkC', 'deferred', 'more']
    for skill in SKILLS:                                    # هل سبق عرض الحقيقة نفسها في مسار التعلّم؟ (3.5)
        seen = set()
        for g in path:
            now = set()
            for it in items:
                if it['skill'] == skill and it['group'] == g:
                    it['fact_seen_before'] = tuple(it['fact']) in seen
                    if it['role'] != 'evidence.alternate':
                        now.add(tuple(it['fact']))
            seen |= now
        for it in items:
            if it['skill'] == skill and 'fact_seen_before' not in it:
                it['fact_seen_before'] = False
    return items


# ---------------------------------------------------------------- التحقق المستقل
def truth(it):
    """الجواب من الأعداد، بلا render."""
    n, p = it['numbers'], it['performance']
    if p in ('dots_flash', 'five_flash', 'ten_flash', 'five_plus'):
        return n['n']
    if p == 'path_gap':
        return n['s'] + n['k'] * n['d']
    if p == 'count_next':
        return n['a'] + n['d']
    if p in ('path_jump', 'addsub'):
        return n['a'] + n['b'] if n['op'] > 0 else n['a'] - n['b']
    if p in ('discs', 'decomp', 'bond', 'cup', 'missing_add'):
        return n['w'] - n['a']
    if p in ('path_add', 'add_small_first'):
        return n['small'] + n['big']
    if p == 'ctx_add':
        return n['a'] + n['b']
    if p in ('ctx_sub10', 'bond_sub', 'sub'):
        return n['a'] - n['b']
    if p == 'equal_missing':
        return n['w'] - (n['c'] if n['f'] == 2 else n['a'])
    if p == 'judge':
        return 'yes' if n['a'] + n['b'] == n['c'] + n['d'] else 'no'
    if p in ('frames2', 'tens_ones'):
        return n['n']
    if p in ('frames2_op', 'addsub20'):
        return n['a'] + n['b'] if n['op'] > 0 else n['a'] - n['b']
    if p in ('beads_double', 'double'):
        return 2 * n['k']
    if p in ('beads_half', 'half', 'ctx_half'):
        return n['k']
    if p == 'near_step':
        return 2 * n['a'] if n['d'] == 1 else n['a'] + 1
    if p == 'near':
        return 2 * n['a'] + n['d']
    if p == 'judge_near':
        return 'yes' if 2 * n['c'] == 2 * n['a'] + 2 else 'no'
    if p == 'ten_step':
        return n['a'] + n['b'] - 10
    if p in ('frames2_add', 'add20', 'ctx_add20'):
        return n['a'] + n['b']
    if p in ('line_down', 'sub20', 'line_up_sum', 'ctx_sub20'):
        return n['a'] - n['b']
    if p == 'down_step':
        return 10 - (n['a'] - n['b'])
    if p == 'up_step':
        return n['a'] - 10
    if p == 'nine_step':
        return 10 + n['b']
    if p == 'three':
        return n['a'] + n['b'] + n['c']
    if p == 'judge_three':
        return 'yes' if n['w'] == 0 else 'no'
    if p in ('tens_model', 'tens_eq'):
        return 10 * n['t'] + n['o']
    if p in ('jump10_line', 'jump10'):
        return n['a'] + n['op'] * 10 * n['k']
    if p in ('wholetens_model', 'wholetens'):
        return 10 * n['a'] + n['op'] * 10 * n['b']
    if p in ('round_line', 'round'):
        return int(round(n['v'] / 10.0 + 1e-9)) * 10
    if p in ('comp_line', 'comp'):
        return -n['a'] % 10
    if p == 'bridge_step':
        return (n['a'] + n['b']) % 10 if n['op'] > 0 else 10 - (n['a'] - n['b']) % 10
    if p == 'tens2_model':
        return n['a'] // 10 * 10 + n['b'] // 10 * 10
    if p in ('two_digit', 'ctx_big', 'jumps_add'):
        return n['a'] + n['op'] * n['b'] if 'op' in n else n['a'] + n['b']
    if p == 'jump_step':
        return n['b'] % 10
    if p == 'partition_step':
        return n['a'] % 10 + n['b'] % 10
    if p in ('judge_partition', 'judge_adjust'):
        return 'yes' if n['w'] == 0 else 'no'
    if p == 'adjust_step':
        return n['a'] + n['b'] + 1 if n['op'] > 0 else n['a'] - n['b'] - 1
    if p == 'transfer_model':
        return (n['a'] // 10 + 1) * 10
    if p == 'transfer_step':
        return n['a'] + n['b'] - (n['a'] // 10 + 1) * 10
    if p == 'slide_model':
        return n['a'] - n['b']
    if p == 'slide_step':
        return (n['b'] // 10 + 1) * 10
    if p in ('hundred_line', 'hundred', 'change'):
        return 100 - n['a']
    if p == 'hundred_step':
        return 100 - (n['a'] // 10 + 1) * 10
    if p == 'double_step':
        return 2 * (n['a'] % 10)
    if p == 'double2':
        return 2 * n['a']
    if p in ('half_step', 'half2', 'ctx_half2', 'bar', 'half_tens'):
        return n['w'] // 2
    raise KeyError(p)


def check(it):
    """مخالفات البند: الجواب، والمجال، والرسم، والنص."""
    bad = []
    ans = truth(it)
    if ans != it['answer']:
        bad.append('جواب لا يطابق إعادة الحساب')
    if isinstance(ans, int) and not 0 <= ans <= 100:
        bad.append('جواب خارج المجال')
    m = it.get('model')
    n = it['numbers']
    if m is not None:
        k = m['kind']
        ok = {'dots': lambda: m['n'] == ans and 0 <= m['layout'] <= 2,
              'frame': lambda: m['n'] == ans and m['n'] <= m['size'],
              'path': lambda: (m.get('hide') is not None and m['start'] + m['hide'] * m['step'] == ans)
              or (m.get('jump') is not None and m['mark'] + m['jump'] == ans and 0 <= ans < m['len']),
              'discs': lambda: m['blue'] == ans and m['red'] + m['blue'] == n['w'],
              'bond': lambda: m['whole'] - m['part'] == ans,
              'cup': lambda: m['total'] - m['shown'] == ans,
              'frames2': lambda: m['n'] == (n['n'] if 'n' in n else n['a']) and m['n'] <= 20,
              'beads': lambda: m['rows'][0] == m['rows'][1] and (m['rows'][0] == ans if m['hide'] == 1
                                                                 else 2 * m['rows'][0] == ans),
              'jumps': lambda: m['start'] + (1 if m['line'] == 'up' else -1) * sum(m['jumps']) == m['stations'][-1]
              and (m.get('ten') is False or m['stations'][0] == 10)
              and (sum(m['jumps']) == ans if m['hide'] is None
                   else (m['jumps'] if m['hide'][0] == 'jump' else m['stations'])[m['hide'][1]] == ans),
              'tens': lambda: 10 * (m['tens'] + m.get('plus', 0) - m.get('minus', 0)) + m['ones'] == ans
              or 10 * m['tens'] + m['ones'] == ans,
              'tens2': lambda: 10 * m['a'][0] + m['a'][1] == n['a'] and 10 * m['b'][0] + m['b'][1] == n['b'],
              'round': lambda: m['lo'] <= m['v'] <= m['hi'] and ans in (m['lo'], m['hi']) and m['v'] == n['v'],
              'slide': lambda: m['a'] - m['b'] == ans and (m['b'] + m['d']) % 10 == 0,
              'bar': lambda: m['whole'] == 2 * ans}.get(k)
        if ok is None or not ok():
            bad.append('رسم يخالف أعداد البند أو جوابه')
    for txt in (it['text_ar'], it['text_en']):
        if txt.count(LRI) != txt.count(PDI) or '-' in txt or '{' in txt:
            bad.append('نص غير سليم')
    if any('؀' <= ch <= 'ۿ' for ch in it['text_en']):
        bad.append('حروف عربية في النص الإنجليزي')
    if it['performance'] not in CARD_PERFS and '=' in it['text_ar'] and BOX not in it['text_ar']:
        bad.append('معادلة بلا مجهول: الجواب ظاهر')
    return bad


TYPES = {s: sp['types'] for s, sp in SKILLS.items()}
SLOT_DESC = {s: [(c, d) for c, d, _p in sp['slots']] for s, sp in SKILLS.items()}

# ---------------------------------------------------------------- التتابع (3.5): لا تتجاور حقيقتان متماثلتان أثناء التشغيل
def slot_pred(skill, slot):
    return slot_order(skill)[slot - 1][1]


def repair(items, rounds=20):
    """يشغّل أنشطة طبقة البنود بكل فروعها (content_sequence.collect) على مهارات المولّد، ويغيّر أعداد البند الثاني من كل
    زوج متجاور بالحقيقة نفسها: يُختار له من مجال أدائه، وبشرط خانته في الفحص، ما لا تساوي حقيقتُه حقيقةَ أي بند يجاوره
    قبله أو بعده. يتكرر حتى لا يبقى زوج أو لا يبقى ما يُختار. يعيد الأزواج الباقية."""
    from content_sequence import collect, violations
    own = [i for i in items if i['skill'] in SKILLS]
    by_id = {i['id']: i for i in own}
    rng = random.Random(7)
    for _ in range(rounds):
        pairs, by, _n = collect(own, TYPES)
        bad = violations(pairs, by)
        if not bad:
            return []
        near = {}
        for a, b, _how, _label in pairs:
            near.setdefault(a, set()).add(b)
            near.setdefault(b, set()).add(a)
        changed = set()
        for a, b, _how, _label, _f in bad:
            if a in changed or b in changed:
                continue
            for it in (by_id[b], by_id[a]):                 # الثاني أولًا، ثم الأول إن لم يبق للثاني ما يُختار
                avoid = {tuple(by_id[x]['fact']) for x in near.get(it['id'], ()) if x in by_id}
                pred = slot_pred(it['skill'], it['slot']) if it['group'].startswith('check') else (lambda n: True)
                opts = [n for n in domain(it['skill'], it['performance'])
                        if pred(n) and tuple(fact(it['skill'], it['performance'], n)) not in avoid]
                if not opts:
                    continue
                n = dict(rng.choice(opts))
                ar, en, ans, model = PERFS[it['performance']](n)
                it.update(numbers=n, text_ar=ar, text_en=en, audio_ar=ar, audio_en=en, answer=ans,
                          fact=fact(it['skill'], it['performance'], n))
                if model is not None:
                    if it['role'] in ('lesson.watch', 'lesson.model') and model.get('flash'):
                        model = dict(model, flash=False)
                    it['model'] = model
                changed.add(it['id'])
                break
        if not changed:
            break
    pairs, by, _n = collect(own, TYPES)
    return violations(pairs, by)


def phase_ends(items):
    """البنود الأصلية التي لا موضع بعدها في مرحلتها، فلا تُؤخَّر (item_layer.Activity._defer): آخر البوابة، وثاني التعويضية
    لكل نوع، وثالث التحقق القصير، والخانة العاشرة، وخامس كل جولة احتفاظ."""
    from content_sequence import ContentSource
    src, out = ContentSource(items), set()
    for skill, ts in TYPES.items():
        for g in ('gate', 'regate'):
            out.add(src.by[(skill, g, 'gate')][-1]['id'])
            out.update(src._typed(skill, g, 'gate.compensation', t)[1]['id'] for t in ts)
        out.add(src.by[(skill, 'short', 'short_check')][2]['id'])
        out.update(i['id'] for a in 'ABC' for i in src.by[(skill, 'check' + a, 'check')] if i['slot'] == 10)
        for rnd in (1, 2, 3):
            out.add([i for i in src.by[(skill, 'deferred', 'deferred_check')] if i['slot'] == rnd][-1]['id'])
    return out


def phase_after(items, it):
    """بنود مرحلة البند التي تأتي بعده: البوابة، والتعويضية من نوعه، والتحقق القصير، ومحاولة الفحص، وجولة الاحتفاظ."""
    same = [x for x in items if x['skill'] == it['skill'] and x['group'] == it['group'] and x['role'] == it['role']]
    if it['role'] == 'gate.compensation':
        same = [x for x in same if x['evidence'] == it['evidence']]
    if it['role'] == 'deferred_check':
        same = [x for x in same if x['slot'] == it['slot']]
    return same[same.index(it) + 1:]


def unstick(items, rounds=10):
    """بند تقييم أصلي يكرر حقيقة ما قبله عند الدخول يُؤخَّر إلى أقرب موضع في مرحلته لا تجاور فيه حقيقتُه ما حوله. فإن لم
    يكن له موضع وهو ليس آخر مرحلته عُرض موسومًا. هذه الحالة تُمنع هنا كما يمنعها مولّد الشريحة: تُغيَّر أعداده فلا تساوي
    حقيقتُه حقيقة أي بند بعده في مرحلته ولا حقيقة بند يجاوره. يعيد البنود الباقية."""
    from content_sequence import collect
    own = [i for i in items if i['skill'] in SKILLS]
    by_id = {i['id']: i for i in own}
    ends = phase_ends(own)
    rng = random.Random(11)
    left = []
    for _ in range(rounds):
        stuck = set()
        pairs, _by, _n = collect(own, TYPES, stuck)
        left = sorted({i for i, _r, _l in stuck if 'alternate' not in by_id[i]['role'] and i not in ends})
        if not left:
            return []
        near = {}
        for a, b, _h, _l in pairs:
            near.setdefault(a, set()).add(b)
            near.setdefault(b, set()).add(a)
        for i in left:
            it = by_id[i]
            avoid = {tuple(x['fact']) for x in phase_after(own, it)}
            avoid |= {tuple(by_id[x]['fact']) for x in near.get(i, ()) if x in by_id}
            pred = slot_pred(it['skill'], it['slot']) if it['group'].startswith('check') else (lambda n: True)
            opts = [n for n in domain(it['skill'], it['performance'])
                    if pred(n) and tuple(fact(it['skill'], it['performance'], n)) not in avoid]
            if opts:
                rerender(it, dict(rng.choice(opts)))
    return left


def rerender(it, n):
    ar, en, ans, model = PERFS[it['performance']](n)
    it.update(numbers=n, text_ar=ar, text_en=en, audio_ar=ar, audio_en=en, answer=ans,
              fact=fact(it['skill'], it['performance'], n))
    if model is not None:
        if it['role'] in ('lesson.watch', 'lesson.model') and model.get('flash'):
            model = dict(model, flash=False)
        it['model'] = model


if __name__ == '__main__':
    from collections import Counter
    its = build()
    print(len(its), Counter(i['skill'] for i in its))
    probs = Counter(p for i in its for p in check(i))
    print(probs or 'لا مخالفة')
