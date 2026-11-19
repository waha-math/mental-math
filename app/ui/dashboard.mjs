// لوحة الوالد (قرار الأب، 19 نوفمبر): ما جرى لكل طفل، من سجله المحفوظ وحده. لا DOM هنا ولا قرار: قراءة فقط.
//
// لكل مهارة في نطاق الطفل: حالتها من أدلة المحرك (progress)، وقرار المعلم إن فُتحت به، ونتائج فحوص الاستقلال
// والاحتفاظ من سجل المجدول، وعدد البنود المسجلة وطلبات المساعدة واختيارات «كيف حسبتها؟» من سجلات البنود.
// قرار المعلم يُعرض منفصلًا عن الحالة: يفتح التقدم وليس دليل إتقان.

const STATE = {
  met: 'أتقنها: فهم واستقلال',
  understood: 'فهم، ولم يثبت استقلاله بعد',
  stumbled: 'تعثّر فيها',
  exempt: 'أُعفي منها ببوابة',
  none: 'لم يثبت فيها شيء بعد',
};

export function summarize(e, sc, profile, pack) {
  const days = [...new Set(e.s.order.map((s) => e.s.sessions[s].day))].sort((a, b) => a - b);
  const skills = profile.scope.map((skill) => {
    const [status, und, ind] = e.progress(skill);
    const state = status === 'met' ? 'met' : status === 'stumbled' ? 'stumbled' : status === 'exempt' ? 'exempt'
      : und ? 'understood' : 'none';
    const tags = sc.log.filter((x) => x[2] === skill).map((x) => x[1]);
    const recs = sc.records.filter((r) => r.skill === skill && !r.void);
    const how = {};
    for (const r of recs) if (r.how) how[r.how] = (how[r.how] ?? 0) + 1;
    const desc = recs.filter((r) => r.activity === 'describe');   // الفحص الوصفي: الصحيح من المعروض، بلا حكم
    return {
      skill, name: pack.ui['skill.' + skill]?.ar ?? skill, state, label: STATE[state],
      teacher: e.decisions('open', skill).length > 0, ind,
      checks: tags.filter((t) => t.startsWith('check_')).map((t) => t.slice(6)),
      retention: tags.filter((t) => t.startsWith('retention_')).map((t) => t.slice(10)),
      items: recs.length,
      help: recs.filter((r) => (r.support ?? []).includes('requested')).length,
      supported: recs.filter((r) => (r.support ?? []).some((x) => x !== 'requested')).length,
      how,
      describe: desc.length ? { correct: desc.filter((r) => r.final === 'correct').length, total: desc.length } : null,
    };
  });
  return { days: days.length, first: days[0] ?? null, last: days[days.length - 1] ?? null, skills };
}

// يوم الأسرة (عدد الأيام منذ 1970 بمنطقة الأسرة) تاريخًا يُقرأ
export const dayText = (d) => (d === null ? '—'
  : new Date(d * 86400000).toLocaleDateString('ar-EG-u-nu-latn', { timeZone: 'UTC', dateStyle: 'medium' }));
