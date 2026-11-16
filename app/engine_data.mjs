// مولَّد من transition_engine.py بالأمر: python3 export_conformance.py <الخريطة>. لا يُعدَّل باليد.
export const DATA = {
 "events": [
  "session_start",
  "session_end",
  "date_confirmed",
  "gate_result",
  "short_check_result",
  "open_lesson",
  "resume_lesson",
  "lesson_opening_result",
  "understanding_proved",
  "check_started",
  "check_resumed",
  "check_held",
  "independence_result",
  "check_abandoned",
  "teacher_open",
  "teacher_defer",
  "teacher_revoke",
  "recheck_result",
  "invalidate_session",
  "retention_result"
 ],
 "network": {
  "ids": [
   "1-1-1",
   "1-1-2",
   "1-2-1",
   "1-2-2",
   "1-3-1",
   "1-3-2",
   "1-3-3",
   "1-4-1",
   "1-4-2",
   "1-5-1",
   "1-5-2",
   "1-5-3",
   "2-1-1",
   "2-1-2",
   "2-2-1",
   "2-2-2",
   "2-3-1",
   "2-3-2",
   "2-4-1",
   "2-4-2",
   "2-5-1",
   "2-5-2",
   "2-5-3",
   "2-6-1",
   "2-6-2",
   "2-6-3",
   "2-6-4",
   "3-1-1",
   "3-1-2",
   "3-1-3",
   "3-1-4",
   "3-2-1",
   "3-2-2",
   "3-2-3",
   "3-3-1",
   "3-3-2",
   "3-4-1",
   "3-4-2",
   "3-5-1",
   "3-5-2",
   "3-5-3",
   "3-6-1",
   "3-6-2",
   "3-6-3",
   "3-6-4",
   "3-7-1",
   "3-7-2",
   "3-8-1",
   "3-8-2",
   "3-8-3"
  ],
  "pre": {
   "1-1-1": [],
   "1-1-2": [
    "1-1-1"
   ],
   "1-2-1": [
    "1-1-1"
   ],
   "1-2-2": [
    "1-2-1"
   ],
   "1-3-1": [
    "1-1-1"
   ],
   "1-3-2": [
    "1-3-1",
    "1-1-2"
   ],
   "1-3-3": [
    "1-3-2"
   ],
   "1-4-1": [
    "1-3-3"
   ],
   "1-4-2": [
    "1-4-1"
   ],
   "1-5-1": [
    "1-2-2",
    "1-3-2"
   ],
   "1-5-2": [
    "1-3-3",
    "1-5-1"
   ],
   "1-5-3": [
    "1-5-2"
   ],
   "2-1-1": [
    "1-4-1"
   ],
   "2-1-2": [
    "2-1-1",
    "1-5-2"
   ],
   "2-2-1": [
    "2-1-1",
    "1-5-1"
   ],
   "2-2-2": [
    "2-2-1"
   ],
   "2-3-1": [
    "2-2-1"
   ],
   "2-3-2": [
    "2-3-1"
   ],
   "2-4-1": [
    "1-4-2",
    "2-1-1"
   ],
   "2-4-2": [
    "2-4-1"
   ],
   "2-5-1": [
    "2-4-2",
    "2-1-2"
   ],
   "2-5-2": [
    "2-4-2"
   ],
   "2-5-3": [
    "2-5-1",
    "2-5-2"
   ],
   "2-6-1": [
    "2-4-1"
   ],
   "2-6-2": [
    "2-4-2"
   ],
   "2-6-3": [
    "2-3-2",
    "2-4-2",
    "2-6-1"
   ],
   "2-6-4": [
    "2-5-3",
    "2-6-3"
   ],
   "3-1-1": [
    "2-1-1"
   ],
   "3-1-2": [
    "3-1-1"
   ],
   "3-1-3": [
    "3-1-1",
    "1-5-2"
   ],
   "3-1-4": [
    "3-1-1"
   ],
   "3-2-1": [
    "3-1-1",
    "1-4-2"
   ],
   "3-2-2": [
    "3-2-1",
    "2-4-2"
   ],
   "3-2-3": [
    "3-2-1",
    "2-5-1"
   ],
   "3-3-1": [
    "3-1-2",
    "2-1-2"
   ],
   "3-3-2": [
    "3-3-1",
    "3-2-2"
   ],
   "3-4-1": [
    "3-1-3",
    "2-1-2"
   ],
   "3-4-2": [
    "3-4-1",
    "2-6-3"
   ],
   "3-5-1": [
    "3-3-2",
    "3-2-3"
   ],
   "3-5-2": [
    "3-2-1",
    "3-3-1",
    "2-5-2"
   ],
   "3-5-3": [
    "3-5-1",
    "3-5-2"
   ],
   "3-6-1": [
    "3-3-2",
    "2-6-1"
   ],
   "3-6-2": [
    "3-5-1",
    "3-6-1"
   ],
   "3-6-3": [
    "3-6-1"
   ],
   "3-6-4": [
    "3-5-2",
    "3-6-2"
   ],
   "3-7-1": [
    "3-5-2"
   ],
   "3-7-2": [
    "3-7-1"
   ],
   "3-8-1": [
    "2-2-1",
    "3-4-2"
   ],
   "3-8-2": [
    "2-2-2",
    "3-8-1"
   ],
   "3-8-3": [
    "3-8-2"
   ]
  }
 },
 "quota": {
  "follow": {
   "gate": 1,
   "short": 2,
   "teach": 1
  },
  "search": {
   "gate": {
    "older": 2,
    "young": 1
   },
   "short": 0,
   "teach": 0
  },
  "start": {
   "gate": 0,
   "short": 4,
   "teach": 1
  }
 },
 "reasons": {
  "already_active": "الدرس أو محاولة الفحص نشط في هذه الجلسة",
  "already_open": "درس المهارة مفتوح",
  "already_satisfied": "المهارة مجتازة أو مستوفاة",
  "bad_decision": "قرار المعلم ناقص: السبب، أو متطلب غير مستوفى لم يُذكر في المتجاوَز",
  "bad_event": "الحدث ناقص أو فيه حقل بنوع أو قيمة غير مسموحة",
  "bad_target": "الجلسة غير موجودة، أو ما زالت مفتوحة، أو أُبطلت من قبل",
  "blocked": "متطلب مباشر متعثَّر فيه أو ينتظر: المهارة لا تُفحص",
  "check_idle": "محاولة الفحص ليست نشطة في هذه الجلسة: تُستأنف بحدث صريح يستهلك الحصة التعليمية",
  "check_needs_practice": "بعد محاولة لم تُجتز تلزم جلسة نشط فيها الدرس قبل الإعادة",
  "check_pending": "للمهارة محاولة فحص لم تُغلق: تُتمّ، أو يتركها المعلم بحدث صريح، قبل بدء أخرى",
  "check_same_day": "فحص الاستقلال في يوم بعد يوم آخر دليل فهم، والإعادة في يوم بعد يوم المحاولة السابقة",
  "check_state": "محاولة الفحص أُغلقت، أو تُركت، أو عُلّقت للمراجعة، أو تحتاج إعادة بدء، أو معرّفها مستعمل",
  "date_unconfirmed": "تاريخ الجلسة يحتاج تأكيد الوالد: جاء قبل يوم آخر جلسة أو بعده بأكثر من 30 يومًا",
  "event_id_conflict": "المعرّف نفسه وصل من قبل بمحتوى مختلف",
  "gate_limit": "للمهارة بوابة وإعادة واحدة على الأكثر",
  "internal_error": "تعطّل التنفيذ، وأُعيدت الحالة كما كانت قبل الطلب",
  "lesson_idle": "الدرس ليس نشطًا في هذه الجلسة أو ينتظر حصة تعليمية: يُستأنف بحدث صريح",
  "no_check": "لا محاولة فحص بهذا المعرّف لهذه المهارة",
  "no_decision": "لا قرار سارٍ بهذا المعرّف",
  "no_recheck": "لا مهارة معلَّقة تنتظر هذا المتطلب، ولا دليل استيفاء مُبطَل لهذه المهارة يُعاد بناؤه",
  "no_session": "لا جلسة مفتوحة بهذا المعرّف",
  "not_checkable": "التحقق القصير للمؤجَّلة أو لمتطلب غير مفحوص، ومرة واحدة",
  "not_deferrable": "للمهارة دليل مباشر، فلا تؤجَّل بقرار",
  "not_flagged": "الجلسة ليست معلَّمة بتنبيه تاريخ",
  "not_met": "فحص الاحتفاظ لمهارة مستوفاة باجتياز فحص الاستقلال",
  "not_open": "درس المهارة غير مفتوح، أو ليس في الطور المطلوب",
  "prerequisite": "متطلب مباشر غير مستوفى",
  "quota_gate": "استُهلكت بوابات هذه الجلسة، أو لا بوابة في هذا النوع من الجلسات",
  "quota_short": "استُهلكت التحققات القصيرة في هذه الجلسة",
  "quota_teach": "استُهلكت الحصة التعليمية الواحدة في هذه الجلسة",
  "regate_not_allowed": "الإعادة بعد فتح الدرس واختصاره، وفي جلسة لاحقة، وإن سُمح بها",
  "retention_done": "أُجريت فحوص الاحتفاظ الثلاثة لهذه المهارة",
  "retention_early": "لم يحِن موعد فحص الاحتفاظ: الفاصل يُحسب من يوم الاجتياز ثم من يوم الفحص السابق",
  "session_open": "جلسة أخرى مفتوحة ولم تُختم",
  "session_order": "نوع الجلسة لا يأتي في هذا الموضع: بحث (4 على الأكثر) ثم بدء واحدة ثم متابعة",
  "suspended": "الوصول إلى المهارة معلَّق حتى إعادة التحقق أو قرار المعلم",
  "understanding_first": "فحص الاستقلال بعد ثبوت الفهم",
  "unknown_skill": "المهارة ليست في المحتوى المسلَّم",
  "version_unavailable": "إصدار تعريفات بنود الفحص غير متاح"
 },
 "retention": {
  "gaps": [
   7,
   21,
   60
  ],
  "items": 5,
  "ok": 4
 },
 "schema": {
  "check_abandoned": {
   "check_id": "str",
   "reason": "str"
  },
  "check_held": {
   "check_id": "str",
   "items?": "strlist",
   "reason": [
    "enum",
    "interruptions",
    "no_alternate",
    "no_items"
   ],
   "session": "str",
   "skill": "str"
  },
  "check_resumed": {
   "check_id": "str",
   "session": "str",
   "skill": "str"
  },
  "check_started": {
   "check_id": "str",
   "content_version": "int",
   "session": "str",
   "skill": "str"
  },
  "date_confirmed": {
   "target": "str"
  },
  "gate_result": {
   "errors?": "strlist",
   "has_calc?": "bool",
   "items?": "strlist",
   "result": [
    "enum",
    "pass",
    "fail",
    "help",
    "interrupted"
   ],
   "session": "str",
   "skill": "str"
  },
  "independence_result": {
   "check_id": "str",
   "items?": "strlist",
   "result": [
    "enum",
    "pass",
    "fail",
    "help"
   ],
   "session": "str",
   "skill": "str"
  },
  "invalidate_session": {
   "target": "str"
  },
  "lesson_opening_result": {
   "items?": "strlist",
   "outcome": [
    "enum",
    "skip",
    "full_error",
    "full_help"
   ],
   "session": "str",
   "skill": "str"
  },
  "open_lesson": {
   "session": "str",
   "skill": "str"
  },
  "recheck_result": {
   "items?": "strlist",
   "ok": "bool",
   "session": "str",
   "skill": "str"
  },
  "resume_lesson": {
   "session": "str",
   "skill": "str"
  },
  "retention_result": {
   "correct": "int",
   "exposed?": "bool",
   "items?": "strlist",
   "session": "str",
   "skill": "str"
  },
  "session_end": {
   "session": "str"
  },
  "session_start": {
   "day": "int",
   "kind": [
    "enum",
    "search",
    "start",
    "follow"
   ],
   "session": "str"
  },
  "short_check_result": {
   "items?": "strlist",
   "ok": "bool",
   "session": "str",
   "skill": "str"
  },
  "teacher_defer": {
   "reason": "str",
   "skills": "strlist"
  },
  "teacher_open": {
   "bypass": "strlist",
   "reason": "str",
   "skill": "str"
  },
  "teacher_revoke": {
   "decision": "str"
  },
  "understanding_proved": {
   "items?": "strlist",
   "session": "str",
   "skill": "str"
  }
 },
 "search_cap": 4
};
