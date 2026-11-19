#!/usr/bin/env python3
"""محتوى الشريحة الأولى: الوحدة 1-4 (1-4-1، 1-4-2) والوحدة 3-5 (3-5-1، 3-5-2، 3-5-3).

    python3 slice_content.py            # يولّد slice-content.json و slice-content.md ويتحقق منهما

يولّد البنود من شروط الخانات في 10.2 من الخريطة، ثم يتحقق منها بدوال مستقلة عن التوليد:
الجواب يُعاد حسابه من أعداد البند، وكل بند وكل بديل يُفحص بشرط خانته، والنصان العربي والإنجليزي
يُفحصان. البذرة ثابتة، فالمخرجات واحدة في كل تشغيل. هذا ملف محتوى، وليس واجهة ولا تسجيل صوت.
"""
import json
import random
import sys
from collections import Counter, defaultdict

LRI, PDI, MINUS, BOX = '⁦', '⁩', '−', '▢'
SEED = 20261111
HOW_SLOT = {'3-5-3': 8}                                 # بعد خانتين من خانات العبور الأربع (7-10) في فحص 3-5-3 (10.2)
MORE_PRACTICE = 12                                     # بنود التدريب الإضافي لكل مهارة: مجموعتان من 6
LEDGER = 'content-ledger.json'                         # سجل إصدارات المحتوى: رقم وبصمة لكل حزمة صدرت


def eq(s):
    """معادلة معزولة الاتجاه من اليسار إلى اليمين، كما في 7.6."""
    return LRI + ' ' + s + ' ' + PDI


# ---------------------------------------------------------------- النصوص باللغتين
T = {
    'frame_empty': ('كم خانة فارغة في الإطار؟', 'How many boxes in the frame are empty?'),
    'frame_counters': ('عدد الخانات الفارغة {e}. كم قرصًا في الإطار؟',
                       'Empty boxes: {e}. How many counters are in the frame?'),
    'make_ten': ('{n} وكم تصير 10؟', '{n} and how many make 10?'),
    'missing': ('ما العدد الناقص؟ {eq}', 'What number is missing? {eq}'),
    'step_pair': ('{eq1} لأن {eq2}. ما العدد الذي يكمل الاثنتين؟',
                  '{eq1} because {eq2}. What number completes both?'),
    'ctx_eggs': ('في العلبة 10 أماكن للبيض. عدد البيض فيها {n}. كم مكانًا فارغًا؟',
                 'The box has 10 places for eggs. Eggs in it: {n}. How many places are empty?'),
    'ctx_bus': ('في الحافلة الصغيرة 10 مقاعد. عدد الركاب {n}. كم مقعدًا بقي فارغًا؟',
                'The minibus has 10 seats. Passengers: {n}. How many seats are still empty?'),
    'ctx_balloons': ('كان مع عمر 10 بالونات. عدد ما طار منها {n}. كم بالونًا بقي؟',
                     'Omar had 10 balloons. Balloons that flew away: {n}. How many are left?'),
    'ctx_steps': ('السلّم 10 درجات. عدد ما صعدته سلمى {n}. كم درجة بقيت؟',
                  'The stairs have 10 steps. Steps Salma has climbed: {n}. How many steps are left?'),
    'line_back': ('الخط يبدأ من {a} ثم يقفز للخلف: {jumps_ar}. عند أي عدد يقف؟',
                  'The line starts at {a} and jumps back: {jumps_en}. What number does it land on?'),
    'station_back': ('{chain_ar}. ما العدد الناقص؟', '{chain_en}. What number is missing?'),
    'solve': ('احسب: {eq}', 'Work out: {eq}'),
    'line_up': ('على الخط: من {b} إلى {t} قفزة {j1}، ومن {t} إلى {a} قفزة {j2}. كم {eq}؟',
                'On the line: from {b} to {t} is a jump of {j1}, and from {t} to {a} is a jump of {j2}. '
                'What is {eq}?'),
    'jump_missing': ('لحساب {eq}: من {b} إلى {t} قفزة {j1}، ومن {t} إلى {a} قفزة ' + BOX + '. ما القفزة الناقصة؟',
                     'To work out {eq}: from {b} to {t} is a jump of {j1}, and from {t} to {a} is a jump of '
                     + BOX + '. What is the missing jump?'),
    'ctx_pages': ('في الكتاب {a} صفحة. قرأت سلمى {b} صفحة. كم صفحة بقيت؟',
                  'The book has {a} pages. Salma has read {b} pages. How many pages are left?'),
    'ctx_stickers': ('مع عمر {a} ملصقًا، ومع أخته {b} ملصقًا. بكم يزيد ما مع عمر؟',
                     'Omar has {a} stickers and his sister has {b}. How many more does Omar have?'),
    'ctx_beads': ('تحتاج سلمى {a} خرزة للعقد، ومعها {b} خرزة. كم خرزة تنقصها؟',
                  'Salma needs {a} beads for the necklace and has {b}. How many more beads does she need?'),
    'ctx_seats': ('في القاعة {a} مقعدًا. جلس الأطفال على {b} مقعدًا. كم مقعدًا فارغًا؟',
                  'The hall has {a} seats. Children are sitting on {b} of them. How many seats are empty?'),
    'compare': ('حلّان للمسألة {eq}. الحل أ بالقفز للخلف: {sa_ar}. الحل ب بالإكمال: {sb_ar}. '
                'أي الحلين قفزاته أقل؟',
                'Two solutions for {eq}. Solution A jumps back: {sa_en}. Solution B counts up: {sb_en}. '
                'Which solution uses fewer jumps?'),
}
CARDS = {
    'compare': {'A': ('الحل أ', 'Solution A'), 'B': ('الحل ب', 'Solution B'), 'same': ('متساويان', 'The same')},
    'how': {'back': ('قفزت للخلف', 'I jumped back'), 'up': ('أكملت من العدد الأصغر',
                                                           'I counted up from the smaller number'),
            'other': ('بطريقة أخرى', 'Another way')},
}
UI = {
    'unit.1-4': ('أصدقاء العشرة', 'Friends of ten'),
    'unit.3-5': ('الطرح برقمين', 'Two-digit subtraction'),
    'skill.1-4-1': ('أزواج العشرة على الإطار', 'Pairs that make ten on the frame'),
    'skill.1-4-2': ('أزواج العشرة بصيغها الثلاث', 'Pairs that make ten in three forms'),
    'skill.3-5-1': ('الطرح بالقفز للخلف', 'Subtracting by jumping back'),
    'skill.3-5-2': ('الطرح بالإكمال', 'Subtracting by counting up'),
    'skill.3-5-3': ('مسائل طرح مختلطة بأي من الطريقتين', 'Mixed subtraction with either method'),
    'lesson.watch': ('شاهِد', 'Watch'),
    'lesson.model': ('افعل بالنموذج', 'Do it with the model'),
    'lesson.fade': ('النموذج يخفت', 'The model fades'),
    'lesson.nomodel': ('بلا نموذج', 'No model'),
    'opening.try': ('جرّب أولًا', 'Try first'),
    'button.tool': ('أرني الأداة', 'Show me the tool'),
    'button.help': ('أحتاج مساعدة', 'I need help'),
    'button.listen': ('اسمع السؤال', 'Hear the question'),
    'how.title': ('كيف حسبتها؟', 'How did you work it out?'),
    'check.intro': ('عشرة أسئلة بلا مساعدة. خذ وقتك.', 'Ten questions without help. Take your time.'),
    'gate.intro': ('أسئلة قصيرة لنعرف من أين نبدأ.', 'A few questions to find where to start.'),
}
# الوصف المحايد للإجابة الخاطئة (4.3): يذكر الفرق أو الشكل الظاهر ولا يسمّي سببًا. ومعه السؤال التشخيصي.
DESCRIBE = {
    'given_back': ('العدد المعطى نفسه', 'The given number itself',
                   'على الإطار: {n} وكم تصير 10؟', 'On the frame: {n} and how many make 10?'),
    'less_by': ('أقل من الصحيح بـ {k}', 'Less than the correct answer by {k}', '', ''),
    'more_by': ('أكثر من الصحيح بـ {k}', 'More than the correct answer by {k}', '', ''),
    'digitwise': ('كل خانة فرق بين رقميها', 'Each digit is the difference of the two digits in its place',
                  'أيهما أكبر: {eq} أم {eq_tens}؟', 'Which is larger: {eq} or {eq_tens}?'),
    'reversed': ('خانتان مقلوبتان', 'Two digits reversed',
                 'اقرأ العدد، ثم انسخه، ثم مثّله بعشرات وآحاد',
                 'Read the number, copy it, then show it with tens and ones'),
    'sum': ('مجموع العددين', 'The sum of the two numbers',
            'الناتج أكبر من {a} أم أصغر منه؟', 'Is the answer more than {a} or less than it?'),
    'other': ('إجابة أخرى', 'Another answer', '', ''),
}


# ---------------------------------------------------------------- طرق الحل
def back_steps(a, b):
    """القفز للخلف: العشرات، ثم الآحاد، وتُقسم الآحاد عند عبور العشرة."""
    out, cur = [], a
    t, u = b - b % 10, b % 10
    if t:
        out.append(t)
        cur -= t
    if u:
        o = cur % 10
        if o == 0 or o >= u:
            out.append(u)
        else:
            out += [o, u - o]
    return out


def up_steps(a, b):
    """الإكمال: إلى العشرة التالية، ثم إلى المطروح منه."""
    if a // 10 == b // 10:
        return [a - b]
    if b % 10 == 0:                                         # من عشرة كاملة: إلى عشرة المطروح منه، ثم آحاده
        t = a - a % 10
        return [t - b] + ([a % 10] if a % 10 else [])
    t = b + 10 - b % 10
    return [t - b] + ([a - t] if a > t else [])


def stations(a, steps):
    out, cur = [], a
    for s in steps:
        cur -= s
        out.append(cur)
    return out


# ---------------------------------------------------------------- شروط الخانات (10.2)
def base(a, b):
    return 21 <= a <= 99 and 11 <= b < a and b % 10 != 0


def cross(a, b):
    return a % 10 < b % 10


def td(a, b):
    return a // 10 - b // 10


SLOTS = {
    '3-5-1': [
        (2, 'بلا عبور، والناتج 10 فأكثر', lambda a, b: base(a, b) and not cross(a, b) and a - b >= 10),
        (3, 'بعبور، عشرات المطروح 1 أو 2، آحاد المطروح منه ليست صفرًا، والناتج 10 فأكثر',
         lambda a, b: base(a, b) and cross(a, b) and b // 10 in (1, 2) and a % 10 != 0 and a - b >= 10),
        (3, 'بعبور، عشرات المطروح 3 فأكثر، آحاد المطروح منه ليست صفرًا، والناتج 10 فأكثر',
         lambda a, b: base(a, b) and cross(a, b) and b // 10 >= 3 and a % 10 != 0 and a - b >= 10),
        (1, 'آحاد المطروح منه صفر، والناتج 10 فأكثر', lambda a, b: base(a, b) and a % 10 == 0 and a - b >= 10),
        (1, 'بعبور، والناتج من 1 إلى 9', lambda a, b: base(a, b) and cross(a, b) and 1 <= a - b <= 9),
    ],
    '3-5-2': [
        (3, 'فرق العشرات 1، وآحاد المطروح منه ليست صفرًا', lambda a, b: base(a, b) and td(a, b) == 1 and a % 10 != 0),
        (2, 'فرق العشرات 2، آحاد المطروح منه ليست صفرًا، والناتج 30 فأقل',
         lambda a, b: base(a, b) and td(a, b) == 2 and a % 10 != 0 and a - b <= 30),
        (2, 'فرق العشرات 3، آحاد المطروح منه ليست صفرًا، والناتج 30 فأقل',
         lambda a, b: base(a, b) and td(a, b) == 3 and a % 10 != 0 and a - b <= 30),
        (2, 'آحاد المطروح منه صفر، وفرق العشرات من 1 إلى 3',
         lambda a, b: base(a, b) and a % 10 == 0 and 1 <= td(a, b) <= 3),
        (1, 'الناتج أكبر من 30، وآحاد المطروح منه ليست صفرًا', lambda a, b: base(a, b) and a - b > 30 and a % 10 != 0),
    ],
    '3-5-3': [
        (3, 'الناتج من 1 إلى 9', lambda a, b: base(a, b) and 1 <= a - b <= 9),
        (3, 'بلا عبور، عشرات المطروح 1، والناتج 10 فأكثر',
         lambda a, b: base(a, b) and not cross(a, b) and b // 10 == 1 and a - b >= 10),
        (4, 'بعبور، عشرات المطروح 2 فأكثر، والناتج 10 فأكثر',
         lambda a, b: base(a, b) and cross(a, b) and b // 10 >= 2 and a - b >= 10),
    ],
}
SLOTS_SMALL = {
    '1-4-1': [
        (3, 'عدد الأقراص من 6 إلى 9، بثلاث قيم مختلفة، والمطلوب عدد الخانات الفارغة', 'frame_empty', (6, 7, 8, 9)),
        (3, 'عدد الأقراص من 1 إلى 4، بثلاث قيم مختلفة، والمطلوب عدد الخانات الفارغة', 'frame_empty', (1, 2, 3, 4)),
        (1, 'خمسة أقراص', 'frame_empty', (5,)),
        (1, 'لا أقراص، أو عشرة أقراص', 'frame_empty', (0, 10)),
        (1, 'يُعطى عدد الخانات الفارغة من 1 إلى 4، ويُطلب عدد الأقراص', 'frame_counters', (1, 2, 3, 4)),
        (1, 'يُعطى عدد الخانات الفارغة من 6 إلى 9، ويُطلب عدد الأقراص', 'frame_counters', (6, 7, 8, 9)),
    ],
    '1-4-2': [(1, 'المجهول %s، والعدد من %d إلى %d' % (nm, lo, lo + 2), pf, (lo, lo + 1, lo + 2))
              for pf, nm in (('missing_second', 'ثانيًا'), ('missing_first', 'أولًا'), ('subtract', 'بصيغة الطرح'))
              for lo in (1, 4, 7)] + [(1, 'العدد 0 أو 10، والمجهول ثانيًا', 'missing_second', (0, 10))],
}
EVIDENCE = {'1-4-1': ['ف1', 'ف3'], '1-4-2': ['ف2', 'ف3', 'ف4'], '3-5-1': ['ف1', 'ف2', 'ف3'],
            '3-5-2': ['ف1', 'ف2', 'ف3', 'ف4'], '3-5-3': ['ف3']}
PERF = {  # الأداء المطلوب لكل نوع دليل في كل مهارة
    '1-4-1': {'ف1': 'frame_empty', 'ف3': 'make_ten'},
    '1-4-2': {'ف2': 'step_pair', 'ف3': 'missing', 'ف4': 'context10'},
    '3-5-1': {'ف1': 'line_back', 'ف2': 'station_back', 'ف3': 'solve'},
    '3-5-2': {'ف1': 'line_up', 'ف2': 'jump_missing', 'ف3': 'solve', 'ف4': 'context_sub'},
    '3-5-3': {'ف3': 'solve'},
}
RESOURCE = {'frame_empty': 'إطار العشرة وعليه الأقراص', 'frame_counters': 'إطار العشرة والأقراص مغطاة',
            'make_ten': 'بلا نموذج', 'missing_second': 'بلا نموذج', 'missing_first': 'بلا نموذج',
            'subtract': 'بلا نموذج', 'step_pair': 'هيكل الإطار الشفاف', 'context10': 'صورة الموقف، والنص منطوق',
            'line_back': 'خط الأعداد الفارغ والقفزات مرسومة', 'station_back': 'هيكل خط الأعداد الشفاف',
            'solve': 'بلا نموذج', 'line_up': 'خط الأعداد: المحطات فوقه والقفزات تحته',
            'jump_missing': 'هيكل خط الأعداد الشفاف', 'context_sub': 'صورة الموقف، والنص منطوق',
            'compare': 'حلّان مرسومان على خطين'}
CTX10 = ['ctx_eggs', 'ctx_bus', 'ctx_balloons', 'ctx_steps']
CTXSUB = ['ctx_pages', 'ctx_stickers', 'ctx_beads', 'ctx_seats']


# ---------------------------------------------------------------- بناء البند
def render(perf, n):
    """يعيد (النص العربي، النص الإنجليزي، الجواب). الجواب هنا من التوليد؛ التحقق يعيد حسابه مستقلًا."""
    if perf in ('frame_empty', 'make_ten'):
        k = dict(n=n['n'])
        return T[perf][0].format(**k), T[perf][1].format(**k), 10 - n['n']
    if perf == 'frame_counters':
        return T[perf][0].format(e=n['e']), T[perf][1].format(e=n['e']), 10 - n['e']
    if perf in ('missing_second', 'missing_first', 'subtract'):
        s = {'missing_second': '%d + %s = 10' % (n['n'], BOX), 'missing_first': '%s + %d = 10' % (BOX, n['n']),
             'subtract': '10 %s %d = %s' % (MINUS, n['n'], BOX)}[perf]
        return T['missing'][0].format(eq=eq(s)), T['missing'][1].format(eq=eq(s)), 10 - n['n']
    if perf == 'step_pair':
        k = dict(eq1=eq('10 %s %d = %s' % (MINUS, n['n'], BOX)), eq2=eq('%d + %s = 10' % (n['n'], BOX)))
        return T[perf][0].format(**k), T[perf][1].format(**k), 10 - n['n']
    if perf == 'context10':
        return T[n['ctx']][0].format(n=n['n']), T[n['ctx']][1].format(n=n['n']), 10 - n['n']
    a, b = n['a'], n['b']
    e = eq('%d %s %d' % (a, MINUS, b))
    if perf == 'solve':
        s = eq('%d %s %d = %s' % (a, MINUS, b, BOX))
        return T[perf][0].format(eq=s), T[perf][1].format(eq=s), a - b
    if perf == 'context_sub':
        return T[n['ctx']][0].format(a=a, b=b), T[n['ctx']][1].format(a=a, b=b), a - b
    if perf == 'line_back':
        st = back_steps(a, b)
        k = dict(a=a, jumps_ar=' ثم '.join(map(str, st)), jumps_en=', then '.join(map(str, st)))
        return T[perf][0].format(**k), T[perf][1].format(**k), a - b
    if perf == 'station_back':
        st = back_steps(a, b)
        ss = stations(a, st)
        hide = ss[-2]                                       # المحطة قبل الأخيرة هي الناقصة
        parts, cur = [], a
        for i, (j, x) in enumerate(zip(st, ss)):
            left = BOX if cur == hide and i == len(st) - 1 else str(cur)
            right = BOX if x == hide else str(x)
            parts.append(eq('%s %s %d = %s' % (left, MINUS, j, right)))
            cur = x
        return (T[perf][0].format(chain_ar=' ثم '.join(parts)), T[perf][1].format(chain_en=', then '.join(parts)),
                hide)
    t = b + 10 - b % 10
    j1, j2 = t - b, a - t
    k = dict(a=a, b=b, t=t, j1=j1, j2=j2, eq=e)
    if perf == 'line_up':
        return T[perf][0].format(**k), T[perf][1].format(**k), a - b
    if perf == 'jump_missing':
        return T[perf][0].format(**k), T[perf][1].format(**k), j2
    if perf == 'compare':
        sa, sb = back_steps(a, b), up_steps(a, b)
        k = dict(eq=e, sa_ar=' ثم '.join(map(str, sa)), sa_en=', then '.join(map(str, sa)),
                 sb_ar=' ثم '.join(map(str, sb)), sb_en=', then '.join(map(str, sb)))
        ans = 'A' if len(sa) < len(sb) else 'B' if len(sb) < len(sa) else 'same'
        return T[perf][0].format(**k), T[perf][1].format(**k), ans
    raise ValueError(perf)


LINES = ('line_back', 'station_back', 'line_up', 'jump_missing')


def line_model(perf, n):
    """ما يرسمه التطبيق لبند على خط الأعداد: القفزات والمحطات التي يذكرها نص البند نفسه، وما يُخفى منها. الرسم من هذا
    الحقل، فلا يعيد التطبيق حساب طريقة الحل. back: يبدأ من المطروح منه ويقفز للخلف. up: يبدأ من المطروح ويكمل إلى
    المطروح منه. hide: ما يُسأل عنه، محطة برقمها في stations أو قفزة برقمها في jumps."""
    a, b = n['a'], n['b']
    if perf in ('line_back', 'station_back'):
        st = back_steps(a, b)
        ss = stations(a, st)
        hide = ['station', len(ss) - 1] if perf == 'line_back' else ['station', len(ss) - 2]
        return dict(line='back', start=a, jumps=st, stations=ss, hide=hide)
    t = b + 10 - b % 10
    return dict(line='up', start=b, jumps=[t - b, a - t], stations=[t, a],
                hide=['total'] if perf == 'line_up' else ['jump', 1])


def compare_model(n):
    """رسم بند المقارنة: الحلان اللذان يذكرهما نصه، كل على خط. أ يقفز للخلف من المطروح منه، و ب يكمل من المطروح.
    لا شيء مخفي: السؤال عن عدد القفزات لا عن عدد."""
    a, b = n['a'], n['b']
    sa, sb = back_steps(a, b), up_steps(a, b)
    up, cur = [], b
    for j in sb:
        cur += j
        up.append(cur)
    return dict(pair=[dict(line='back', start=a, jumps=sa, stations=stations(a, sa), hide=None),
                      dict(line='up', start=b, jumps=sb, stations=up, hide=None)])


def wrong_answers(perf, n, ans):
    """إجابات خاطئة متوقعة ووصفها المحايد. ما سواها يوصف بالفرق عن الصحيح."""
    out = {}
    if 'a' in n and isinstance(ans, int) and perf in ('solve', 'context_sub', 'line_back', 'line_up'):
        a, b = n['a'], n['b']
        d = abs(a // 10 - b // 10) * 10 + abs(a % 10 - b % 10)
        if d != ans:
            out[d] = 'digitwise'
        r = int(str(ans)[::-1]) if ans >= 10 and ans % 10 else None
        if r and r != ans and r not in out:
            out[r] = 'reversed'
        if a + b not in out:
            out[a + b] = 'sum'
    elif 'n' in n and n['n'] != ans:
        out[n['n']] = 'given_back'
    return out


class Bank:
    def __init__(self):
        self.items = []
        self.count = Counter()

    def add(self, skill, group, role, ev, perf, slot=None, alt_of=None, note=None, **n):
        self.count[(skill, group)] += 1
        ar, en, ans = render(perf, n)
        it = dict(id='%s/%s/%02d' % (skill, group, self.count[(skill, group)]), skill=skill, group=group,
                  role=role, evidence=ev, performance=perf, numbers=n, resource=RESOURCE[perf],
                  answer_type='ج8' if perf == 'compare' else 'ج1', answer=ans, text_ar=ar, text_en=en,
                  audio_ar=ar, audio_en=en, wrong=wrong_answers(perf, n, ans), slot=slot, alt_of=alt_of,
                  graded=True)
        if perf == 'compare':
            it['cards'] = sorted(CARDS['compare'])
        if note:
            it['note'] = note
        self.items.append(it)
        return it


# ---------------------------------------------------------------- توليد وحدة 3-5
def zero_step(it):
    """هل في تسلسل الحل المعروض قفزة قيمتها صفر؟"""
    n = it['numbers']
    return it['performance'] in ('line_up', 'jump_missing') and n['a'] == n['b'] + 10 - n['b'] % 10


def build_big(bank, rng, used):
    pool = [(a, b) for a in range(21, 100) for b in range(11, a) if b % 10]
    rng.shuffle(pool)

    def take(pred, extra=lambda a, b: True):
        for ab in pool:
            if ab not in used and pred(*ab) and extra(*ab):
                used.add(ab)
                return ab
        raise RuntimeError('نفد المجال')

    def maker(skill):
        fams = [f for _c, _d, f in SLOTS[skill]]
        turn = [0]

        def nxt(extra=lambda a, b: True):
            turn[0] += 1
            return take(fams[turn[0] % len(fams)], extra)

        def modelled(a, b):                                 # بنود النموذج والخطوة تحتاج محطتين على الأقل
            return len(back_steps(a, b)) >= 2 if skill == '3-5-1' else td(a, b) >= 1

        def put(group, role, ev, perf, extra=lambda a, b: True, **kw):
            need = modelled if perf not in ('solve', 'context_sub', 'compare') else (lambda a, b: True)
            a, b = nxt(lambda a, b: need(a, b) and extra(a, b))
            n = dict(a=a, b=b)
            if perf == 'context_sub':
                n['ctx'] = CTXSUB[bank.count[(skill, group)] % len(CTXSUB)]
            return bank.add(skill, group, role, ev, perf, **dict(kw, **n))
        return put

    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        P, types = PERF[skill], EVIDENCE[skill]
        main = P.get('ف1', 'solve')
        step = P.get('ف2', 'solve')

        put('lesson', 'lesson.watch', None, main)
        for _ in range(2):
            put('lesson', 'lesson.model', None, main)
        for _ in range(2):
            put('lesson', 'lesson.fade', None, step)
        for _ in range(2):
            put('lesson', 'lesson.nomodel', None, 'solve')
        put('opening', 'opening.try', 'ف3', 'solve')
        put('opening', 'opening.try', types[0], P[types[0]])
        for _ in range(3):
            put('opening', 'opening.guided', types[0], P[types[0]])
        for _ in range(6):
            put('practice', 'practice', None, 'solve')
        for t in types:                                     # بندان لكل نوع، وبندان بعد الدرس القصير
            for i in range(4):
                put('evidence', 'evidence' if i < 2 else 'evidence.reserve', t, P[t])
        calc = [t for t in types if t in ('ف3', 'ف4')]
        und = [t for t in types if t not in calc]
        plan = [t for t in calc for _ in range(5 if t == 'ف3' else 2)] + [t for t in und for _ in range(2)]
        while len(plan) < 6:
            plan.insert(0, 'ف3')
        for g in ('gate', 'regate'):                        # البوابة، ثم إعادتها الوحيدة ببنود جديدة (6.1)
            for t in plan:                                  # بنود الحساب أولًا
                put(g, 'gate', t, P[t])
            for t in types:
                for _ in range(2):
                    put(g, 'gate.compensation', t, P[t])
            for t in types:                                 # بديلان لكل نوع: يُستبدل بهما البند المنقطع
                for _ in range(2):
                    put(g, 'gate.alternate', t, P[t])
        for t in ([und[0]] if und else ['ف3']) + ['ف3', 'ف3']:
            put('short', 'short_check', t, P[t])
        for attempt in ('A', 'B'):
            k = 0
            for c, _d, pred in SLOTS[skill]:
                for _ in range(c):
                    k += 1
                    a, b = take(pred)
                    main_it = bank.add(skill, 'check' + attempt, 'check', 'ف3', 'solve', slot=k, a=a, b=b)
                    a, b = take(pred)
                    bank.add(skill, 'check' + attempt, 'check.alternate', 'ف3', 'solve', slot=k,
                             alt_of=main_it['id'], a=a, b=b)
        for rnd in (1, 2, 3):                               # ثلاث جولات من 5 بنود بعد 7 و21 و60 يومًا (3.7)
            for _ in range(5):
                put('deferred', 'deferred_check', 'ف3', 'solve', slot=rnd)
        if skill == '3-5-3':
            tens = [(a, b) for a in range(21, 100) for b in range(20, a - 9, 10) if a % 10]
            rng.shuffle(tens)                               # مطروح من العشرات الكاملة: القفز للخلف قفزة واحدة

            def pick(w):
                if w == 'A':
                    return tens.pop()
                return take(base, lambda a, b: render('compare', dict(a=a, b=b))[2] == w)

            want = ['B', 'A', 'same', 'B']
            for w in want:
                a, b = pick(w)
                it = bank.add(skill, 'compare', 'descriptive_check', 'ف5',
                              'compare', a=a, b=b, note='وصفي: يُعرض في اللوحة ولا يُشترط لتقدم')
                it['graded'] = False
            for w in ('B', 'A'):
                a, b = pick(w)
                it = bank.add(skill, 'lesson', 'lesson.compare', None, 'compare', a=a, b=b,
                              note='نشاط في الدرس. تفضيل الطفل يُسجَّل ولا يُصحَّح')
                it['graded'] = False
    # بعد المرحلة الأولى كلها، فلا تتغير أعداد ما سبق: جولة ثانية لدليل الفهم (3.5) ومحاولة ثالثة للفحص (3.6)
    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        P, types = PERF[skill], EVIDENCE[skill]
        for t in types:
            for i in range(4):
                put('evidence', 'evidence' if i < 2 else 'evidence.reserve', t, P[t])['round'] = 2
        k = 0
        for c, _d, pred in SLOTS[skill]:
            for _ in range(c):
                k += 1
                a, b = take(pred)
                main_it = bank.add(skill, 'checkC', 'check', 'ف3', 'solve', slot=k, a=a, b=b)
                a, b = take(pred)
                bank.add(skill, 'checkC', 'check.alternate', 'ف3', 'solve', slot=k, alt_of=main_it['id'], a=a, b=b)
    # بقرار الأب (6.2، ك4): بندا «جرّب أولًا» لكل نوع، يُعرضان حين يؤخذ النوعان من أخطاء بوابة المهارة
    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        for t in EVIDENCE[skill]:
            for _ in range(2):
                put('tryfirst', 'opening.try', t, PERF[skill][t])
    # بديل لبند دليل فهم استُبعد بعد أن أُجيب عنه أو طُلب فيه دعم (R18-01): واحد لكل نوع في كل جولة، بحقيقة جديدة.
    # بعد كل ما سبق، فلا تتغير أعداده. والقفزة المطلوبة فيه ليست صفرًا
    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        for rnd in (1, 2):
            for t in EVIDENCE[skill]:
                perf = PERF[skill][t]
                for _ in SLOTS[skill]:                      # عائلة أعداد لا تحقق الشرط تُترك إلى التالية
                    try:
                        it = put('evidence', 'evidence.alternate', t, perf,
                                 extra=(lambda a, b: a % 10 != 0) if perf == 'jump_missing' else (lambda a, b: True))
                        break
                    except RuntimeError:
                        continue
                else:
                    raise RuntimeError('لا بديل لدليل الفهم: %s %s' % (skill, t))
                it['round'] = rnd
    # بنود يُعرض فيها الإكمال بقفزتين وثانيتهما صفر (من 26 إلى 30 ثم «من 30 إلى 30»): الصفر صحيح حسابيًا، لكن البند لا
    # يقيس الإكمال بقفزتين. تُستبدل أعدادها بأول زوج لم يُستعمل من عائلة خانتها نفسها وقفزته الثانية ليست صفرًا.
    # بعد كل ما سبق، فلا تتغير أعداد بند آخر
    for it in bank.items:
        if it['skill'] in SLOTS and it['performance'] in ('line_up', 'jump_missing') and zero_step(it):
            a, b = it['numbers']['a'], it['numbers']['b']
            fam = next(f for _c, _d, f in SLOTS[it['skill']] if f(a, b))
            a, b = take(fam, lambda a, b: len(up_steps(a, b)) == 2)
            it['numbers'].update(a=a, b=b)
            rerender(it)
            it['note'] = 'استُبدلت أعداده: كانت قفزته الثانية صفرًا'
    # بدائل جولات الفحص المؤجل (ت3 في مراجعة 04e0168): طلب المساعدة ينهي الجولة بلا حكم، والجولة اللاحقة ببنود بديلة.
    # مجموعة بديلة واحدة (set=1) لكل جولة، بأزواج أعداد لم تُستعمل. بعد كل ما سبق، فلا تتغير أعداد بند آخر
    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        for rnd in (1, 2, 3):
            for _ in range(5):
                put('deferred', 'deferred_check.alternate', 'ف3', 'solve', slot=rnd)['set'] = 1
    # تدريب إضافي لمن أراد أن يستمر بعد جلسة يومه (قرار الأب، 19 نوفمبر): مجموعتان من 6 بعد بنود التدريب الستة، بأزواج
    # أعداد لم تُستعمل، وبصيغ المهارة كلها لا بالحساب المجرد وحده. بعد كل ما سبق، فلا تتغير أعداد بند آخر
    for skill in ('3-5-1', '3-5-2', '3-5-3'):
        put = maker(skill)
        forms = ['solve'] + [PERF[skill][t] for t in EVIDENCE[skill] if PERF[skill][t] != 'solve']
        for k in range(MORE_PRACTICE):
            put('more', 'practice.more', None, forms[k % len(forms)] if k % 2 else 'solve')


# ---------------------------------------------------------------- توليد وحدة 1-4
def check_plan_142():
    """أعداد الخانات التسع الأولى في محاولات فحص 1-4-2 الثلاث. كل خانة من ثلاثيتها (1 إلى 3، 4 إلى 6، 7 إلى 9)، وكل
    عدد من 1 إلى 9 مرة واحدة في المحاولة، ولا خانتان متتاليتان بعددين متتامين إلى 10 (3.5: الحقيقة نفسها لا تُعرض
    في بندين متتاليين)، وعدد كل خانة يتبدل بين المحاولات الثلاث. المحاولة الأولى كما كانت، والباقيتان أول ما يحقق
    الشروط بالترتيب المعجمي."""
    triples = [(1, 2, 3), (4, 5, 6), (7, 8, 9)]

    def fill(prefix, banned):
        k = len(prefix)
        if k == 9:
            yield list(prefix)
            return
        for v in triples[k % 3]:
            if v in prefix or v in banned[k] or (prefix and prefix[-1] + v == 10):
                continue
            yield from fill(prefix + [v], banned)
    plans = [[1, 4, 7, 2, 5, 8, 3, 6, 9]]
    assert plans[0] in list(fill([], [set()] * 9))
    for _ in range(2):
        plans.append(next(fill([], [{p[k] for p in plans} for k in range(9)])))
    return plans


def rerender(it):
    """يعيد كتابة نص البند وجوابه وإجاباته الخاطئة المتوقعة بعد تغيير أعداده."""
    ar, en, ans = render(it['performance'], it['numbers'])
    it.update(answer=ans, text_ar=ar, text_en=en, audio_ar=ar, audio_en=en,
              wrong=wrong_answers(it['performance'], it['numbers'], ans))


def small_fact(it):
    n = it['numbers']
    v = n.get('n', n.get('e'))
    return frozenset((v, 10 - v))


def respace_small(items):
    """3.5: لا تُعرض الحقيقة نفسها في بندين متتاليين. يأخذ من content_sequence كل زوج بنود يمكن أن يراه الطفل متتاليين
    أثناء التشغيل (بكل الفروع والبدائل والاستئناف)، ويعيد اختيار أعداد بنود الوحدة 1-4 خارج فحص الاستقلال (خاناته
    تُضبط عند توليدها) حتى لا يخالف زوج. بحث بالتراجع: البند الأكثر قيودًا أولًا، وعدده الحالي أول ما يُجرَّب، فلا
    يتغير بند بلا حاجة، ثم أقل الأعداد استعمالًا في مجموعته وأدائه. وبديل دليل الفهم تبقى حقيقته خارج بنود نوعه في
    جولته. يعيد عدد البنود التي تغيّرت."""
    from content_sequence import collect
    pairs, by_id, _n = collect(items, EVIDENCE)
    near = defaultdict(set)
    for a, b, how, _label in pairs:
        if 'more' in (by_id[a]['group'], by_id[b]['group']):   # التدريب الإضافي يُكتب بعد هذا البحث وخارجه (more_small)
            continue
        if a != b and how != 'interrupted' and by_id[a]['skill'] in SLOTS_SMALL:
            near[a].add(b)
            near[b].add(a)
    changed = 0
    for skill in SLOTS_SMALL:
        for it in items:                                    # بديل دليل الفهم: حقيقته خارج بنود نوعه في جولته
            if it['skill'] == skill and it['role'] == 'evidence.alternate':
                for o in items:
                    if (o['skill'] == skill and o['group'] == 'evidence' and o is not it
                            and o['evidence'] == it['evidence'] and o.get('round', 1) == it.get('round', 1)):
                        near[it['id']].add(o['id'])
                        near[o['id']].add(it['id'])
        # تأخير بند التقييم (item_layer.Activity._defer) يحتاج موضعًا لا يجاور فيه البند حقيقته. البند الثالث من
        # آخر مرحلته لا موضع له إلا آخرها، فلا يحمل حقيقة آخرها: بهذا يبقى بلا موضع آخرُ كل مرحلة وحده
        stages = [[i for i in items if i['skill'] == skill and i['group'] == g and i['role'] == r]
                  for g, r in (('gate', 'gate'), ('regate', 'gate'), ('short', 'short_check'))]
        stages += [[i for i in items if i['skill'] == skill and i['role'] == role and i['slot'] == rnd]
                   for role in ('deferred_check', 'deferred_check.alternate') for rnd in (1, 2, 3)]
        for lst in stages:
            if len(lst) >= 3:
                near[lst[-3]['id']].add(lst[-1]['id'])
                near[lst[-1]['id']].add(lst[-3]['id'])
        todo = [i for i in items if i['skill'] == skill and not i['group'].startswith('check') and i['group'] != 'more'
                and 1 <= i['numbers'].get('n', i['numbers'].get('e')) <= 9]
        ids = {i['id'] for i in todo}
        order = sorted(todo, key=lambda i: -len(near[i['id']]))      # الترتيب ثابت: sorted مستقر على ترتيب الملف
        fixed = {i['id']: small_fact(i) for i in items if i['skill'] == skill and i['id'] not in ids}
        value, used = {}, Counter()

        def fact_of(x):
            return fixed[x] if x in fixed else frozenset((value[x], 10 - value[x])) if x in value else None

        steps = [0]

        def solve(k):
            steps[0] += 1
            if steps[0] > 500000:                           # لا يُترك البحث يدور بلا نهاية: الإخفاق يُعلن
                raise RuntimeError('تعذّر إيجاد أعداد تحقق التتابع في %s بعد %d خطوة' % (skill, steps[0]))
            if k == len(order):
                return True
            it = order[k]
            key = 'e' if 'e' in it['numbers'] else 'n'
            cur, grp = it['numbers'][key], (it['group'], it['performance'])
            taken = {fact_of(x) for x in near[it['id']]} - {None}
            cands = sorted((v for v in range(1, 10) if frozenset((v, 10 - v)) not in taken),
                           key=lambda v: (v != cur, used[(grp, v)], used[(it['group'], v)], (v - cur) % 9))
            for v in cands:
                value[it['id']] = v
                used[(grp, v)] += 1
                used[(it['group'], v)] += 1
                if solve(k + 1):
                    return True
                used[(grp, v)] -= 1
                used[(it['group'], v)] -= 1
                del value[it['id']]
            return False

        sys.setrecursionlimit(10000)
        if not solve(0):
            raise RuntimeError('لا أعداد تحقق التتابع في %s' % skill)
        for it in todo:
            key = 'e' if 'e' in it['numbers'] else 'n'
            if it['numbers'][key] != value[it['id']]:
                it['numbers'][key] = value[it['id']]
                rerender(it)
                changed += 1
    return changed


def build_small(bank, rng):
    plan_142 = check_plan_142()
    for skill in ('1-4-1', '1-4-2'):
        P, types = PERF[skill], EVIDENCE[skill]
        order = [6, 3, 8, 1, 5, 9, 2, 7, 4]
        turn = defaultdict(int)

        def put(group, role, ev, perf, force=None, **kw):
            key = (group, perf)                             # كل أداء يدور على الأعداد مستقلًا داخل مجموعته
            turn[key] += 1
            n = dict(n=order[(turn[key] + 2 * len(group)) % 9] if force is None else force)
            if perf == 'missing':
                perf = ('missing_second', 'missing_first', 'subtract')[turn[key] % 3]
            if perf == 'context10':
                n['ctx'] = CTX10[turn[key] % len(CTX10)]
            return bank.add(skill, group, role, ev, perf, **dict(kw, **n))

        first = P[types[0]]
        put('lesson', 'lesson.watch', None, first)
        for _ in range(2):
            put('lesson', 'lesson.model', None, first)
        for _ in range(2):
            put('lesson', 'lesson.fade', None, 'step_pair' if skill == '1-4-2' else 'frame_empty')
        for _ in range(2):
            put('lesson', 'lesson.nomodel', None, P['ف3'])
        put('opening', 'opening.try', 'ف3', P['ف3'])
        put('opening', 'opening.try', types[0], first)
        for _ in range(3):
            put('opening', 'opening.guided', types[0], first)
        for _ in range(6):
            put('practice', 'practice', None, P['ف3'])
        for t in types:
            for i in range(4):
                put('evidence', 'evidence' if i < 2 else 'evidence.reserve', t, P[t])
        calc = [t for t in types if t in ('ف3', 'ف4')]
        und = [t for t in types if t not in calc]
        for g in ('gate', 'regate'):                        # البوابة، ثم إعادتها الوحيدة (6.1)
            for t in [t for t in calc for _ in range(5 if t == 'ف3' else 2)] + [t for t in und for _ in range(2)]:
                put(g, 'gate', t, P[t])
            for t in types:
                for _ in range(2):
                    put(g, 'gate.compensation', t, P[t])
            for t in types:
                for _ in range(2):
                    put(g, 'gate.alternate', t, P[t])
        for t in [und[0], 'ف3', 'ف3']:
            put('short', 'short_check', t, P[t])
        for ai, attempt in enumerate(('A', 'B', 'C')):
            k, taken, tail = 0, set(), []                   # tail: آخر ما قد يُعرض قبل هذه المجموعة، بندًا وبديلًا
            for c, _d, perf, values in SLOTS_SMALL[skill]:
                vals = list(values)
                if skill == '1-4-2' and len(vals) == 3:     # كل عدد مرة واحدة في المحاولة، وتتبدل بين المحاولات (3.5)
                    pick = [plan_142[ai][k]]
                elif len(vals) == 2 and c == 1 and set(vals) == {0, 10}:
                    pick = [vals[ai % 2]]                   # الحالة الأخرى في المحاولة التالية
                else:
                    r = ai % len(vals)
                    for shift in range(len(vals)):          # أول المجموعة لا يتمّ عشرةً مع آخر ما سبقها (3.5)
                        pick = (vals[r + shift:] + vals[:r + shift])[:c]
                        if all(pick[0] + t != 10 for t in tail):
                            break
                    else:
                        raise RuntimeError('لا ترتيب لخانات %s يحقق التتابع' % skill)
                spare = [v for v in values if v not in pick and v not in taken]
                for v in pick:
                    k += 1
                    taken.add(v) if skill == '1-4-2' else None
                    key = 'e' if perf == 'frame_counters' else 'n'
                    m = bank.add(skill, 'check' + attempt, 'check', 'ف3' if perf != 'frame_empty' else 'ف1',
                                 perf, slot=k, **{key: v})
                    if spare and skill == '1-4-1':
                        alt = spare[0] if c == 1 else spare[-1]
                        tail = [v, alt]
                        bank.add(skill, 'check' + attempt, 'check.alternate', m['evidence'], perf, slot=k,
                                 alt_of=m['id'], note='بديل مشترك لخانات مجموعته' if c > 1 else None, **{key: alt})
                    else:
                        tail = [v]
                        bank.add(skill, 'check' + attempt, 'check.alternate', m['evidence'], perf, slot=k,
                                 alt_of=m['id'], note='لا قيمة أخرى تحقق شرط الخانة: إعادة عرض الحقيقة نفسها بعد '
                                 'الانقطاع، بقرار الأب (3.6)', **{key: v})
        other = {'1-4-1': ('frame_empty', 'n', 10), '1-4-2': ('missing_second', 'n', 10)}[skill]
        bank.add(skill, 'deferred', 'deferred_check', 'ف3', other[0], slot=1,
                 note='الحالة التي لم ترد في المحاولة الأولى', **{other[1]: other[2]})
        for rnd in (1, 2, 3):                               # ثلاث جولات من 5 بنود (3.7)
            for _ in range(4 if rnd == 1 else 5):
                put('deferred', 'deferred_check', 'ف3', P['ف3'], slot=rnd)
        for t in types:                                     # جولة ثانية لدليل الفهم ببنود جديدة (3.5)
            for i in range(4):
                put('evidence', 'evidence' if i < 2 else 'evidence.reserve', t, P[t])['round'] = 2
        for t in types:                                     # بندا «جرّب أولًا» لكل نوع (6.2، ك4)
            for _ in range(2):
                put('tryfirst', 'opening.try', t, P[t])
        # بديل لبند دليل فهم استُبعد بعد أن أُجيب عنه أو طُلب فيه دعم (R18-01): واحد لكل نوع في كل جولة، بحقيقة لم ترد
        # في بنود نوعه الأربعة في تلك الجولة، فلا يعيد البند المستبعد بمعرّف آخر ولا يجاور الحقيقة نفسها (3.5).
        # بعد كل ما سبق، فلا تتغير أعداده
        for rnd in (1, 2):
            for t in types:
                group = [i for i in bank.items if i['skill'] == skill and i['group'] == 'evidence'
                         and i['evidence'] == t and i.get('round', 1) == rnd]
                taken = {frozenset((i['numbers']['n'], 10 - i['numbers']['n'])) for i in group}
                free = [n for n in order if frozenset((n, 10 - n)) not in taken]
                put('evidence', 'evidence.alternate', t, P[t], force=free[0])['round'] = rnd
        # بدائل جولات الفحص المؤجل (ت3): مجموعة بديلة واحدة (set=1) لكل جولة. حقائق هذه الوحدة خمس، فالبنود البديلة
        # بنود أخرى لا حقائق أخرى: لا تخلو الجولة البديلة من حقيقة وردت في الأصلية. بعد كل ما سبق
        for rnd in (1, 2, 3):
            for _ in range(5):
                put('deferred', 'deferred_check.alternate', 'ف3', P['ف3'], slot=rnd)['set'] = 1


def more_small(bank):
    """تدريب إضافي للوحدة 1-4، لمن أراد أن يستمر بعد جلسة يومه (قرار الأب، 19 نوفمبر): مجموعتان من 6 تُعرضان بعد بنود
    التدريب الستة. حقائق الوحدة خمس، فالتنويع في الصيغة لا في الحقيقة: صيغ المهارة كلها بالتناوب. ولا تتوالى الحقيقة
    نفسها في بندين، من آخر بنود التدريب إلى آخر الإضافي (3.5). يُستدعى بعد respace_small، وبنوده خارج بحثها، فلا يتغير
    بها عدد بند سابق."""
    order = [6, 3, 8, 1, 5, 9, 2, 7, 4]
    for skill in SLOTS_SMALL:
        forms = [PERF[skill][t] for t in EVIDENCE[skill]]
        prev = small_fact([i for i in bank.items if i['skill'] == skill and i['role'] == 'practice'][-1])
        k, missing, ctx = 0, 0, 0
        for j in range(MORE_PRACTICE):
            while frozenset((order[k % 9], 10 - order[k % 9])) == prev:
                k += 1
            perf, n = forms[j % len(forms)], dict(n=order[k % 9])
            if perf == 'missing':
                perf, missing = ('missing_second', 'missing_first', 'subtract')[missing % 3], missing + 1
            if perf == 'context10':
                n['ctx'], ctx = CTX10[ctx % len(CTX10)], ctx + 1
            it = bank.add(skill, 'more', 'practice.more', None, perf, **n)
            prev, k = small_fact(it), k + 1


# ---------------------------------------------------------------- التحقق المستقل
def truth(it):
    """يعيد حساب الجواب من أعداد البند ونوع أدائه، بلا استعمال دوال العرض."""
    n, p = it['numbers'], it['performance']
    if p == 'frame_counters':
        return 10 - n['e']
    if 'n' in n:
        return 10 - n['n']
    a, b = n['a'], n['b']
    if p == 'jump_missing':
        return a - ((b // 10 + 1) * 10)
    if p == 'station_back':
        tens, ones = (b // 10) * 10, b % 10
        cur = a - tens
        if a % 10 < ones and a % 10 != 0:
            return cur - a % 10                             # المحطة عند العشرة
        return cur                                          # المحطة بعد قفزة العشرات
    if p == 'compare':
        back = 1 + (0 if b % 10 == 0 else 1 if (a % 10 == 0 or a % 10 >= b % 10) else 2)
        if a // 10 == b // 10:
            up = 1
        elif b % 10 == 0:
            up = 1 + (1 if a % 10 else 0)
        else:
            up = 2 if a > (b // 10 + 1) * 10 else 1
        return 'A' if back < up else 'B' if up < back else 'same'
    return a - b


GATE_LEN = {'1-4-1': 7, '1-4-2': 9, '3-5-1': 9, '3-5-2': 11, '3-5-3': 6}
ARABIC_DIGITS = set('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹')


def validate(items):
    bad = Counter()
    by = defaultdict(list)
    for it in items:
        by[(it['skill'], it['group'])].append(it)
        bad['جواب لا يطابق إعادة الحساب'] += int(truth(it) != it['answer'])
        for txt in (it['text_ar'], it['text_en']):
            bad['نص ناقص'] += int(not txt.strip())
            bad['عزل اتجاه غير متوازن'] += int(txt.count(LRI) != txt.count(PDI))
            bad['أرقام غير 0 إلى 9'] += int(bool(ARABIC_DIGITS & set(txt)))
            bad['إشارة طرح غير U+2212'] += int('-' in txt)
            bad['قالب لم يُملأ'] += int('{' in txt or '}' in txt)
        bad['حروف عربية في النص الإنجليزي'] += int(any('؀' <= ch <= 'ۿ' for ch in it['text_en']))
        m = it.get('model')
        bad['بند خط أعداد بلا رسمه، أو رسم لغير بنده'] += int((m is None) != (it['performance'] not in LINES + ('compare',)))
        if m is not None and it['performance'] == 'compare':  # الحلان يُعاد حسابهما: أ ينتهي عند الناتج، و ب عند المطروح منه
            a, b = it['numbers']['a'], it['numbers']['b']
            A, B = m['pair']
            ends = (A['line'] == 'back' and A['start'] == a and a - sum(A['jumps']) == a - b and A['stations'][-1] == a - b
                    and B['line'] == 'up' and B['start'] == b and b + sum(B['jumps']) == a and B['stations'][-1] == a
                    and A['hide'] is None and B['hide'] is None)
            n_a, n_b = len(A['jumps']), len(B['jumps'])
            ans = 'A' if n_a < n_b else 'B' if n_b < n_a else 'same'
            said = all(str(j) in it['text_ar'] and str(j) in it['text_en'] for j in A['jumps'] + B['jumps'])
            bad['رسم الحلين يخالف أعداد بند المقارنة أو جوابه أو نصه'] += int(not (ends and ans == it['answer'] and said))
        elif m is not None:                                   # الرسم يُعاد حسابه هنا مستقلًا: المحطات من القفزات، وآخرها والمخفي
            a, b, cur, seq = it['numbers']['a'], it['numbers']['b'], m['start'], []
            for j in m['jumps']:
                cur += -j if m['line'] == 'back' else j
                seq.append(cur)
            ends = (m['start'] == a and cur == a - b) if m['line'] == 'back' else (m['start'] == b and cur == a)
            asked = {'total': sum(m['jumps']), 'jump': None, 'station': None}[m['hide'][0]]
            if m['hide'][0] == 'jump':
                asked = m['jumps'][m['hide'][1]]
            elif m['hide'][0] == 'station':
                asked = m['stations'][m['hide'][1]]
            said = all(str(j) in it['text_ar'] for k, j in enumerate(m['jumps']) if m['hide'] != ['jump', k])
            bad['رسم خط الأعداد يخالف أعداد بنده أو جوابه أو نصه'] += int(
                seq != m['stations'] or not ends or asked != it['answer'] or any(j <= 0 for j in m['jumps']) or not said)
        if it['answer_type'] == 'ج1':
            bad['جواب خارج المجال'] += int(not (isinstance(it['answer'], int) and 0 <= it['answer'] <= 99))
            bad['إجابة خاطئة متوقعة تساوي الصحيحة'] += int(it['answer'] in it['wrong'])
    ids = Counter(it['id'] for it in items)
    bad['معرّف مكرر'] += sum(1 for v in ids.values() if v > 1)
    for skill in SLOTS:                                     # الخانات في المجال الكبير
        facts = Counter((it['numbers']['a'], it['numbers']['b']) for it in items if it['skill'] == skill)
        bad['حقيقة مكررة في مهارة مجالها كبير'] += sum(1 for v in facts.values() if v > 1)
        for attempt in ('A', 'B', 'C'):
            its = by[(skill, 'check' + attempt)]
            preds = [f for c, _d, f in SLOTS[skill] for _ in range(c)]
            bad['محاولة بلا 10 خانات'] += int(sorted(i['slot'] for i in its if i['role'] == 'check')
                                                != list(range(1, 11)))
            for i in its:
                bad['بند لا يحقق شرط خانته'] += int(not preds[i['slot'] - 1](i['numbers']['a'], i['numbers']['b']))
            bad['خانة بلا بديل'] += 10 - sum(1 for i in its if i['role'] == 'check.alternate')
    unit = Counter((it['numbers']['a'], it['numbers']['b']) for it in items if it['skill'] in SLOTS)
    bad['حقيقة مكررة في الوحدة 3-5'] += sum(1 for v in unit.values() if v > 1)
    for skill, spec in SLOTS_SMALL.items():                 # الخانات في المجال الصغير
        flat = [(perf, values) for c, _d, perf, values in spec for _ in range(c)]
        cases = []
        for attempt in ('A', 'B', 'C'):
            its = by[(skill, 'check' + attempt)]
            mains = sorted((i for i in its if i['role'] == 'check'), key=lambda i: i['slot'])
            bad['محاولة بلا 10 خانات'] += int([i['slot'] for i in mains] != list(range(1, 11)))
            for i in its:
                perf, values = flat[i['slot'] - 1]
                v = i['numbers'].get('n', i['numbers'].get('e'))
                bad['بند لا يحقق شرط خانته'] += int(i['performance'] != perf or v not in values)
            key = [(i['performance'], i['numbers'].get('n', i['numbers'].get('e'))) for i in mains]
            bad['هوية مكررة في محاولة واحدة'] += len(key) - len(set(key))
            if skill == '1-4-2':
                nums = sorted(i['numbers']['n'] for i in mains[:9])
                bad['الأعداد 1 إلى 9 ليست كلها مرة واحدة'] += int(nums != list(range(1, 10)))
            if attempt != 'C':                              # الحالتان على المحاولتين الأوليين، والثالثة تعيد إحداهما
                cases.append(mains[7 if skill == '1-4-1' else 9]['numbers']['n'])
        bad['حالتا الصفر والعشرة لم تتوزعا على المحاولتين'] += int(sorted(cases) != [0, 10])
    for skill, want in GATE_LEN.items():
        for kind in ('gate', 'gate.compensation', 'gate.alternate'):
            pair = [[(i['role'], i['evidence']) for i in by[(skill, g)] if i['role'] == kind] for g in ('gate', 'regate')]
            bad['إعادة البوابة لا تطابق البوابة في بنيتها'] += int(pair[0] != pair[1])
        g = [i for i in by[(skill, 'gate')] if i['role'] == 'gate']
        bad['طول البوابة لا يطابق قالبها'] += int(len(g) != want)
        kinds = [i['evidence'] in ('ف3', 'ف4') for i in g]
        bad['بنود الحساب ليست أولًا في البوابة'] += int(kinds != sorted(kinds, reverse=True))
        for t in EVIDENCE[skill]:
            for rnd in (1, 2):
                ev = [i for i in by[(skill, 'evidence')] if i['evidence'] == t and i.get('round') == rnd]
                alt = [i for i in ev if i['role'] == 'evidence.alternate']
                ev = [i for i in ev if i['role'] != 'evidence.alternate']
                bad['دليل الفهم ليس 2 + 2 لكل نوع في كل جولة'] += int(len(ev) != 4)
                bad['لا بديل واحد لنوع في جولة دليل الفهم'] += int(len(alt) != 1)
                bad['بديل دليل الفهم يكرر حقيقة من بنود نوعه في جولته'] += sum(
                    1 for a in alt if a.get('fact') in [i.get('fact') for i in ev])
            bad['لا بندا «جرّب أولًا» لنوع'] += int(
                sum(1 for i in by[(skill, 'tryfirst')] if i['evidence'] == t) != 2)
            bad['لا بندا تعويض لنوع في البوابة'] += int(
                sum(1 for i in by[(skill, 'gate')] if i['role'] == 'gate.compensation' and i['evidence'] == t) != 2)
            bad['لا بديلان لنوع في البوابة'] += int(
                sum(1 for i in by[(skill, 'gate')] if i['role'] == 'gate.alternate' and i['evidence'] == t) != 2)
        bad['قفزة قيمتها صفر في تسلسل الحل المعروض'] += sum(1 for i in items if i['skill'] == skill and zero_step(i))
        for role, sets in (('deferred_check', (0,)), ('deferred_check.alternate', (1,))):
            rounds = Counter((i.get('set', 0), i['slot']) for i in by[(skill, 'deferred')] if i['role'] == role)
            bad['الفحص المؤجل ليس 3 جولات من 5 بنود، أو بدائله ليست مجموعة من 5 لكل جولة'] += int(
                rounds != Counter({(k, r): 5 for k in sets for r in (1, 2, 3)}))
        ids = lambda role, r: {i['id'] for i in by[(skill, 'deferred')] if i['role'] == role and i['slot'] == r}
        bad['بند بديل في الفحص المؤجل هو بند من جولته الأصلية'] += sum(
            len(ids('deferred_check', r) & ids('deferred_check.alternate', r)) for r in (1, 2, 3))
    return bad


def rejected_examples():
    """الأمثلة المرفوضة المكتوبة في 10.2: يجب أن ترفضها شروط خاناتها."""
    s = SLOTS
    cases = [('3-5-1 «بلا عبور»: 68 − 20', s['3-5-1'][0][2](68, 20)), ('3-5-1 «بلا عبور»: 83 − 17', s['3-5-1'][0][2](83, 17)),
             ('3-5-2 الخانات الأولى: 62 − 48', s['3-5-2'][0][2](62, 48)), ('3-5-2 الخانات الأولى: 60 − 58', s['3-5-2'][0][2](60, 58)),
             ('3-5-3 الخانات الأولى: 64 − 37', s['3-5-3'][0][2](64, 37)), ('1-4-1 الخانة 1: خمسة أقراص', 5 in SLOTS_SMALL['1-4-1'][0][3])]
    accepted = [('3-5-1: 68 − 23', s['3-5-1'][0][2](68, 23)), ('3-5-1: 83 − 17', s['3-5-1'][1][2](83, 17)),
                ('3-5-1: 83 − 37', s['3-5-1'][2][2](83, 37)), ('3-5-1: 70 − 34', s['3-5-1'][3][2](70, 34)),
                ('3-5-1: 52 − 47', s['3-5-1'][4][2](52, 47)), ('3-5-2: 62 − 58', s['3-5-2'][0][2](62, 58)),
                ('3-5-2: 62 − 48', s['3-5-2'][1][2](62, 48)), ('3-5-2: 71 − 45', s['3-5-2'][2][2](71, 45)),
                ('3-5-2: 80 − 67', s['3-5-2'][3][2](80, 67)), ('3-5-2: 91 − 56', s['3-5-2'][4][2](91, 56)),
                ('3-5-3: 71 − 68', s['3-5-3'][0][2](71, 68)), ('3-5-3: 83 − 12', s['3-5-3'][1][2](83, 12)),
                ('3-5-3: 64 − 37', s['3-5-3'][2][2](64, 37))]
    return cases, accepted


# ---------------------------------------------------------------- الملف المقروء
def markdown(items, bad, cases, accepted):
    by = defaultdict(list)
    for it in items:
        by[(it['skill'], it['group'])].append(it)
    out = ['# محتوى الشريحة الأولى: الوحدتان 1-4 و3-5', '',
           '13 نوفمبر 2026 · مولَّد من `slice_content.py`، والبنود كاملة في `slice-content.json`. '
           'النصوص هنا عربية؛ الإنجليزية في الملف نفسه لكل بند، وجدول القوالب باللغتين في القسم 7.', '',
           '**الحالة:** محتوى مكتوب ومفحوص آليًا. لم يُعرض على طفل، ولم يُسجَّل صوته، ولم يراجعه معلم.', '',
           '## 1. ما في البنك', '',
           '| المهارة | الدرس | الافتتاح | «جرّب أولًا» لكل نوع | التدريب | دليل الفهم بجولتيه | البوابة وتعويضها وبدائلها | إعادة البوابة | تحقق قصير | محاولات الفحص الثلاث وبدائلها | مؤجل | وصفي |',
           '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for skill in GATE_LEN:
        n = lambda g: len(by[(skill, g)])
        out.append('| %s %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |' % (
            skill, UI['skill.' + skill][0], n('lesson'), n('opening'), n('tryfirst'), n('practice'), n('evidence'), n('gate'), n('regate'),
            n('short'), n('checkA') + n('checkB') + n('checkC'), n('deferred'), n('compare')))
    out += ['', 'المجموع %d بندًا. لكل بند: معرّف، دور، نوع دليل، أداء مطلوب، أعداد، مورد مسموح، نوع إجابة، '
            'جواب، نص وصوت بالعربية والإنجليزية، وإجابات خاطئة متوقعة بوصفها المحايد.' % len(items), '',
            '## 2. التصحيح', '',
            '- **ج1، عدد صحيح:** تُحوَّل الأرقام العربية والفارسية إلى 0–9، وتُقارن القيمة بالجواب. لا يُقبل غير عدد صحيح.',
            '- **ج8، بطاقة:** يُقارن معرّف البطاقة. بنود المقارنة وصفية: تُسجَّل ولا تدخل قرار تقدم.',
            '- **بطاقة «كيف حسبتها؟»** في فحص 3-5-3 بعد الخانة 8: ثلاث بطاقات، يُسجَّل الاختيار بلا تصحيح.',
            '- **الإجابة الخاطئة** تأخذ وصفًا محايدًا: إن كانت من المتوقعة في البند فبوصفها، وإلا «أقل من الصحيح بـ k» أو «أكثر من الصحيح بـ k».',
            '- في البوابة وفحص الاستقلال لا يُعرض وصف ولا تصحيح أثناءهما.', '',
            '## 3. خانات فحص الاستقلال ومحاولاته الثلاث', '']
    for skill in GATE_LEN:
        spec = [(c, d) for c, d, *_ in (SLOTS.get(skill) or SLOTS_SMALL[skill])]
        desc = [d for c, d in spec for _ in range(c)]
        out += ['### %s %s' % (skill, UI['skill.' + skill][0]), '',
                '| الخانة | شرطها | المحاولة أ | بديلها | المحاولة ب | بديلها | المحاولة ج | بديلها |',
                '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for k in range(1, 11):
            cell = []
            for attempt in ('A', 'B', 'C'):
                for role in ('check', 'check.alternate'):
                    i = [x for x in by[(skill, 'check' + attempt)] if x['slot'] == k and x['role'] == role][0]
                    cell.append(short(i) + (' *' if i.get('note', '').startswith('لا قيمة') else ''))
            out.append('| %d | %s | %s |' % (k, desc[k - 1], ' | '.join(cell)))
        out.append('')
    out += ['\\* لا قيمة أخرى تحقق شرط الخانة، فالبديل إعادة عرض الحقيقة نفسها بقرار الأب (3.6). انظر القسم 8.', '',
            '## 4. بقية البنود', '']
    names = [('lesson', 'الدرس'), ('opening', 'الافتتاح: «جرّب أولًا» ثم 3 بنود موجَّهة'),
             ('tryfirst', '«جرّب أولًا» بعد بوابة أخفقت: بندان لكل نوع، يُعرض منها نوعا الخطأ (6.2)'), ('practice', 'التدريب'),
             ('evidence', 'دليل الفهم: جولتان، في كل منهما بندان لكل نوع وبندان احتياطيان بعد الدرس القصير. وآخر القائمة '
                          'بديل واحد لكل نوع في كل جولة، لبند استُبعد بعد أن أُجيب عنه أو طُلب فيه دعم (R18-01)'),
             ('gate', 'البوابة، بنود الحساب أولًا، ثم بندا تعويض وبديلان لكل نوع'),
             ('regate', 'إعادة البوابة الوحيدة، ببنود جديدة وبالبنية نفسها'), ('short', 'التحقق القصير'),
             ('deferred', 'الفحص المؤجل: ثلاث جولات من 5 بنود بعد 7 و21 و60 يومًا. ثم مجموعة بديلة من 5 لكل جولة، لجولة '
                          'لاحقة بعد طلب مساعدة أنهى الجولة بلا حكم (ت3)'),
             ('compare', 'الفحص الوصفي للمقارنة')]
    for skill in GATE_LEN:
        out += ['### %s' % skill, '']
        for g, title in names:
            if by[(skill, g)]:
                out.append('- **%s:** %s' % (title, '، '.join('%s %s' % (i['evidence'] or LABEL[i['role']], short(i))
                                                              for i in by[(skill, g)])))
        out.append('')
    out += ['## 5. أمثلة من النصوص', '', '| البند | العربية | الإنجليزية | الجواب |', '| --- | --- | --- | --- |']
    seen = set()
    for it in items:
        key = (it['skill'][:3], it['performance'], it['numbers'].get('ctx'))
        if key not in seen:
            seen.add(key)
            out.append('| %s | %s | %s | %s |' % (it['id'], it['text_ar'], it['text_en'], it['answer']))
    out += ['', '## 6. الأوصاف المحايدة للإجابات الخاطئة', '',
            '| الرمز | الوصف | بالإنجليزية | السؤال التشخيصي | بالإنجليزية |', '| --- | --- | --- | --- | --- |']
    out += ['| `%s` | %s | %s | %s | %s |' % ((k,) + v) for k, v in DESCRIBE.items()]
    out += ['', 'المتغيرات في أسئلة التشخيص تُملأ من أعداد البند، والمعادلات فيها معزولة الاتجاه.', '',
            '## 7. نصوص الواجهة والبطاقات', '', '| المفتاح | العربية | الإنجليزية |', '| --- | --- | --- |']
    out += ['| `%s` | %s | %s |' % (k, v[0], v[1]) for k, v in UI.items()]
    out += ['| `card.%s.%s` | %s | %s |' % (g, k, v[0], v[1]) for g, d in CARDS.items() for k, v in d.items()]
    out += ['', '## 8. ما يحتاج قرارًا أو مراجعة', '',
            '- **بدائل الخانات في المجال الصغير: حُسمت.** في 1-4-2 تستنفد خانات المحاولة الأعداد التي تحقق شروطها، '
            'فلا يبقى عدد آخر يحقق شرط خانة انقطع بندها. وكذلك خانة «خمسة أقراص» في 1-4-1. بقرار الأب في 13 نوفمبر '
            '2026 (3.6): يُعاد عرض الحقيقة نفسها بعد الانقطاع، ويُسجَّل البند «أُعيد عرضه بعد انقطاع». الطفل لم يُجب، '
            'فلا دليل تسرّب غير رؤية السؤال. وانقطاعان في الخانة نفسها يعلّقان الفحص للمراجعة، كما في بقية المهارات. '
            'البنود المعلَّمة بنجمة هي هذه البدائل: 33 بديلًا في المحاولات الثلاث.',
            '- **جملة 10.2** عن حقائق 1-4-1 و1-4-2 عُدّلت مع القرار، لأنها كانت تقول إن حقائقهما تكفي محاولة '
            'واحدة ببدائلها.',
            '- **تصحيح بعد التسليم السابق.** كان الفحص المؤجل 3 بنود، والصحيح 5 بنود في كل جولة، وجولاته ثلاث '
            '(3.7). ولم يكن للبوابة بدائل يُستبدل بها البند المنقطع (6.1)، فأُضيف بديلان لكل نوع. ولم يكن لإعادة '
            'البوابة بنود، فكانت ستعرض على الطفل البنود التي أجاب عنها، فأُضيفت لها مجموعة جديدة بالبنية نفسها. وجدتُ '
            'الثلاثة وأنا أكتب طبقة البنود.',
            '- **تصحيح ثانٍ.** إذا لم يثبت الفهم في جولة دليله، كانت الجولة التالية ستعرض البنود نفسها، و3.5 تشترط '
            'بنودًا جديدة. وكانت محاولة الفحص الثالثة بلا بنود فتُعلَّق للمعلم. أُضيفت جولة ثانية لدليل الفهم ومحاولة ثالثة '
            'للفحص، بالشروط نفسها، بعد بنود المرحلة الأولى فلم تتغير أعدادها. بعد الجولة الثانية أو المحاولة الثالثة '
            'تنفد البنود، فيُعرض الأمر على المعلم.',
            '- **بندا «جرّب أولًا» لكل نوع.** بقرار الأب (6.2): بعد بوابة أخفقت يُؤخذ بندا «جرّب أولًا» من نوعي الخطأ فيها، '
            'فأُضيف بندان لكل نوع. المهارة التي لا بوابة أخفقت لها تبقى على البندين الثابتين في الافتتاح.',
            '- **بنود ف1 في 3-5-1 و3-5-2** قراءة نموذج معروض، لا بناؤه. بناء النموذج بالنقر يحتاج نوع إجابة ليس في '
            'ج1 إلى ج9، فتُرك للدرس (خطوة «افعل بالنموذج») ولم يدخل دليل الفهم.',
            '- **مقارنة الحلين.** بشروط خانات الوحدة، وفيها آحاد المطروح ليست صفرًا، لا يكون القفز للخلف أقل قفزات من '
            'الإكمال في أي مسألة: الجواب «الحل ب» أو «متساويان» دائمًا. لذلك أُدخلت في بنود المقارنة مسائل مطروحها '
            'عشرات كاملة، مثل ' + eq('83 %s 30' % MINUS) + '، ليكون «الحل أ» جوابًا ممكنًا. هذه البنود وصفية ولا تدخل الفحص.',
            '- **تكرار الحقائق.** في 1-4-1 و1-4-2 سبق عرض حقيقة %d من %d بندًا في دليل الفهم والفحصين والمؤجل. '
            'هذا حتمي في مجال من 11 حقيقة، ومسجَّل لكل بند في الحقل `fact_seen_before`. في الوحدة 3-5 لا حقيقة مكررة.'
            % (sum(1 for i in items if i['skill'] < '2' and i['group'] in PATH[3:] and i.get('fact_seen_before')),
               sum(1 for i in items if i['skill'] < '2' and i['group'] in PATH[3:])),
            '- **السياقات** ثمانية مواقف مصوَّرة. الأسماء فيها عامة، وليست أسماء الأطفال. تحتاج رسمًا، ومراجعة من المعلم.',
            '- **الصوت** نصه هو نص البند. من يسجّله، ونطق الأعداد المركّبة بالإنجليزية، مفتوحان.',
            '- **الصياغة العربية** تتجنب تمييز العدد المتغير («عدد الركاب 3» بدل «3 ركاب») ليصح النص مع كل عدد.', '',
            '## 9. نتيجة الفحص الآلي', '']
    out += ['- %s: %d' % kv for kv in sorted(bad.items())]
    out += ['', 'الأمثلة المرفوضة في 10.2، وكلها يجب أن ترفضها شروط خاناتها: '
            + '؛ '.join('%s: %s' % (n, 'مقبول، خطأ' if v else 'مرفوض') for n, v in cases) + '.',
            '', 'الأمثلة المقبولة في 10.2، وكلها يجب أن تقبلها شروط خاناتها: '
            + '؛ '.join('%s: %s' % (n, 'مقبول' if v else 'مرفوض، خطأ') for n, v in accepted) + '.',
            '', 'هذا الفحص يثبت أن كل بند يحقق الشروط المكتوبة وأن جوابه صحيح حسابيًا. لا يثبت أن البند مناسب '
            'تربويًا، ولا أن الصياغة واضحة للطفل، ولا أن الشروط نفسها كافية.']
    return '\n'.join(out) + '\n'


LABEL = {'lesson.watch': 'شاهِد', 'lesson.model': 'بالنموذج', 'lesson.fade': 'يخفت', 'lesson.nomodel': 'بلا نموذج',
         'lesson.compare': 'مقارنة', 'practice': 'تدريب', 'practice.more': 'تدريب إضافي'}
PATH = ['lesson', 'opening', 'practice', 'evidence', 'checkA', 'checkB', 'checkC', 'deferred', 'more']   # الإضافي آخرًا: لا يغيّر وسم بند سابق


def mark_seen(items):
    """في مسار التعلّم: هل سبق عرض الحقيقة الحسابية نفسها قبل هذا البند؟ (3.5)"""
    for skill in GATE_LEN:
        seen = set()
        for g in PATH:
            now = set()
            for it in items:
                if it['skill'] == skill and it['group'] == g:
                    n = it['numbers']
                    v = n.get('n', n.get('e'))
                    fact = (n['a'], n['b']) if 'a' in n else tuple(sorted((v, 10 - v)))
                    it['fact'] = list(fact)
                    it['fact_seen_before'] = fact in seen
                    if it['role'] != 'evidence.alternate':  # البديل يُعرض نادرًا، فلا يجعل ما بعده «سبق عرضه»
                        now.add(fact)
            seen |= now


def short(it):
    n = it['numbers']
    if 'a' in n:
        return eq('%d %s %d' % (n['a'], MINUS, n['b']))
    p = it['performance']
    if p == 'frame_counters':
        return 'فارغ %d' % n['e']
    if p == 'frame_empty':
        return 'أقراص %d' % n['n']
    if p == 'missing_first':
        return eq('%s + %d = 10' % (BOX, n['n']))
    if p in ('subtract', 'step_pair'):
        return eq('10 %s %d = %s' % (MINUS, n['n'], BOX))
    return eq('%d + %s = 10' % (n['n'], BOX))


if __name__ == '__main__':
    rng = random.Random(SEED)
    bank = Bank()
    build_small(bank, rng)
    build_big(bank, rng, set())
    for it in bank.items:
        if it['group'] == 'evidence':
            it.setdefault('round', 1)
    respaced = respace_small(bank.items)
    more_small(bank)
    mark_seen(bank.items)
    for it in bank.items:                                   # كل بند يحمل حقيقته: يقرؤها المجدول للتتابع بين الأنشطة
        if 'fact' not in it:
            n = it['numbers']
            v = n.get('n', n.get('e'))
            it['fact'] = [n['a'], n['b']] if 'a' in n else sorted((v, 10 - v))
    for it in bank.items:                                   # بنود خط الأعداد تحمل ما يُرسم لها، بعد أن ثبتت أعدادها
        if it['performance'] in LINES:
            it['model'] = line_model(it['performance'], it['numbers'])
        elif it['performance'] == 'compare':
            it['model'] = compare_model(it['numbers'])
    for it in bank.items:                                   # بطاقة «كيف حسبتها؟» (10.2): بند الخانة 8 في محاولات الفحص وبدائله
        if it['role'] in ('check', 'check.alternate') and HOW_SLOT.get(it['skill']) == it['slot']:
            it['how'] = True
    bad = validate(bank.items)
    bad['بطاقة «كيف حسبتها؟» على غير خانتها أو غير بند فحص'] += sum(
        1 for it in bank.items if it.get('how') and not (it['role'] in ('check', 'check.alternate')
                                                         and HOW_SLOT.get(it['skill']) == it['slot']))
    from content_sequence import collect, violations
    seq_pairs, seq_by, seq_n = collect(bank.items, EVIDENCE)
    seq_bad = violations(seq_pairs, seq_by)
    bad['الحقيقة نفسها في بندين متتاليين أثناء التشغيل (3.5)'] += len(seq_bad)
    cases, accepted = rejected_examples()
    for it in bank.items:
        it['wrong'] = {str(k): v for k, v in it['wrong'].items()}
    # هوية المحتوى (ك1): بصمة لكل بند، وبصمة للحزمة، ورقم إصدار من سجل الإصدارات لا يُعاد استعماله. تغيّر أي بند
    # أو نص يغيّر البصمة فيأخذ الرقم التالي ويُكتب في السجل. الرقمان 1 و2 سبقا السجل، والرقم 2 استُعمل لمحتويين
    from content_source import item_digest, pack_digest, next_version
    for it in bank.items:
        it.pop('v', None)
        it['v'] = item_digest(it)
    pack = dict(texts={k: dict(ar=v[0], en=v[1]) for k, v in T.items()},
                ui={k: dict(ar=v[0], en=v[1]) for k, v in UI.items()},
                cards={g: {k: dict(ar=v[0], en=v[1]) for k, v in d.items()} for g, d in CARDS.items()},
                describe={k: dict(ar=v[0], en=v[1], ask_ar=v[2], ask_en=v[3]) for k, v in DESCRIBE.items()},
                items=bank.items)
    digest = pack_digest(pack)
    book = json.load(open(LEDGER, encoding='utf-8'))
    version = next_version(book['packs'], digest)
    if not book['packs'] or book['packs'][-1]['version'] != version:
        book['packs'].append(dict(version=version, digest=digest, items=len(bank.items)))
        json.dump(book, open(LEDGER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('إصدار محتوى جديد: %d (%s)' % (version, digest[:12]))
    json.dump(dict(version=version, digest=digest, seed=SEED, **pack),
              open('slice-content.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open('slice-content.md', 'w', encoding='utf-8').write(markdown(bank.items, bad, cases, accepted))
    print('البنود: %d' % len(bank.items))
    for k, v in sorted(bad.items()):
        print('  %s: %d' % (k, v))
    wrong = [n for n, v in cases if v] + [n for n, v in accepted if not v]
    print('أمثلة 10.2 المرفوضة والمقبولة: %s' % ('مطابقة' if not wrong else 'تخالف: ' + '، '.join(wrong)))
    print('تتابع البنود أثناء التشغيل: %d نشاطًا مستكشَفًا، و%d زوجًا ممكنًا، وأُعيد اختيار عدد %d بندًا في الوحدة 1-4'
          % (seq_n, len(seq_pairs), respaced))
    for a, b, how, label, f in seq_bad[:8]:
        print('    %s ثم %s (%s) في %s: الحقيقة %s' % (a, b, how, label, f))
    flagged = sum(1 for it in bank.items if it.get('note', '').startswith('لا قيمة'))
    print('بدائل تعيد الحقيقة نفسها (3.6، بقرار الأب): %d' % flagged)
    hard = {k: v for k, v in bad.items() if v and k != 'هوية مكررة في محاولة واحدة'}
    sys.exit(1 if hard or wrong else 0)
