#!/usr/bin/env python3
"""محرك مرجعي لانتقال الحالات في التشخيص وفتح الدروس (الأقسام 3.4 و6.1 و6.2 و8.3 من الخريطة).

    python3 transition_engine.py <ملف الخريطة> --table     # يطبع جدول الانتقالات بصيغة Markdown
    python3 test_transition_engine.py <ملف الخريطة>         # يشغّل اختبارات المحرك

هذا مرجع قابل للتنفيذ لمواصفة الانتقالات، وليس التطبيق. قواعده:
- كل تغيير يدخل حدثًا له معرّف. المعرّف نفسه بالمحتوى نفسه إعادة إرسال بلا أثر، وبمحتوى مختلف مرفوض.
- كل حدث يُفحص مخططه (الحقول وأنواعها وقيمها) ثم شروط قبوله، قبل أي تغيير. المرفوض لا يكتب شيئًا:
  لا دليل، ولا سجل، ولا عدّاد. ويعيد رمز الرفض وسببه والمتطلب الناقص إن وُجد.
- التطبيق ذرّي: يكتمل الحدث كله، أو تعود الحالة كما كانت، ولو وقع استثناء في منتصفه.
- المحرك يحفظ نسخة مستقلة من الحدث ويعيد نسخة مستقلة من النتيجة. تعديل المدخل أو المخرج لا يغيّره.
- لكل دليل معرّف ونوع ومصدر وجلسة وعلامة صلاحية. حالة كل مهارة تُشتق من الأدلة الصالحة وقرارات
  المعلم السارية، ولا تُخزَّن. إبطال جلسة يُسقط صلاحية أدلتها هي وحدها، ثم تُشتق الحالات من جديد.
- الحالة كلها قاموس يُحفظ نصًّا (JSON). الاستئناف قراءة هذا النص، وإعادة تشغيل السجل تعطي الحالة نفسها.

ما ليس فيه: اختيار النشاط التالي (المجدول)، وبنود الأسئلة وتصحيحها، وحساب «ثبت الفهم» من البنود،
وميزانية 20 بندًا لبوابتي جلسة البحث، وفحص يوم الأسرة لفحص الاستقلال. هذه تسبق الحدث أو تليه
في التطبيق، والمحرك يستقبل نتيجتها حدثًا.
"""
import copy
import json
import pickle
import re
import sys

ROW = re.compile(r'^\| (\d-\d-\d) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$', re.M)


def load_network(path, stages='123'):
    """شبكة الإصدار 1 من ملف الخريطة: المعرّفات بترتيبها، والمتطلبات المباشرة."""
    ids, pre = [], {}
    for sid, _t, _m, req, ev, _a in ROW.findall(open(path, encoding='utf-8').read()):
        if not re.findall(r'ف\d', ev) or sid in pre or sid[0] not in stages:
            continue
        ids.append(sid)
        pre[sid] = re.findall(r'\d-\d-\d', req)
    return ids, pre


EXEMPT, STUMBLE, UNDERSTOOD, INDEPENDENT, SHORT_OK, RECHECK = (
    'exempt', 'stumble', 'understood', 'independent', 'short_ok', 'recheck')
SATISFIED = ('exempt', 'met')
BLOCKING = ('stumbled', 'waiting')

# حصص الجلسة بحسب نوعها: بوابات، تحققات قصيرة، حصة تعليمية
QUOTA = {
    'search': {'gate': {'older': 2, 'young': 1}, 'short': 0, 'teach': 0},
    'start': {'gate': 0, 'short': 4, 'teach': 1},
    'follow': {'gate': 1, 'short': 2, 'teach': 1},
}
SEARCH_CAP = 4
# 3.7: فواصل فحوص الاحتفاظ بالأيام. الأول من يوم اجتياز الاستقلال، وكل فاصل بعده من يوم الفحص السابق الفعلي
RETENTION_GAPS = (7, 21, 60)
# نسخة ترحيل الحالة المحفوظة (المراجعة 12). حالة نسختها أقل تُراجع محاولاتها عند قراءتها، ولو كانت فيها قائمة الجلسات
# المساهمة: الالتزام 16b124a كان يضيف القائمة ولا يطبّق أثر الإبطال. 0: بلا حقل، أي كل ما حُفظ قبل هذه النسخة
MIGRATION = 1
RETENTION_ITEMS, RETENTION_OK = 5, 4

REASONS = {
    'unknown_skill': 'المهارة ليست في المحتوى المسلَّم',
    'no_session': 'لا جلسة مفتوحة بهذا المعرّف',
    'session_open': 'جلسة أخرى مفتوحة ولم تُختم',
    'session_order': 'نوع الجلسة لا يأتي في هذا الموضع: بحث (4 على الأكثر) ثم بدء واحدة ثم متابعة',
    'quota_gate': 'استُهلكت بوابات هذه الجلسة، أو لا بوابة في هذا النوع من الجلسات',
    'quota_short': 'استُهلكت التحققات القصيرة في هذه الجلسة',
    'quota_teach': 'استُهلكت الحصة التعليمية الواحدة في هذه الجلسة',
    'blocked': 'متطلب مباشر متعثَّر فيه أو ينتظر: المهارة لا تُفحص',
    'prerequisite': 'متطلب مباشر غير مستوفى',
    'already_satisfied': 'المهارة مجتازة أو مستوفاة',
    'gate_limit': 'للمهارة بوابة وإعادة واحدة على الأكثر',
    'regate_not_allowed': 'الإعادة بعد فتح الدرس واختصاره، وفي جلسة لاحقة، وإن سُمح بها',
    'not_checkable': 'التحقق القصير للمؤجَّلة أو لمتطلب غير مفحوص، ومرة واحدة',
    'already_open': 'درس المهارة مفتوح',
    'not_open': 'درس المهارة غير مفتوح، أو ليس في الطور المطلوب',
    'suspended': 'الوصول إلى المهارة معلَّق حتى إعادة التحقق أو قرار المعلم',
    'understanding_first': 'فحص الاستقلال بعد ثبوت الفهم',
    'bad_decision': 'قرار المعلم ناقص: السبب، أو متطلب غير مستوفى لم يُذكر في المتجاوَز',
    'not_deferrable': 'للمهارة دليل مباشر، فلا تؤجَّل بقرار',
    'no_decision': 'لا قرار سارٍ بهذا المعرّف',
    'bad_target': 'الجلسة غير موجودة، أو ما زالت مفتوحة، أو أُبطلت من قبل',
    'no_recheck': 'لا مهارة معلَّقة تنتظر هذا المتطلب، ولا دليل استيفاء مُبطَل لهذه المهارة يُعاد بناؤه',
    'bad_event': 'الحدث ناقص أو فيه حقل بنوع أو قيمة غير مسموحة',
    'event_id_conflict': 'المعرّف نفسه وصل من قبل بمحتوى مختلف',
    'internal_error': 'تعطّل التنفيذ، وأُعيدت الحالة كما كانت قبل الطلب',
    'lesson_idle': 'الدرس ليس نشطًا في هذه الجلسة أو ينتظر حصة تعليمية: يُستأنف بحدث صريح',
    'already_active': 'الدرس أو محاولة الفحص نشط في هذه الجلسة',
    'check_idle': 'محاولة الفحص ليست نشطة في هذه الجلسة: تُستأنف بحدث صريح يستهلك الحصة التعليمية',
    'no_check': 'لا محاولة فحص بهذا المعرّف لهذه المهارة',
    'check_state': 'محاولة الفحص أُغلقت، أو تُركت، أو عُلّقت للمراجعة، أو تحتاج إعادة بدء، أو معرّفها مستعمل',
    'check_pending': 'للمهارة محاولة فحص لم تُغلق: تُتمّ، أو يتركها المعلم بحدث صريح، قبل بدء أخرى',
    'version_unavailable': 'إصدار تعريفات بنود الفحص غير متاح',
    'date_unconfirmed': 'تاريخ الجلسة يحتاج تأكيد الوالد: جاء قبل يوم آخر جلسة أو بعده بأكثر من 30 يومًا',
    'not_flagged': 'الجلسة ليست معلَّمة بتنبيه تاريخ',
    'check_same_day': 'فحص الاستقلال في يوم بعد يوم آخر دليل فهم، والإعادة في يوم بعد يوم المحاولة السابقة',
    'check_needs_practice': 'بعد محاولة لم تُجتز تلزم جلسة نشط فيها الدرس قبل الإعادة',
    'not_met': 'فحص الاحتفاظ لمهارة مستوفاة باجتياز فحص الاستقلال',
    'retention_done': 'أُجريت فحوص الاحتفاظ الثلاثة لهذه المهارة',
    'retention_early': 'لم يحِن موعد فحص الاحتفاظ: الفاصل يُحسب من يوم الاجتياز ثم من يوم الفحص السابق',
}

RESULTS = ('pass', 'fail', 'help')
OPEN_CHECK = ('pending', 'held', 'needs_restart')        # محاولة لم تُغلق ولم تُترك: تمنع بدء أخرى
# مخطط كل حدث: الحقول المطلوبة وأنواعها وقيمها. الحقل المنتهي بعلامة ? اختياري. لا يُقبل حقل غيرها.
SCHEMA = {
    'session_start': {'session': str, 'kind': ('search', 'start', 'follow'), 'day': int},
    'date_confirmed': {'target': str},
    'session_end': {'session': str},
    'gate_result': {'session': str, 'skill': str, 'result': RESULTS + ('interrupted',),
                    'errors?': [str], 'has_calc?': bool, 'items?': [str]},
    'short_check_result': {'session': str, 'skill': str, 'ok': bool, 'items?': [str]},
    'open_lesson': {'session': str, 'skill': str},
    'resume_lesson': {'session': str, 'skill': str},
    'lesson_opening_result': {'session': str, 'skill': str, 'outcome': ('skip', 'full_error', 'full_help'),
                              'items?': [str]},
    'understanding_proved': {'session': str, 'skill': str, 'items?': [str]},
    'check_started': {'session': str, 'skill': str, 'check_id': str, 'content_version': int},
    'check_resumed': {'session': str, 'skill': str, 'check_id': str},
    'check_held': {'session': str, 'skill': str, 'check_id': str,
                   'reason': ('interruptions', 'no_alternate', 'no_items'), 'items?': [str]},
    'check_abandoned': {'check_id': str, 'reason': str},
    'independence_result': {'session': str, 'skill': str, 'check_id': str, 'result': RESULTS, 'items?': [str]},
    'teacher_open': {'skill': str, 'bypass': [str], 'reason': str},
    'teacher_defer': {'skills': [str], 'reason': str},
    'teacher_revoke': {'decision': str},
    'recheck_result': {'session': str, 'skill': str, 'ok': bool, 'items?': [str]},
    'invalidate_session': {'target': str},
    'retention_result': {'session': str, 'skill': str, 'correct': int, 'exposed?': bool, 'items?': [str]},
}


def _fits(v, rule):
    if rule is str:
        return isinstance(v, str) and v != ''
    if rule in (bool, int):
        return type(v) is rule
    if isinstance(rule, tuple):
        return isinstance(v, str) and v in rule
    return isinstance(v, list) and all(isinstance(x, str) and x for x in v)

# جدول الانتقالات. منه يُطبع جدول المواصفة، وأسماء الأحداث فيه هي أسماء دوال الفحص والتنفيذ.
TABLE = [
    ('session_start', 'بدء جلسة',
     'لا جلسة مفتوحة. يوم الأسرة عدد صحيح غير سالب. بحث: أقل من 4 جلسات بحث ولم تقع جلسة البدء. بدء: مرة '
     'واحدة. متابعة: بعد جلسة البدء',
     'تُفتح الجلسة بنوعها ويومها وعدّاداتها صفر. مرجع التاريخ يوم آخر جلسة، بترتيب الجلسات، تاريخها موثوق: لم '
     'تُعلَّم بتنبيه، أو عُلّمت ثم أكّد الوالد تاريخها. الجلسة المبطلة تبقى مرجعًا لأن الإبطال يخص الطفل لا ساعة '
     'الجهاز. إن جاء يومها قبل المرجع، أو بعده بأكثر من 30 يومًا، عُلّمت بتنبيه تاريخ (9.1)',
     'session_open، session_order، bad_event', 'لا أثر'),
    ('session_end', 'ختم الجلسة', 'هي الجلسة المفتوحة', 'تُختم. ما لم يكتمل يبقى في حالته',
     'no_session', 'لا أثر'),
    ('date_confirmed', 'تأكيد التاريخ من الوالد', 'الجلسة معلَّمة بتنبيه تاريخ',
     'يزول التنبيه، فتُقبل في الجلسة القرارات المعتمدة على التاريخ، ويصير يومها مرجع التاريخ للجلسات بعدها إن '
     'كانت آخر جلسة موثوقة. الجلسة وأحداثها لا تُحذف ولا تُعدَّل، والتنبيه يبقى في التاريخ',
     'not_flagged', 'لا أثر'),
    ('gate_result', 'نتيجة بوابة',
     'جلسة مفتوحة وفيها حصة بوابة. لا متطلب مباشر متعثَّر فيه أو ينتظر. المهارة غير مجتازة. '
     'بوابتان على الأكثر في دورة التحقق الحالية، أي في الجلسات غير المبطلة. الثانية، وكل بوابة '
     'بعد فتح الدرس، تأتي بعد اختصاره وفي جلسة لاحقة',
     'اجتاز: دليل إعفاء. أخفق: دليل تعثّر ومعالجته من أنواع الأخطاء. طلب دعم: تُحفظ العلّة ولا دليل. '
     'انقطعت: محاولة بلا نتيجة ولا تُعدّ. بعد فتح الدرس، الإخفاق وطلب الدعم يُمضيان الدرس كاملًا إن '
     'بقيت حصة تعليمية في الجلسة، وإلا صار الدرس «ينتظر حصة»',
     'no_session، unknown_skill، quota_gate، blocked، already_satisfied، gate_limit، regate_not_allowed',
     'تُشتق الحالات من جديد: التعثّر يجعل التوابع بلا دليل مباشر «تنتظر»، والاجتياز يؤجّل الأسلاف '
     'ويفكّ ما كان ينتظر. طلب الدعم لا يغيّر حالة أحد'),
    ('short_check_result', 'نتيجة تحقق قصير',
     'جلسة مفتوحة وفيها حصة تحقق. المهارة مؤجَّلة أو غير مفحوصة، لم يُجرَ تحققها، ولا يمنعها متطلب',
     'صحّت الثلاثة: دليل تحقق قصير. غير ذلك: تُسجَّل بوابتها',
     'no_session، unknown_skill، quota_short، blocked، not_checkable', 'لا يغيّر الحالات. يدخل أهلية جلسة البدء'),
    ('open_lesson', 'فتح درس',
     'جلسة بدء أو متابعة وفيها الحصة التعليمية. الدرس غير مفتوح. المهارة غير مجتازة. دالة الأهلية تجيز',
     'يُسجَّل الفتح بجلسته وطوره، ويصير الدرس نشطًا في هذه الجلسة وتُسجَّل في جلسات تدريسه، وتُستهلك الحصة '
     'التعليمية',
     'no_session، unknown_skill، quota_teach، already_open، already_satisfied، suspended، prerequisite',
     'لا أثر'),
    ('resume_lesson', 'استئناف درس',
     'جلسة فيها الحصة التعليمية. الدرس مفتوح، في الافتتاح أو كامل أو ينتظر حصة، وليس نشطًا في هذه '
     'الجلسة، وغير معلَّق. دالة الأهلية تجيز بالطور الذي فُتح فيه',
     'يصير الدرس نشطًا في هذه الجلسة وتُسجَّل في جلسات تدريسه، وتُستهلك حصتها التعليمية، وتزول علامة انتظار '
     'الحصة',
     'no_session، unknown_skill، quota_teach، not_open، suspended، already_active، prerequisite', 'لا أثر'),
    ('lesson_opening_result', 'نتيجة «جرّب أولًا» والبنود الموجَّهة',
     'الدرس في طور الافتتاح، ونشط في هذه الجلسة، وغير معلَّق',
     'اختُصر: تُسجَّل بوابة لجلسة لاحقة، إلا لمهارة متعثَّر فيها والإعادة غير مسموحة. '
     'كامل بخطأ: دليل تعثّر من الدرس، بمعالجة آخر تعثّر صالح إن كان، وإلا المسار العادي (6.1). '
     'كامل بطلب دعم: تُحفظ العلّة ولا دليل',
     'no_session، not_open، suspended، lesson_idle', 'دليل التعثّر يجعل التوابع بلا دليل مباشر «تنتظر»'),
    ('understanding_proved', 'ثبوت الفهم', 'الدرس في الافتتاح أو كامل، ونشط في هذه الجلسة، وغير معلَّق',
     'دليل فهم', 'no_session، not_open، suspended، lesson_idle', 'لا أثر قبل اجتياز فحص الاستقلال'),
    ('check_started', 'بدء محاولة فحص الاستقلال',
     'الدرس مفتوح وغير معلَّق ولا ينتظر حصة. الفهم سارٍ، أي ثبت بعد آخر تعثّر. المهارة غير مستوفاة ولا '
     'مجتازة. معرّف المحاولة جديد. لا محاولة أخرى للمهارة لم تُغلق ولم تُترك. إصدار تعريفات البنود '
     'متاح. لا تنبيه تاريخ على الجلسة. يوم الجلسة بعد يوم آخر دليل فهم صالح. بعد محاولة أُغلقت: يوم لاحق '
     'ليوم إغلاقها، وبعد الإخفاق جلسة نشط فيها الدرس بعدها (3.6). في الجلسة حصة تعليمية، لأن الفحص هو نشاط '
     '«تعلّم أو أصلح» في يومه (7.1)',
     'محاولة «معلَّقة» بمعرّفها ومهارتها وإصدار تعريفاتها، نشطة في هذه الجلسة، وتُستهلك الحصة التعليمية',
     'no_session، not_open، suspended، lesson_idle، understanding_first، already_satisfied، check_state، '
     'check_pending، version_unavailable، date_unconfirmed، check_same_day، check_needs_practice، quota_teach',
     'لا أثر'),
    ('check_resumed', 'استئناف محاولة فحص في جلسة لاحقة',
     'شروط البدء نفسها في الدرس والفهم. المحاولة موجودة، لهذه المهارة، «معلَّقة»، وليست نشطة في هذه الجلسة. '
     'إصدار تعريفاتها متاح. لا تنبيه تاريخ على الجلسة، ويومها يحقق شروط توقيت البدء (3.6). في الجلسة حصة '
     'تعليمية (7.1: ما لم يكتمل يُستأنف في الجلسة التالية)',
     'تصير المحاولة نشطة في هذه الجلسة وتُضاف إلى جلساتها المساهمة، وتُستهلك الحصة التعليمية. إجابات خاناتها '
     'السابقة تبقى',
     'no_session، not_open، suspended، lesson_idle، understanding_first، no_check، check_state، already_active، '
     'version_unavailable، date_unconfirmed، check_same_day، check_needs_practice، quota_teach', 'لا أثر'),
    ('check_held', 'تعليق محاولة فحص للمراجعة',
     'المحاولة موجودة، لهذه المهارة، «معلَّقة»، ونشطة في هذه الجلسة. السبب: انقطاعان في خانة أو 3 في الفحص، '
     'أو نفاد بدائل خانة، أو لا بنود لهذه المحاولة (3.6)',
     'تصير «معلَّقة للمراجعة» بسببها وتظهر للمعلم. لا نتيجة، ولا يُسجَّل خطأ. لا تُستأنف ولا تُقبل نتيجتها، '
     'ولا تُبدأ للمهارة محاولة أخرى حتى يتركها المعلم',
     'no_session، unknown_skill، no_check، check_state، check_idle', 'لا أثر'),
    ('independence_result', 'نتيجة محاولة فحص الاستقلال',
     'شروط البدء نفسها في الدرس والفهم. المحاولة موجودة، لهذه المهارة، «معلَّقة». لا تنبيه تاريخ على الجلسة. '
     'المحاولة نشطة في هذه الجلسة: بدأت فيها أو استؤنفت فيها. يوم الجلسة يحقق شروط توقيت البدء (3.6). إصدار '
     'تعريفاتها متاح',
     'تُغلق المحاولة بنتيجتها. اجتاز: دليل استقلال، وبه مع الفهم الساري تصير المهارة مستوفاة، ويوم هذه الجلسة '
     'مرجع أول فحص احتفاظ',
     'no_session، not_open، suspended، lesson_idle، understanding_first، no_check، check_state، date_unconfirmed، '
     'check_idle، check_same_day، check_needs_practice، version_unavailable', 'المستوفاة تفكّ انتظار توابعها، وتصير متطلبًا مستوفى في دالة الأهلية'),
    ('check_abandoned', 'ترك محاولة فحص',
     'المحاولة «معلَّقة» أو «معلَّقة للمراجعة» أو «تحتاج إعادة بدء». سبب مكتوب',
     'تصير «متروكة» بسبب الترك، وتبقى في السجل ومعها سبب تعليقها إن عُلّقت. بعدها يجوز بدء محاولة جديدة',
     'no_check، check_state', 'لا أثر'),
    ('teacher_open', 'قرار فتح من المعلم',
     'سبب مكتوب. المتجاوَز من متطلباتها المباشرة، وفيه كل متطلب مباشر غير مستوفى',
     'قرار سارٍ على المهارة المسماة وحدها', 'unknown_skill، bad_decision',
     'لا يجعل المهارة متطلبًا مستوفى لما بعدها، ولا ينتقل الإذن'),
    ('teacher_defer', 'تأجيل تدريس بقرار المعلم', 'سبب مكتوب. لا دليل مباشر للمهارات المسماة',
     'قرار سارٍ: تُعرض «مؤجَّلة بقرار المعلم» ما لم تنتظر', 'unknown_skill، bad_decision، not_deferrable',
     'لا يفتح ما بعدها. يبقى لها التحقق القصير'),
    ('teacher_revoke', 'إلغاء قرار', 'القرار سارٍ', 'يصير غير سارٍ ويبقى في التاريخ', 'no_decision',
     'الدرس الذي فقد مسوّغه يُعلَّق'),
    ('recheck_result', 'نتيجة إعادة التحقق',
     'جلسة مفتوحة. لا يمنع المهارة متطلب. وهي متطلب ناقص لدرس معلَّق، أو مهارة أُبطل دليل استيفائها '
     'وصارت بلا دليل مباشر',
     'صحّت: دليل إعادة تحقق، فتعود مجتازة بلا درس. غير ذلك: محاولة، ويبقى طريق البوابة',
     'no_session، unknown_skill، no_recheck، blocked', 'الدرس المعلَّق الذي عاد مسوّغه يُستأنف'),
    ('invalidate_session', 'إبطال جلسة', 'الجلسة موجودة ومختومة ولم تُبطل',
     'أدلة تلك الجلسة وحدها تصير غير صالحة، وبواباتها تخرج من حدّ الدورة الحالية وتبقى في التاريخ. '
     'محاولة فحص أسهمت فيها الجلسة، أي بدأت أو استؤنفت أو أُغلقت فيها: إن لم تكتمل صارت «تحتاج إعادة بدء» فلا '
     'تُستأنف ولا تُقبل نتيجتها؛ وإن اكتملت صارت غير صالحة، فيسقط دليل اجتيازها ولا تُعدّ في توقيت محاولة '
     'لاحقة. البنود المعروضة تبقى في السجل. '
     'الدرس الذي فُتح فيها يبقى مفتوحًا ويعود إلى طور الافتتاح بلا نشاط. قرارات المعلم باقية. مرجع التاريخ لا '
     'يتغير',
     'bad_target',
     'تُشتق الحالات من الأدلة الصالحة الباقية. الدرس المفتوح الذي لم يبقَ له مسوّغ يُعلَّق، '
     'والذي بقي له دليل مستقل أو قرار سارٍ يبقى مفتوحًا'),
    ('retention_result', 'نتيجة فحص احتفاظ',
     'جلسة مفتوحة بلا تنبيه تاريخ. المهارة مستوفاة باجتياز فحص الاستقلال. أُجري لها أقل من 3 فحوص احتفاظ صالحة '
     'بعد دليل استقلالها الساري. يوم الجلسة بلغ الموعد: 7 أيام بعد يوم الاجتياز، ثم 21 يومًا بعد يوم الفحص '
     'السابق الفعلي، ثم 60 (3.7). عدد الصحيح من 0 إلى 5',
     'تُحفظ النتيجة بجولتها ويومها وموعدها ومدتها منذ الاجتياز أو الفحص السابق وبنودها. توصف «احتفاظ»، أو «أداء '
     'مؤجل» إن نشط درس المهارة داخل الفاصل أو أبلغ التطبيق عن تدريب مباشر فيه. أقل من 4 من 5: تُعلَّم «تحتاج '
     'تثبيتًا». ليست دليلًا، ولا تغيّر حالة',
     'no_session، unknown_skill، bad_event، not_met، retention_done، date_unconfirmed، retention_early',
     'لا أثر: لا تُغلق ما فُتح'),
]

def ok(**kw):
    return dict(ok=True, **kw)


def no(code, missing=None):
    return dict(ok=False, code=code, reason=REASONS[code], missing=missing)


# حدث ختام كل نشاط: قاعدة قبوله هي قاعدة استمرار النشاط (may_continue)
CONTINUE = dict(gate='gate_result', short='short_check_result', opening='lesson_opening_result',
                evidence='understanding_proved', check='independence_result', retention='retention_result')


class Engine:
    def __init__(self, net, group='older', regate=True, versions=None):
        self.ids, self.pre = net
        self._items = []                                   # بنود الحدث الجاري، تُحفظ مع دليله
        self.idx = {s: n for n, s in enumerate(self.ids)}
        self.kids = {s: [c for c in self.ids if s in self.pre[c]] for s in self.ids}
        self.anc = {}
        for s in self.ids:                                 # المتطلبات تسبق مهاراتها في الترتيب
            self.anc[s] = set(self.pre[s]).union(*(self.anc[p] for p in self.pre[s]))
        self.versions = None if versions is None else set(versions)   # إصدارات التعريفات المتاحة
        self.s = dict(group=group, regate=regate, seq=0, log=[], applied={}, evidence=[], decisions=[],
                      attempts=[], sessions={}, order=[], current=None, opened={}, queue=[], gates={},
                      checked=[], checks={}, suspended={}, history=[], retention=[], migration=MIGRATION)

    def _has_version(self, v):
        return self.versions is None or v in self.versions

    # ---------------------------------------------------------------- حفظ واستئناف
    def dump(self):
        return json.dumps(self.s, ensure_ascii=False, sort_keys=True)

    @classmethod
    def restore(cls, net, text, content_versions=None):
        """الاستئناف من النص المحفوظ. محاولة فحص معلَّقة لا يتاح إصدار تعريفاتها تصير «تحتاج إعادة بدء»،
        ولا تُقبل نتيجتها بعد ذلك. تُترك بحدث صريح ثم تُبدأ محاولة جديدة."""
        st = json.loads(text)
        e = cls(net, st['group'], st['regate'], content_versions)
        e.s = st
        st.setdefault('retention', [])                     # حالة حُفظت قبل إضافة فحوص الاحتفاظ
        if st.get('migration', 0) < MIGRATION:
            e._migrate_checks()
            st['migration'] = MIGRATION
        for cid, c in st['checks'].items():
            if c['state'] == 'pending' and not e._has_version(c['content_version']):
                c['state'] = 'needs_restart'
                st['history'].append(dict(seq=st['seq'], what='check_needs_restart', check=cid))
        return e

    def _migrate_checks(self):
        """ترحيل حالة نسختها أقل من MIGRATION (المراجعتان 11 و12). وجود قائمة الجلسات المساهمة لا يثبت شيئًا: تُستكمل
        القائمة من أحداث السجل، البدء وكل استئناف، ومن حقول المحاولة، مرتبةً بترتيب الجلسات. ثم يُطبَّق أثر كل جلسة
        مساهمة أُبطلت كما لو وقع الإبطال بالمحرك الجديد، والأثر لا يتكرر على محاولة طُبّق عليها. وإن خلا السجل من بدء
        المحاولة لم تُعرف جلساتها الوسطى، فالإجراء التحفظي: جلسة مبطلة في مداها، من جلسة البدء إلى الختم أو آخر جلسة،
        تُعامل كأنها مساهمة، بسبب migration_unverified."""
        st, hit = self.s, False
        pos = {x: n for n, x in enumerate(st['order'])}
        for cid, c in st['checks'].items():
            logged = [ev['session'] for ev in st['log'] if ev['type'] in ('check_started', 'check_resumed')
                      and ev.get('check_id') == cid]
            known = any(ev['type'] == 'check_started' and ev.get('check_id') == cid for ev in st['log'])
            have = set(c.get('sessions', [])) | set(logged) | {x for x in (
                c['session'], c.get('active'), c.get('held_session'), c.get('closed_session')) if x}
            c['sessions'] = sorted(have, key=pos.get)
            bad, reason = [x for x in c['sessions'] if st['sessions'][x]['invalid']], 'session_invalidated'
            if not bad and not known:
                a = pos[c['session']]
                b = pos[c['closed_session']] if c.get('closed_session') else len(st['order']) - 1
                bad, reason = [x for x in st['order'][a:b + 1] if st['sessions'][x]['invalid']], 'migration_unverified'
            if bad:                                         # أقدم إبطال أولًا: هو الذي يحدد أسبق الختمَ أم لا
                first = min(bad, key=lambda x: (self._invalidated_at(x) is None, self._invalidated_at(x) or 0))
                hit = self._taint_check(cid, first, reason, migrated=True) or hit
        if hit:
            self._reconcile()

    def _invalidated_at(self, session):
        return next((h['seq'] for h in self.s['history'] if h['what'] == 'session_invalidated'
                     and h['session'] == session), None)

    def _taint_check(self, cid, session, reason, migrated=False):
        """أثر إبطال جلسة أسهمت في محاولة فحص. غير المكتملة تحتاج إعادة بدء. والمكتملة يسقط دليلها، وإن كان
        الإبطال قبل ختمها (حالة قديمة قبِل محركها النتيجة بعده) فحكمها حكم غير المكتملة، كما في إعادة تشغيل سجلها."""
        c = self.s['checks'][cid]
        extra = dict(reason=reason, migrated=True) if migrated else {}
        when = self._invalidated_at(session)
        reopen = (migrated and c['state'] == 'closed' and not c.get('invalid') and when is not None
                  and when < c['closed_seq'])
        if c['state'] == 'closed' and not c.get('invalid') and not reopen:
            c['invalid'] = True                             # اكتملت: يسقط دليلها، وتبقى بنودها في السجل
            self._drop_check_evidence(cid)
            self.s['history'].append(dict(seq=self.s['seq'], what='check_invalidated', check=cid, session=session,
                                          **extra))
            return True
        if c['state'] in ('pending', 'held') or reopen:  # لم تكتمل: لا تُستأنف ولا تُقبل نتيجتها
            if reopen:
                c['migrated_result'] = c.pop('result')
                c.pop('closed_session'), c.pop('closed_seq')
                self._drop_check_evidence(cid)
            c['restart_reason'], c['state'] = reason, 'needs_restart'
            self.s['history'].append(dict(seq=self.s['seq'], what='check_needs_restart', check=cid, session=session,
                                          **extra))
            return True
        return False                                        # طُبّق الأثر من قبل، أو المحاولة متروكة

    def _drop_check_evidence(self, cid):
        for e in self.s['evidence']:
            if e.get('check') == cid and e['valid']:
                e['valid'] = False

    @classmethod
    def replay(cls, net, log, group='older', regate=True, versions=None):
        e = cls(net, group, regate, versions)
        for ev in log:
            e.apply(ev)
        return e

    # ---------------------------------------------------------------- الاشتقاق
    def _add(self, skill, kind, source, session, **extra):
        """يُحفظ كل دليل ببنوده وتاريخه (3.5): البنود من حقل items في الحدث، والتاريخ يوم جلسته."""
        self.s['evidence'].append(dict(id='E%d' % (len(self.s['evidence']) + 1), skill=skill, kind=kind,
                                       source=source, session=session, seq=self.s['seq'], valid=True,
                                       items=list(self._items), **extra))

    def _attempt(self, **kw):
        self.s['attempts'].append(dict(seq=self.s['seq'], items=list(self._items), **kw))

    def valid_evidence(self, skill=None, kind=None):
        return [e for e in self.s['evidence'] if e['valid'] and (skill is None or e['skill'] == skill)
                and (kind is None or e['kind'] == kind)]

    def decisions(self, kind, skill=None):
        return [d for d in self.s['decisions'] if d['standing'] and d['kind'] == kind
                and (skill is None or skill in d['skills'])]

    def progress(self, skill):
        """الحالة المباشرة، والفهم الساري، والاستقلال الساري: من تسلسل واحد للأدلة الصالحة.
        التعثّر يُسقط ما سبقه من فهم واستقلال، فلا يكفي دليل فهم تاريخي سبق آخر تعثّر."""
        return self._fold(self.valid_evidence(skill))

    @staticmethod
    def _fold(evidence):
        status, und, ind = None, False, False
        for e in evidence:
            if e['kind'] in (EXEMPT, RECHECK):
                status = 'exempt'
            elif e['kind'] == STUMBLE:
                status, und, ind = 'stumbled', False, False
            elif e['kind'] == UNDERSTOOD:
                und = True
            elif e['kind'] == INDEPENDENT:
                ind = True
            if und and ind:
                status = 'met'
        return status, und, ind

    def direct(self, skill):
        return self.progress(skill)[0]

    def derive(self):
        """حالة كل مهارة. لا تُخزَّن: تُحسب من الأدلة الصالحة وقرارات المعلم السارية."""
        by = {}
        for e in self.s['evidence']:                       # تمريرة واحدة على الأدلة الصالحة
            if e['valid']:
                by.setdefault(e['skill'], []).append(e)
        direct = {s: self._fold(by.get(s, ()))[0] for s in self.ids}
        deferred = set()
        for s in self.ids:
            if direct[s] == 'exempt' and any(e['kind'] == EXEMPT for e in by.get(s, ())):
                deferred |= self.anc[s]                    # أسلاف مهارة اجتازت بوابتها
        for d in self.decisions('defer'):
            deferred |= set(d['skills'])
        st = {}
        for s in self.ids:
            if direct[s]:
                st[s] = direct[s]
            elif any(st[p] in BLOCKING for p in self.pre[s]):
                st[s] = 'waiting'                          # طلب الدعم ليس دليلًا ولا يستثني
            elif s in deferred:
                st[s] = 'deferred'
            else:
                st[s] = None
        return st

    def blockers(self, skill, st=None):
        st, out, stack = st or self.derive(), set(), list(self.pre[skill])
        while stack:
            p = stack.pop()
            if st[p] == 'stumbled':
                out.add(p)
            elif st[p] == 'waiting':
                stack.extend(self.pre[p])
        return sorted(out, key=self.idx.get)

    def eligible(self, skill, mode='follow', st=None):
        """دالة الأهلية الواحدة لفتح درس (3.4)."""
        st = st or self.derive()
        bypass = set()
        for d in self.decisions('open', skill):
            bypass |= set(d['bypass'])
        for p in sorted(self.pre[skill], key=self.idx.get):
            if p in bypass or st[p] in SATISFIED:
                continue
            if st[p] in BLOCKING:
                return no('prerequisite', p)
            if mode == 'start' and self.valid_evidence(p, SHORT_OK):
                continue                                   # استثناء جلسة البدء وحدها
            return no('prerequisite', p)
        return ok()

    def _reconcile(self):
        """بعد كل حدث مقبول: الدرس المفتوح الذي فقد مسوّغه يُعلَّق، والذي عاد مسوّغه يُستأنف."""
        st = self.derive()
        for skill, o in self.s['opened'].items():
            if st[skill] in SATISFIED:
                self.s['suspended'].pop(skill, None)
                continue
            e = self.eligible(skill, o['mode'], st)
            was = skill in self.s['suspended']
            if not e['ok'] and not was:
                self.s['suspended'][skill] = dict(missing=e['missing'], seq=self.s['seq'])
                self.s['history'].append(dict(seq=self.s['seq'], what='access_suspended', skill=skill,
                                              missing=e['missing']))
            elif not e['ok']:
                self.s['suspended'][skill]['missing'] = e['missing']
            elif was:
                del self.s['suspended'][skill]
                self.s['history'].append(dict(seq=self.s['seq'], what='access_resumed', skill=skill))

    # ---------------------------------------------------------------- التطبيق
    def _schema(self, ev):
        if not isinstance(ev, dict):
            return dict(no('bad_event'), field=None)
        if not _fits(ev.get('id'), str):
            return dict(no('bad_event'), field='id')
        spec = SCHEMA.get(ev.get('type')) if isinstance(ev.get('type'), str) else None
        if spec is None:
            return dict(no('bad_event'), field='type')
        names = set()
        for f, rule in spec.items():
            name = f.rstrip('?')
            names.add(name)
            if name not in ev:
                if f.endswith('?'):
                    continue
                return dict(no('bad_event'), field=name)
            if not _fits(ev[name], rule):
                return dict(no('bad_event'), field=name)
        extra = sorted(set(ev) - names - {'id', 'type'})
        return dict(no('bad_event'), field=extra[0]) if extra else None

    def preflight(self, ev):
        """هل يُقبل الحدث الآن؟ لا يكتب شيئًا ولا يحجز معرّفه. تسأله طبقة البنود والمجدول قبل عرض أول بند،
        فيُرفض الطلب غير المؤهل قبل أن يرى الطفل شيئًا. apply يعيد الفحص نفسه عند الإرسال."""
        bad = self._schema(ev)
        if bad:
            return bad
        ev = copy.deepcopy(ev)
        seen = self.s['applied'].get(ev['id'])
        if seen:
            if seen['key'] != json.dumps(ev, ensure_ascii=False, sort_keys=True):
                return no('event_id_conflict')
            return dict(copy.deepcopy(seen['result']), duplicate=True)
        return getattr(self, 'can_' + ev['type'])(ev)

    def apply(self, ev):
        """المدخل الوحيد. مخطط، ثم هوية، ثم شروط القبول، ثم تنفيذ ذرّي على نسخة مستقلة من الحدث."""
        bad = self._schema(ev)
        if bad:
            return bad
        ev = copy.deepcopy(ev)                              # لا يبقى مرجع إلى كائن المرسِل
        key = json.dumps(ev, ensure_ascii=False, sort_keys=True)
        seen = self.s['applied'].get(ev['id'])
        if seen:
            if seen['key'] != key:
                return no('event_id_conflict')
            return dict(copy.deepcopy(seen['result']), duplicate=True)
        verdict = getattr(self, 'can_' + ev['type'])(ev)
        if not verdict['ok']:
            return verdict                                  # لم يُكتب شيء
        before = self.derive()
        snapshot = pickle.dumps(self.s, pickle.HIGHEST_PROTOCOL)   # لقطة كاملة، أسرع من النسخ العميق
        try:
            self.s['seq'] += 1
            self._items = ev.get('items', [])
            getattr(self, 'do_' + ev['type'])(ev)
            self.s['log'].append(ev)
            self._reconcile()
            after = self.derive()
            res = ok(seq=self.s['seq'],
                     changed={s: [before[s], after[s]] for s in self.ids if before[s] != after[s]},
                     suspended=sorted(self.s['suspended'], key=self.idx.get))
            self.s['applied'][ev['id']] = dict(key=key, result=res)
        except Exception as err:                            # ذرّية: تعود الحالة كما كانت قبل الطلب
            self.s = pickle.loads(snapshot)
            return dict(no('internal_error'), detail=repr(err))
        return copy.deepcopy(res)                           # ولا مرجع إلى النتيجة المحفوظة

    # ---------------------------------------------------------------- فحوص مشتركة
    def _session(self, ev):
        cur = self.s['current']
        if cur is None or cur != ev.get('session'):
            return None
        return self.s['sessions'][cur]

    def _need(self, ev, quota=None, skill=True):
        if skill and ev.get('skill') not in self.idx:
            return no('unknown_skill')
        ses = self._session(ev)
        if ses is None:
            return no('no_session')
        if quota:
            limit = QUOTA[ses['kind']][quota]
            if isinstance(limit, dict):
                limit = limit[self.s['group']]
            if ses[quota] >= limit:
                return no('quota_' + quota)
        return None

    def _blocked(self, skill, st):
        for p in sorted(self.pre[skill], key=self.idx.get):
            if st[p] in BLOCKING:
                return no('blocked', p)
        return None

    def _lesson(self, ev, phases, active=True):
        """نشاط على درس: مفتوح، غير معلَّق، لا ينتظر حصة، ونشط في هذه الجلسة إن كان النشاط تعليميًا."""
        bad = self._need(ev)
        if bad:
            return bad
        o = self.s['opened'].get(ev['skill'])
        if not o or o['phase'] not in phases + ('due',):
            return no('not_open')
        if ev['skill'] in self.s['suspended']:
            return no('suspended', self.s['suspended'][ev['skill']]['missing'])
        if o['phase'] == 'due' or (active and o['active'] != ev['session']):
            return no('lesson_idle')
        return None

    # ---------------------------------------------------------------- الجلسات
    def can_session_start(self, ev):
        if ev['day'] < 0:
            return dict(no('bad_event'), field='day')
        if self.s['current'] is not None:
            return no('session_open')
        kinds = [self.s['sessions'][x]['kind'] for x in self.s['order']]
        k = ev['kind']
        fine = ((k == 'search' and 'start' not in kinds and kinds.count('search') < SEARCH_CAP)
                or (k == 'start' and 'start' not in kinds) or (k == 'follow' and 'start' in kinds))
        return ok() if fine and ev['session'] not in self.s['sessions'] else no('session_order')

    def date_reference(self):
        """مرجع التاريخ (9.1): يوم آخر جلسة، بترتيب الجلسات، تاريخها موثوق، أي لم تُعلَّم بتنبيه أو أكّد الوالد
        تاريخها. التاريخ المعلَّم غير المؤكد لا يصير مرجعًا. الجلسة المبطلة تبقى مرجعًا: الإبطال يخص الطفل لا الساعة."""
        for x in reversed(self.s['order']):
            if not self.s['sessions'][x]['clock']:
                return self.s['sessions'][x]['day']
        return None

    def do_session_start(self, ev):
        last = self.date_reference()
        flag = last is not None and (ev['day'] < last or ev['day'] > last + 30)
        self.s['sessions'][ev['session']] = dict(kind=ev['kind'], day=ev['day'], clock=flag, gate=0, short=0,
                                                 teach=0, ended=False, invalid=False)
        self.s['order'].append(ev['session'])
        self.s['current'] = ev['session']
        if flag:                                            # 9.1: يُحفظ بتنبيه، ولا يُحذف
            self.s['history'].append(dict(seq=self.s['seq'], what='clock_flag', session=ev['session'],
                                          day=ev['day'], last_day=last))

    def can_date_confirmed(self, ev):
        t = self.s['sessions'].get(ev['target'])
        return ok() if t and t['clock'] else no('not_flagged')

    def do_date_confirmed(self, ev):
        self.s['sessions'][ev['target']]['clock'] = False
        self.s['history'].append(dict(seq=self.s['seq'], what='date_confirmed', session=ev['target']))

    def can_session_end(self, ev):
        return ok() if self._session(ev) else no('no_session')

    def do_session_end(self, ev):
        self.s['sessions'][ev['session']]['ended'] = True
        self.s['current'] = None

    # ---------------------------------------------------------------- البوابة والتحقق القصير
    def valid_gates(self, skill):
        """بوابات المهارة في دورة التحقق الحالية: ما وقع في جلسات غير مبطلة. التاريخ كله في attempts."""
        return sum(1 for a in self.s['attempts'] if a['skill'] == skill and a['what'] == 'gate'
                   and a['result'] != 'interrupted' and not self.s['sessions'][a['session']]['invalid'])

    def can_gate_result(self, ev):
        bad = self._need(ev, 'gate')
        if bad:
            return bad
        skill, st = ev['skill'], self.derive()
        bad = self._blocked(skill, st)
        if bad:
            return bad
        if st[skill] in SATISFIED:
            return no('already_satisfied')
        n = self.valid_gates(skill)
        if n >= 2:
            return no('gate_limit')
        o = self.s['opened'].get(skill)
        if n == 1 or o:
            # بوابة بعد فتح الدرس: بعد اختصاره، وفي جلسة لاحقة، والإعادة لمتعثَّر فيها تحتاج السماح
            if not o or o['phase'] != 'skipped' or o['session'] == ev['session']:
                return no('regate_not_allowed')
            if st[skill] == 'stumbled' and not self.s['regate']:
                return no('regate_not_allowed')
        return ok()

    def do_gate_result(self, ev):
        skill, res, ses = ev['skill'], ev['result'], self.s['sessions'][ev['session']]
        self._attempt(skill=skill, what='gate', result=res, session=ev['session'])
        if res == 'interrupted':
            return                                          # بلا نتيجة، ولا تُعدّ بوابة
        ses['gate'] += 1
        self.s['gates'][skill] = self.s['gates'].get(skill, 0) + 1     # العدد التاريخي
        if skill in self.s['queue']:
            self.s['queue'].remove(skill)
        if res == 'pass':
            self._add(skill, EXEMPT, 'gate', ev['session'])
        elif res == 'fail':
            errs = ev.get('errors', [])
            calc = any(t in ('ف3', 'ف4') for t in errs)
            self._add(skill, STUMBLE, 'gate', ev['session'],
                      treatment='regular' if calc or not ev.get('has_calc', True) else 'structure')
        o = self.s['opened'].get(skill)
        if o and res in ('fail', 'help'):                   # يمضي الدرس كاملًا. طلب الدعم بلا دليل
            if ses['teach'] < QUOTA[ses['kind']]['teach']:
                ses['teach'] += 1
                o['phase'], o['active'] = 'full', ev['session']
                o['taught'].append(ev['session'])
            else:
                o['phase'] = 'due'                          # ينتظر حصة: يُستأنف بحدث resume_lesson

    def can_short_check_result(self, ev):
        bad = self._need(ev, 'short')
        if bad:
            return bad
        skill, st = ev['skill'], self.derive()
        bad = self._blocked(skill, st)
        if bad:
            return bad
        if st[skill] not in (None, 'deferred') or skill in self.s['checked']:
            return no('not_checkable')
        return ok()

    def do_short_check_result(self, ev):
        self.s['sessions'][ev['session']]['short'] += 1
        self.s['checked'].append(ev['skill'])
        if ev['ok']:
            self._add(ev['skill'], SHORT_OK, 'short', ev['session'])
        elif ev['skill'] not in self.s['queue']:
            self.s['queue'].append(ev['skill'])

    # ---------------------------------------------------------------- الدرس
    def can_open_lesson(self, ev):
        bad = self._need(ev, 'teach')
        if bad:
            return bad
        skill, st = ev['skill'], self.derive()
        if skill in self.s['suspended']:
            return no('suspended', self.s['suspended'][skill]['missing'])
        if skill in self.s['opened']:
            return no('already_open')
        if st[skill] in SATISFIED:
            return no('already_satisfied')
        return self.eligible(skill, self.s['sessions'][ev['session']]['kind'], st)

    def do_open_lesson(self, ev):
        ses = self.s['sessions'][ev['session']]
        ses['teach'] += 1
        self.s['opened'][ev['skill']] = dict(session=ev['session'], mode=ses['kind'], phase='opening',
                                             active=ev['session'], taught=[ev['session']])

    def can_resume_lesson(self, ev):
        bad = self._need(ev, 'teach')
        if bad:
            return bad
        skill = ev['skill']
        o = self.s['opened'].get(skill)
        if not o or o['phase'] not in ('opening', 'full', 'due'):
            return no('not_open')
        if skill in self.s['suspended']:
            return no('suspended', self.s['suspended'][skill]['missing'])
        if o['phase'] != 'due' and o['active'] == ev['session']:
            return no('already_active')
        return self.eligible(skill, o['mode'])

    def do_resume_lesson(self, ev):
        o = self.s['opened'][ev['skill']]
        self.s['sessions'][ev['session']]['teach'] += 1
        if o['phase'] == 'due':
            o['phase'] = 'full'
        o['active'] = ev['session']
        o['taught'].append(ev['session'])

    def may_continue(self, kind, session, skill, check_id=None):
        """هل يستمر نشاط جارٍ في هذه الجلسة؟ يسأله المجدول قبل عرض كل بند وقبل تطبيق كل إجابة (المراجعة 16)، فقرار
        يقع أثناء النشاط، كإبطال جلسة أو ترك محاولة، يوقفه قبل أن يُعرض بند أو تُحتسب إجابة. لا يكتب شيئًا ولا يستهلك
        حصة. القاعدة هي قاعدة قبول حدث ختام النشاط نفسها، وهي لا تقرأ نتيجته: فالحكم واحد مهما كانت الإجابة المقبلة
        (تفحصه الحالة 13 في tests/test_phase0). وبنود الدرس والتدريب (show) لا حدث لها، فشرطها شرط الدرس النشط في الجلسة."""
        ev = dict(session=session, skill=skill, check_id=check_id, correct=0)
        if kind == 'show':
            return self._lesson(ev, ('opening', 'skipped', 'full')) or ok()
        return getattr(self, 'can_' + CONTINUE[kind])(ev)

    def can_lesson_opening_result(self, ev):
        return self._lesson(ev, ('opening',)) or ok()

    def do_lesson_opening_result(self, ev):
        skill, o = ev['skill'], self.s['opened'][ev['skill']]
        if ev['outcome'] == 'skip':
            o['phase'] = 'skipped'                          # قاعدة الاختصار لا تتغير بخيار الإعادة
            stumbled = self.direct(skill) == 'stumbled'
            if (self.s['regate'] or not stumbled) and skill not in self.s['queue']:
                self.s['queue'].append(skill)
            return
        o['phase'] = 'full'
        if ev['outcome'] == 'full_error':
            # المعالجة تحددها البوابة (6.1): خطأ البنود الموجَّهة يُبقي معالجة آخر تعثّر صالح، والمسار العادي إن لم يكن
            prev = [x for x in self.valid_evidence(skill, STUMBLE) if x.get('treatment')]
            self._add(skill, STUMBLE, 'lesson', ev['session'],
                      treatment=prev[-1]['treatment'] if prev else 'regular')
        else:
            self._attempt(skill=skill, what='lesson', result='help', session=ev['session'])

    def can_understanding_proved(self, ev):
        return self._lesson(ev, ('opening', 'full')) or ok()

    def do_understanding_proved(self, ev):
        self._add(ev['skill'], UNDERSTOOD, 'lesson', ev['session'])

    # ---------------------------------------------------------------- محاولات فحص الاستقلال
    def _check_ready(self, ev):
        """درس مفتوح غير معلَّق ولا ينتظر حصة، وفهم سارٍ من التسلسل نفسه الذي يحسب حالة المهارة."""
        bad = self._lesson(ev, ('opening', 'skipped', 'full'), active=False)
        if bad:
            return bad
        return None if self.progress(ev['skill'])[1] else no('understanding_first')

    def can_check_started(self, ev):
        bad = self._check_ready(ev)
        if bad:
            return bad
        skill, ses = ev['skill'], self.s['sessions'][ev['session']]
        if self.direct(skill) in SATISFIED:
            return no('already_satisfied')
        if ev['check_id'] in self.s['checks']:
            return no('check_state')
        if any(c['skill'] == skill and c['state'] in OPEN_CHECK for c in self.s['checks'].values()):
            return no('check_pending')
        if not self._has_version(ev['content_version']):
            return no('version_unavailable')
        if ses['clock']:
            return no('date_unconfirmed')
        bad = self._check_timing(skill, ses['day'])
        if bad:
            return bad
        return ok() if ses['teach'] < QUOTA[ses['kind']]['teach'] else no('quota_teach')

    def _check_timing(self, skill, day):
        """3.6: في يوم بعد يوم الدرس، والإعادة في يوم لاحق، وبعد الإخفاق جلسة تدريب. الأيام أيام الأسرة.
        تُطبَّق على البدء والاستئناف والنتيجة، فلا يُعتمد دليل في يوم يناقض أدلته السابقة. المحاولة المكتملة التي
        أُبطلت جلسة أسهمت فيها لا تُعدّ."""
        und = self.valid_evidence(skill, UNDERSTOOD)
        if und and day <= self.s['sessions'][und[-1]['session']]['day']:
            return no('check_same_day')
        closed = [c for c in self.s['checks'].values() if c['skill'] == skill and c['state'] == 'closed'
                  and not c.get('invalid')]
        if closed:
            last = max(closed, key=lambda c: c['closed_seq'])
            if day <= self.s['sessions'][last['closed_session']]['day']:
                return no('check_same_day')
            if last['result'] == 'fail':
                at = self.s['order'].index(last['closed_session'])
                if not any(self.s['order'].index(x) > at for x in self.s['opened'][skill]['taught']):
                    return no('check_needs_practice')
        return None

    def do_check_started(self, ev):
        self.s['sessions'][ev['session']]['teach'] += 1
        self.s['checks'][ev['check_id']] = dict(skill=ev['skill'], content_version=ev['content_version'],
                                                session=ev['session'], active=ev['session'], state='pending',
                                                seq=self.s['seq'], sessions=[ev['session']])

    def _own_check(self, ev):
        c = self.s['checks'].get(ev['check_id'])
        return c if c and c['skill'] == ev['skill'] else None

    def can_check_resumed(self, ev):
        bad = self._check_ready(ev)
        if bad:
            return bad
        c = self._own_check(ev)
        if not c:
            return no('no_check')
        if c['state'] != 'pending':
            return no('check_state')
        if c['active'] == ev['session']:
            return no('already_active')
        if not self._has_version(c['content_version']):
            return no('version_unavailable')
        ses = self.s['sessions'][ev['session']]
        if ses['clock']:                                    # 9.1: لا يُعتمد عمل فحص في يوم غير مؤكد
            return no('date_unconfirmed')
        bad = self._check_timing(ev['skill'], ses['day'])
        if bad:
            return bad
        return ok() if ses['teach'] < QUOTA[ses['kind']]['teach'] else no('quota_teach')

    def do_check_resumed(self, ev):
        self.s['sessions'][ev['session']]['teach'] += 1
        c = self.s['checks'][ev['check_id']]
        c['active'] = ev['session']
        if ev['session'] not in c['sessions']:              # كل جلسة عُرضت فيها بنود المحاولة
            c['sessions'].append(ev['session'])

    def can_check_held(self, ev):
        bad = self._need(ev)
        if bad:
            return bad
        c = self._own_check(ev)
        if not c:
            return no('no_check')
        if c['state'] != 'pending':
            return no('check_state')
        return ok() if c['active'] == ev['session'] else no('check_idle')

    def do_check_held(self, ev):
        c = self.s['checks'][ev['check_id']]
        c['state'], c['hold_reason'], c['held_session'] = 'held', ev['reason'], ev['session']   # يبقى بعد الترك
        c['held_items'] = list(ev.get('items', []))     # ما عُرض قبل التعليق، ليراجعه المعلم

    def can_check_abandoned(self, ev):
        c = self.s['checks'].get(ev['check_id'])
        if not c:
            return no('no_check')
        return ok() if c['state'] in OPEN_CHECK else no('check_state')

    def do_check_abandoned(self, ev):
        c = self.s['checks'][ev['check_id']]
        c['state'], c['reason'] = 'abandoned', ev['reason']

    def can_independence_result(self, ev):
        bad = self._check_ready(ev)
        if bad:
            return bad
        c = self.s['checks'].get(ev['check_id'])
        if not c or c['skill'] != ev['skill']:
            return no('no_check')
        if c['state'] != 'pending':
            return no('check_state')
        ses = self.s['sessions'][ev['session']]
        if ses['clock']:
            return no('date_unconfirmed')
        if c['active'] != ev['session']:
            return no('check_idle')
        bad = self._check_timing(ev['skill'], ses['day'])
        if bad:
            return bad
        return ok() if self._has_version(c['content_version']) else no('version_unavailable')

    def do_independence_result(self, ev):
        c = self.s['checks'][ev['check_id']]
        c['state'], c['result'] = 'closed', ev['result']
        c['closed_session'], c['closed_seq'] = ev['session'], self.s['seq']
        self._attempt(skill=ev['skill'], what='independence', result=ev['result'], session=ev['session'],
                      check=ev['check_id'])
        if ev['result'] == 'pass':
            self._add(ev['skill'], INDEPENDENT, 'check', ev['session'], check=ev['check_id'])

    # ---------------------------------------------------------------- قرارات المعلم
    def can_teacher_open(self, ev):
        skill = ev['skill']
        if skill not in self.idx:
            return no('unknown_skill')
        st, by = self.derive(), set(ev.get('bypass', []))
        if not ev.get('reason') or not by <= set(self.pre[skill]):
            return no('bad_decision')
        for p in sorted(self.pre[skill], key=self.idx.get):
            if st[p] not in SATISFIED and p not in by:
                return no('bad_decision', p)
        return ok()

    def do_teacher_open(self, ev):
        self.s['decisions'].append(dict(id=ev['id'], kind='open', skills=[ev['skill']], standing=True,
                                        bypass=sorted(ev.get('bypass', [])), reason=ev['reason'],
                                        seq=self.s['seq']))

    def can_teacher_defer(self, ev):
        if not ev.get('skills') or any(x not in self.idx for x in ev['skills']):
            return no('unknown_skill')
        if not ev.get('reason'):
            return no('bad_decision')
        for x in ev['skills']:
            if self.direct(x):
                return no('not_deferrable', x)
        return ok()

    def do_teacher_defer(self, ev):
        self.s['decisions'].append(dict(id=ev['id'], kind='defer', skills=list(ev['skills']), standing=True,
                                        reason=ev['reason'], seq=self.s['seq']))

    def can_teacher_revoke(self, ev):
        return ok() if any(d['id'] == ev['decision'] and d['standing'] for d in self.s['decisions']) \
            else no('no_decision')

    def do_teacher_revoke(self, ev):
        for d in self.s['decisions']:
            if d['id'] == ev['decision']:
                d['standing'] = False

    # ---------------------------------------------------------------- إعادة التحقق والإبطال
    def _rebuildable(self, skill):
        """دليل استيفاء أُبطل والمهارة بلا دليل مباشر الآن: دورة تحققها تُعاد بلا إلزام بدرس."""
        return self.direct(skill) is None and any(
            not e['valid'] and e['skill'] == skill and e['kind'] in (EXEMPT, RECHECK, INDEPENDENT)
            for e in self.s['evidence'])

    def can_recheck_result(self, ev):
        bad = self._need(ev)
        if bad:
            return bad
        waited = any(v['missing'] == ev['skill'] for v in self.s['suspended'].values())
        if not waited and not self._rebuildable(ev['skill']):
            return no('no_recheck')
        return self._blocked(ev['skill'], self.derive()) or ok()

    def do_recheck_result(self, ev):
        self._attempt(skill=ev['skill'], what='recheck', result='pass' if ev['ok'] else 'fail',
                      session=ev['session'])
        if ev['ok']:
            self._add(ev['skill'], RECHECK, 'recheck', ev['session'])

    def can_invalidate_session(self, ev):
        t = self.s['sessions'].get(ev['target'])
        return ok() if t and t['ended'] and not t['invalid'] else no('bad_target')

    def do_invalidate_session(self, ev):
        self.s['sessions'][ev['target']]['invalid'] = True
        hit = []
        for e in self.s['evidence']:
            if e['session'] == ev['target'] and e['valid']:
                e['valid'] = False                          # الدليل يبقى في السجل، غير صالح
                hit.append(e['id'])
        self.s['history'].append(dict(seq=self.s['seq'], what='session_invalidated', session=ev['target'],
                                      evidence=hit))
        for cid, c in self.s['checks'].items():            # محاولة فحص أسهمت فيها الجلسة
            if ev['target'] in c['sessions']:
                self._taint_check(cid, ev['target'], 'session_invalidated')
        for r in self.s['retention']:                       # فحص الاحتفاظ في الجلسة المبطلة لا يُعدّ، ويبقى في السجل
            if r['session'] == ev['target'] and r['valid']:
                r['valid'] = False
                self.s['history'].append(dict(seq=self.s['seq'], what='retention_invalidated', retention=r['id']))
        for skill, o in self.s['opened'].items():           # الدرس المفتوح فيها: يبقى، ويعود إلى الافتتاح
            if o['session'] == ev['target'] and o['phase'] != 'opening':
                self.s['history'].append(dict(seq=self.s['seq'], what='opening_reset', skill=skill,
                                              phase=o['phase']))
                o['phase'], o['active'] = 'opening', None
                if skill in self.s['queue']:
                    self.s['queue'].remove(skill)

    # ---------------------------------------------------------------- فحوص الاحتفاظ (3.7)
    def retention_next(self, skill):
        """فحص الاحتفاظ التالي للمهارة: (الجولة، يوم الموعد، يوم المرجع، جلسة المرجع)، أو None."""
        if self.direct(skill) != 'met':
            return None
        ind = self.valid_evidence(skill, INDEPENDENT)[-1]
        done = [r for r in self.s['retention'] if r['skill'] == skill and r['valid'] and r['seq'] > ind['seq']]
        if len(done) >= len(RETENTION_GAPS):
            return None
        ref = (done[-1] if done else ind)['session']
        day = self.s['sessions'][ref]['day']
        return len(done) + 1, day + RETENTION_GAPS[len(done)], day, ref

    def retention_due(self, day):
        """ما استحق من فحوص الاحتفاظ حتى هذا اليوم، الأقدم استحقاقًا أولًا (3.7)."""
        out = []
        for s in self.ids:
            nxt = self.retention_next(s)
            if nxt and nxt[1] <= day:
                out.append((s, nxt[0], nxt[1]))
        return sorted(out, key=lambda x: (x[2], self.idx[x[0]]))

    def retention_pending(self):
        return [s for s in self.ids if self.retention_next(s)]

    def can_retention_result(self, ev):
        bad = self._need(ev)
        if bad:
            return bad
        if not 0 <= ev['correct'] <= RETENTION_ITEMS:
            return dict(no('bad_event'), field='correct')
        if self.direct(ev['skill']) != 'met':
            return no('not_met')
        nxt = self.retention_next(ev['skill'])
        if nxt is None:
            return no('retention_done')
        ses = self.s['sessions'][ev['session']]
        if ses['clock']:
            return no('date_unconfirmed')
        return ok() if ses['day'] >= nxt[1] else no('retention_early')

    def do_retention_result(self, ev):
        skill = ev['skill']
        rnd, due, ref_day, ref = self.retention_next(skill)
        day, at = self.s['sessions'][ev['session']]['day'], self.s['order'].index(ref)
        o = self.s['opened'].get(skill)
        practised = ev.get('exposed', False) or bool(o and any(self.s['order'].index(x) > at for x in o['taught']))
        low = ev['correct'] < RETENTION_OK
        self.s['retention'].append(dict(
            id='R%d' % (len(self.s['retention']) + 1), skill=skill, round=rnd, session=ev['session'], day=day,
            due_day=due, days_since=day - ref_day, correct=ev['correct'], of=RETENTION_ITEMS,
            label='deferred_performance' if practised else 'retention', consolidate=low, valid=True,
            seq=self.s['seq'], items=list(self._items)))
        if low:                                             # 3.7: تثبيت قصير، ولا يُغلق ما فُتح
            self.s['history'].append(dict(seq=self.s['seq'], what='retention_consolidate', skill=skill, round=rnd))


def check_table():
    """يُستدعى قبل طباعة الجدول: لكل حدث فيه مخطط ودالتا فحص وتنفيذ، ولا حدث في المخطط خارجه، وكل رمز رفض
    في الجدول أو في الكود معرَّف في REASONS."""
    import inspect
    names = [t[0] for t in TABLE]
    assert len(names) == len(set(names)) and set(names) == set(SCHEMA), 'الجدول والمخطط لا يتطابقان'
    for name in names:
        assert hasattr(Engine, 'can_' + name) and hasattr(Engine, 'do_' + name), name
    listed = {c for t in TABLE for c in t[4].split('، ')}
    used = set(re.findall(r"no\('([a-z_]+)'", inspect.getsource(sys.modules[__name__]))) - {'quota_'}
    missing = (listed | used) - set(REASONS)
    assert not missing, missing


def table_markdown():
    check_table()
    out = ['| الحدث | شروط قبوله | التغيير الناتج | رموز الرفض | أثره على المهارات التابعة |',
           '| --- | --- | --- | --- | --- |']
    for name, title, cond, change, rej, dep in TABLE:
        codes = '، '.join('`%s`' % c for c in rej.split('، '))
        out.append('| %s `%s` | %s | %s | %s | %s |' % (title, name, cond, change, codes, dep))
    out += ['', '| رمز الرفض | معناه |', '| --- | --- |']
    out += ['| `%s` | %s |' % kv for kv in REASONS.items()]
    return '\n'.join(out)


if __name__ == '__main__':
    if '--table' in sys.argv:
        print(table_markdown())
