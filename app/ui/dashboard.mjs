// لوحة الوالد (قرار الأب، 19 نوفمبر): ما جرى لكل طفل، من سجله المحفوظ وحده. لا DOM هنا ولا قرار: قراءة فقط.
//
// لكل مهارة في نطاق الطفل جرى فيها شيء: حالتها من أدلة المحرك (progress)، وقرار المعلم إن فُتحت به، ونتائج فحوص الاستقلال
// والاحتفاظ من سجل المجدول، وعدد البنود المسجلة وطلبات المساعدة واختيارات «كيف حسبتها؟» من سجلات البنود.
// قرار المعلم يُعرض منفصلًا عن الحالة: يفتح التقدم وليس دليل إتقان.

const STATE = {
  met: 'أثبتها الطفل: فهم واستقلال',
  understood: 'فهم، ولم يثبت استقلاله بعد',
  stumbled: 'تعثّر فيها',
  exempt: 'أثبتها الطفل ببوابة',
  none: 'لم يثبت فيها شيء بعد',
};

// دليل الطريقة (قرار الأب، 25 نوفمبر): نوع الدليل الذي يؤدي فيه الطفل خطوة تميّز الطريقة. ف2 حيث هو في صف المهارة،
// و3-4-1 بلا ف2: بند نموذجه يطلب جمع العشرات (خطوة التجزئة)
const METHOD_F1 = new Set(['3-4-1']);
const plainText = (t) => String(t).replace(/[\u2066-\u2069]/g, '').trim();

export function summarize(e, sc, profile, pack) {
  const BY = new Map(pack.items.map((i) => [i.id, i]));
  const days = [...new Set(e.s.order.map((s) => e.s.sessions[s].day))].sort((a, b) => a - b);
  const all = profile.scope.map((skill) => {
    const [status, und, ind] = e.progress(skill);
    const state = status === 'met' ? 'met' : status === 'stumbled' ? 'stumbled' : status === 'exempt' ? 'exempt'
      : und ? 'understood' : 'none';
    const tags = sc.log.filter((x) => x[2] === skill).map((x) => x[1]);
    const recs = sc.records.filter((r) => r.skill === skill && !r.void);
    const how = {};
    for (const r of recs) if (r.how) how[r.how] = (how[r.how] ?? 0) + 1;
    const desc = recs.filter((r) => r.activity === 'describe');   // الفحص الوصفي: الصحيح من المعروض، بلا حكم
    // «استطاع تنفيذ الطريقة عند طلبها»: بند دليل فهم من نوع الطريقة، أُجيب صحيحًا من أول مرة بلا دعم، وحقيقته لم تُعرض
    // قبله في الدرس. لا يُستنتج من الناتج أو الزمن
    const types = profile.types[skill] ?? [];
    const mtype = types.includes('ف2') ? 'ف2' : METHOD_F1.has(skill) ? 'ف1' : null;
    const method = mtype === null ? null : recs.filter((r) => r.activity === 'evidence' && BY.get(r.item)?.evidence === mtype
      && r.first === true && r.final === 'correct' && !(r.support ?? []).length && !BY.get(r.item)?.fact_seen_before
      && !r.fact_just_seen).length;
    // فحص الاستقلال: كم بندًا وكم حقيقة، وأي الحقائق أخطأ فيها وكم مرة (3-8-3: عشرة بنود على خمس حقائق)
    const chk = recs.filter((r) => r.activity === 'check' && r.status === 'complete');
    const facts = new Map();
    for (const r of chk) {
      const it = BY.get(r.item);
      const k = JSON.stringify(it?.fact ?? r.item);
      const f = facts.get(k) ?? { text: plainText(it?.text_ar ?? r.item), n: 0, wrong: 0 };
      f.n += 1;
      if (r.final !== 'correct') f.wrong += 1;
      facts.set(k, f);
    }
    const checkFacts = chk.length ? { items: chk.length, facts: facts.size,
      wrong: [...facts.values()].filter((f) => f.wrong).map((f) => [f.text, f.wrong]) } : null;
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
      method, checkFacts,
    };
  });
  // النطاق صار المراحل 1 إلى 3 (50 مهارة): صفوف اللوحة لما جرى فيه شيء وحده. وما تحت قرار البداية بلا دليل من الطفل يُذكر
  // في سطر واحد «تُخطيت بقرار تحديد نقطة البداية»، فلا يُقرأ إتقانًا ولا يختفي. ما له دليل يبقى صفًّا بحالته من الدليل
  const touched = (x) => x.state !== 'none' || x.teacher || x.items > 0 || x.checks.length || x.retention.length;
  const below = new Set(profile.scope.filter((x) => e.decisions('open', x).length).flatMap((x) => [...e.anc[x]]));
  const skills = all.filter(touched);
  const skipped = all.filter((x) => !touched(x) && below.has(x.skill)).map((x) => x.skill);
  // وما لم يُفحص أصلًا وليس تحت قرار البداية: مهارة جانبية لم يحتج إليها بعد (قرار الأب، 25 نوفمبر)
  const untested = all.filter((x) => !touched(x) && !below.has(x.skill)).map((x) => x.skill);
  return { skipped, untested, days: days.length, first: days[0] ?? null, last: days[days.length - 1] ?? null, skills };
}

// يوم الأسرة (عدد الأيام منذ 1970 بمنطقة الأسرة) تاريخًا يُقرأ
export const dayText = (d) => (d === null ? '—'
  : new Date(d * 86400000).toLocaleDateString('ar-EG-u-nu-latn', { timeZone: 'UTC', dateStyle: 'medium' }));
