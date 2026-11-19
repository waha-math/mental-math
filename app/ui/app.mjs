// الشاشات (UI-PLAN.md، القسم 4)، للوح أفقي. هذه الجولة: مسار الصغير في 1-4 بالعربية، ومدخل بالغ محدود.
// لا قرار تربوي هنا: الشاشة تعرض البند الذي يطلبه المجدول، وترسل النقرات أحداثًا خامًا عبر طبقة الوصل (link.mjs).
// ما تقرره الشاشة شكلٌ فقط: متى يظهر النموذج بعد خطأ في التعلّم (4.1)، ومتى يظهر زر «التالي».
import { openDB } from '../store.mjs';
import { Link, Blocked, familyDay, loadDevice, saveDevice, pinHash, checkRecord } from './link.mjs';
import { readAll, makeBackup, checkBackup, importBackup, undoInfo, undoImport } from '../backup.mjs';
import { PROFILES, TZ, DEVICE } from './config.mjs';
import { spoken, browserSpeaker } from './speech.mjs';
import { modelFor, supportFor, comparePair } from './models.mjs';

const T = globalThis.MM_TEST ?? {};     // منفذ الاختبار: speaker و now و mono و hooks و db
const root = document.getElementById('app');

// نصوص الواجهة التي ليست في ملف المحتوى بعد (7.6). العربية وحدها في هذه الجولة
const STR = {
  start: 'ابدأ', tapStart: 'اضغط ابدأ', callAdult: 'نادِ أحد الكبار', adults: 'للكبار', next: 'التالي',
  lookFrame: 'انظر إلى الإطار، وجرّب مرة أخرى', tryAgain: 'جرّب مرة أخرى', askHelp: 'هل تحتاج مساعدة؟',
  yes: 'نعم', no: 'لا', someone: 'أحد الكبار', back: 'عدنا', exit: 'خروج', soon: 'قريبًا',
  doneToday: 'انتهت مهمة اليوم. نلتقي غدًا', nothing: 'لا مهمة جديدة الآن',
  more: { resume: 'أكمل الدرس', lesson: 'أكمل الدرس', practice: 'تدريب أكثر', open: 'درس جديد' }, askMore: 'هل تريد المزيد؟',
  answered: (n) => (n === 0 ? 'انتهت مهمة اليوم' : n === 1 ? 'أجبتَ عن سؤال واحد اليوم' : n === 2 ? 'أجبتَ عن سؤالين اليوم'
    : n <= 10 ? `أجبتَ عن ${n} أسئلة اليوم` : `أجبتَ عن ${n} سؤالًا اليوم`),
  save: { idle: '', saving: 'جارٍ الحفظ', saved: 'تم الحفظ', failed: 'لم يُحفظ', read_only: 'لم يُحفظ' },
};
const REASON = {
  setup: 'لا ملف لهذا الطفل بعد. يُنشأ بقرار الفتح في 10.2.',
  save: 'تعذّر الحفظ. ما أجابه الطفل باقٍ في هذه النافذة، ولن يُعرض بند جديد قبل أن يُحفظ.',
  conflict: 'نافذة أخرى كتبت في ملف هذا الطفل. هذه النافذة توقفت.',
  other_window: 'ملف هذا الطفل مفتوح في نافذة أخرى.',
  audio: 'لا صوت عربي على هذا الجهاز. الطفل الذي لا يقرأ يحتاج من يقرأ له.',
  restore_rejected: 'السجل المحفوظ لم يُقبل عند الفتح. لم يُغيَّر شيء.',
  content_changed: 'المحتوى تغيّر وفي الملف نشاط جارٍ. لم يُغيَّر شيء.',
  menu: 'مدخل البالغ',
};

let worker = null;                      // تسجيل عامل الخدمة، إن وُجد
let db, dev, pack, speaker, link = null, child = null, lastActivity = null, audioWaived = false, muted = false;

function h(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'on') for (const [e, f] of Object.entries(v)) n.addEventListener(e, f);
    else if (v === true) n.setAttribute(k, '');
    else if (v !== false && v !== null && v !== undefined) n.setAttribute(k, v);
  }
  n.append(...kids.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
  return n;
}

function screen(name, ...kids) {
  root.dataset.screen = name;
  root.replaceChildren(...kids.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
}

const say = (text) => { if (speaker && !muted) speaker.say(spoken(text)); };
const ui = (key) => pack.ui[key].ar;
const nameOf = (c) => dev.names[c] ?? '';

function strip({ adult = null } = {}) {
  const p = child ? PROFILES[child] : null;
  return h('header', { class: 'strip' },
    p && h('span', { class: 'who', 'data-child': child }, p.avatar),
    p && h('span', { class: 'name' }, nameOf(child)),
    h('span', { class: 'save', id: 'save' }, link && link.saver ? STR.save[link.saver.state] : ''),
    adult && h('button', { class: 'adult', id: 'adult', on: { click: adult } }, STR.adults));
}

function showSave() {
  const n = document.getElementById('save');
  if (n && link && link.saver) {
    n.textContent = STR.save[link.saver.state];
    n.dataset.state = link.saver.state;
  }
}

// يشغّل عملًا قد يحتاج بالغًا. يعيد null إن حُوّل إلى «نادِ أحد الكبار»
async function guard(fn) {
  try {
    return await fn();
  } catch (err) {
    if (!(err instanceof Blocked)) throw err;
    callAdult(err.reason, err.detail);
    return null;
  }
}

// ---------------------------------------------------------------- من أنا؟
function who() {
  if (link) link.close();
  link = null;
  child = null;
  lastActivity = null;
  screen('who', strip({ adult: () => pinGate(() => adultPanel('menu'), who) }),
    h('section', { class: 'center' }, h('div', { class: 'avatars' },
      Object.entries(PROFILES).map(([id, p]) => h('button', { class: 'avatar', 'data-child': id, disabled: !p.ready,
        'aria-label': nameOf(id) || id, on: { click: () => enter(id) } }, p.avatar,
      h('small', {}, p.ready ? nameOf(id) : STR.soon))))));
}

async function enter(id) {
  child = id;
  link = new Link({ db, child: id, profile: PROFILES[id], pack, tz: TZ, now: T.now, mono: T.mono, hooks: T.hooks ?? {},
    onStatus: showSave });
  const r = await guard(() => link.load());
  if (r === null) return;
  if (r === 'setup') return callAdult('setup');
  await ready();
}

// الصوت شرط لمن لا يقرأ (profile.voice): بلا صوت عربي يُنادى بالغ. من يقرأ يمضي بلا صوت
async function ready() {
  const ok = await speaker.available();
  if (!ok && PROFILES[child].voice && !audioWaived) return callAdult('audio');
  muted = !ok;
  workshop();
}

// ---------------------------------------------------------------- الورشة
function workshop() {
  const today = familyDay((T.now ?? Date.now)(), TZ);
  // جلسة مفتوحة، ولو إضافية، تُكمَل بـ«ابدأ». وبعد ختم جلسة اليوم لا «ابدأ»: يُعرض «أريد المزيد» إن كان عندنا ما يُعرض
  const done = link.sc.cur === null
    && link.e.s.order.some((s) => link.e.s.sessions[s].ended && link.e.s.sessions[s].day === today);
  screen('workshop', strip({ adult: () => pinGate(() => adultPanel('menu'), workshop) }),
    h('section', { class: 'center' },
      done ? [h('div', { class: 'icon' }, '🌙'), h('h1', { id: 'done-today' }, STR.doneToday), moreButton(),
        h('button', { id: 'exit', on: { click: who } }, STR.exit)]
        : h('button', { class: 'big', id: 'start', on: { click: () => begin() } }, '▶ ' + STR.start)));
  say(done ? STR.doneToday + (link.more().length ? '. ' + STR.askMore : '') : STR.tapStart);
}

// «أريد المزيد»: يظهر حين يعرض المجدول جلسة إضافية، باسم أول ما فيها. لا يظهر زر لا شيء وراءه
function moreButton() {
  const plan = link.more();
  return plan.length ? h('button', { class: 'big', id: 'more', 'data-plan': plan[0][0], on: { click: () => begin(true) } },
    '▶ ' + STR.more[plan[0][0]]) : null;
}

async function begin(more = false) {
  const r = await guard(() => link.start(more));
  if (r === null || r === 'busy') return;
  if (r === 'done') {
    screen('nothing', strip({ adult: () => pinGate(() => adultPanel('menu'), who) }),
      h('section', { class: 'center' }, h('h1', {}, STR.nothing), h('button', { id: 'exit', on: { click: who } }, STR.exit)));
    return;
  }
  after();
}

function after() {
  if (link.ended() || link.view() === null) endScreen();
  else item();
}

// ---------------------------------------------------------------- شاشة المسألة
// النص: المعادلة بين علامتي العزل في المحتوى تُعرض داخل <bdi dir="ltr">، فلا تنعكس مع العربية (7.6)
function promptOf(text) {
  const p = h('p', { class: 'prompt', id: 'prompt' });
  for (const part of text.split(/(⁦[^⁩]*⁩)/)) {
    if (part.startsWith('⁦')) p.append(h('bdi', { dir: 'ltr', class: 'eq' }, part.slice(1, -1).trim()));
    else if (part) p.append(part);
  }
  return p;
}

async function item() {
  const v = link.view();
  const { item: it, want, kind, seq } = v;
  const watch = want.role === 'lesson.watch' || it.role === 'lesson.watch';
  const s = { typed: '', tries: v.raw.filter((x) => x[0] === 'confirm').length, solved: false, support: false, ready: false,
    sheet: null, how: v.raw.some((x) => x[0] === 'how') };

  const send = async (ev) => {
    const r = await guard(() => link.press(seq, ev));
    showSave();
    if (r === 'rejected') console.warn('حدث مرفوض', ev, link.st.reject);
    return r;
  };
  const speakItem = () => say(it.audio_ar);

  const confirm = async () => {
    if (!s.ready || s.solved || s.typed === '') return;
    const val = Number(s.typed);
    if (kind === 'assess' && it.how && !s.how) {   // «كيف حسبتها؟» (10.2): اختيار يُسجَّل قبل التأكيد، بلا تصحيح
      say(ui('how.title'));
      s.sheet = h('div', { id: 'how' }, h('h1', {}, ui('how.title')), h('div', { class: 'row' },
        Object.entries(pack.cards.how).map(([k, c]) => h('button', { 'data-how': k, on: { click: async () => {
          s.sheet = null;
          s.ready = false;
          draw();
          const r = await send(['how', k]);
          if (r === 'void') return after();
          if (r !== 'open') { s.ready = true; draw(); return; }
          s.how = true;
          s.ready = true;
          await confirm();
        } } }, c.ar))));
      draw();
      return;
    }
    if (kind === 'assess') {            // لا تغذية راجعة في التقييم (4.1): البند ينتهي بأول تأكيد
      s.ready = false;
      draw();
      const r = await send(['confirm', val]);
      if (r === 'next' || r === 'void') after();
      return;
    }
    if (kind === 'teach') {
      const r = await send(['confirm', val]);
      if (r !== 'open') { if (r === 'void' || r === 'next') after(); return; }
    }
    s.tries += 1;
    if (val === it.answer) {
      s.solved = true;
    } else {                            // 4.1: لا علامة خطأ. يعود النموذج مجهّزًا بالمسألة، ويحاول الطفل ثانية
      s.support = true;
      s.typed = '';
      say(supportFor(it) ? STR.lookFrame : STR.tryAgain);
    }
    draw();
  };

  const next = async () => {
    if (!s.ready) return;
    s.ready = false;
    draw();
    const r = await send(['end']);
    if (r === 'next' || r === 'void') after();
    else if (r !== null) { s.ready = true; draw(); }
  };

  const help = () => {
    if (!s.ready) return;
    if (kind === 'assess') {            // 2.7: يسجّل الطلب وينهي البند. تأكيد بنقرة ثانية، لئلا تنهي المحاولةَ لمسةٌ خاطئة
      say(STR.askHelp);
      s.sheet = h('div', {}, h('h1', {}, STR.askHelp), h('div', { class: 'row' },
        h('button', { id: 'help-yes', on: { click: async () => {
          s.sheet = null; s.ready = false; draw();
          const r = await send(['support', 'requested']);
          if (r === 'next' || r === 'void') after();
        } } }, '✋ ' + STR.yes),
        h('button', { id: 'help-no', on: { click: () => { s.sheet = null; draw(); } } }, STR.no)));
    } else if (kind === 'teach') {
      s.sheet = h('div', {}, h('div', { class: 'row' },
        h('button', { id: 'help-tool', on: { click: async () => {
          s.sheet = null;
          const r = await send(['support', 'extra_model']);
          if (r === 'open') s.support = true;
          draw();
        } } }, '🧰 ' + ui('button.tool')),
        h('button', { id: 'help-someone', on: { click: async () => {
          const r = await send(['support', 'someone']);
          if (r !== 'open') { s.sheet = null; draw(); return; }
          say(STR.callAdult);
          s.sheet = h('div', {}, h('div', { class: 'icon' }, '🧑‍🤝‍🧑'), h('h1', {}, STR.callAdult),
            h('button', { id: 'help-back', on: { click: () => { s.sheet = null; draw(); } } }, STR.back));
          draw();
        } } }, '🧑 ' + STR.someone)));
    } else {
      s.support = true;                 // بند عرض: الأداة تظهر، ولا حدث يُسجَّل (البند لا سجل له)
    }
    draw();
  };

  const key = (d) => {
    if (!s.ready || s.solved || watch) return;
    if (d === 'del') s.typed = s.typed.slice(0, -1);
    else if (s.typed.length < 3) s.typed = (s.typed === '0' ? '' : s.typed) + d;
    draw();
  };

  // بند المقارنة في الدرس: يختار الطفل بطاقة، ثم يُعرض الجواب لأن السؤال له جواب يُتحقق منه (ر7)، ولا سجل لبند عرض
  const cards = it.performance === 'compare' ? it.cards : null;
  const pick = (k) => {
    if (!s.ready || s.solved) return;
    s.picked = k;
    s.solved = true;
    say(pack.cards.compare[it.answer].ar);
    draw();
  };

  function draw() {
    const model = cards ? comparePair(it.model, pack.cards.compare) : (s.support && supportFor(it)) || modelFor(it);
    const canNext = kind !== 'assess' && s.ready && (watch || s.solved || s.tries >= 2);
    const padOff = !s.ready || s.solved || watch;
    screen('item', strip(),
      h('section', { class: 'task', 'data-item': it.id, 'data-kind': kind, 'data-activity': want.activity,
        'data-ready': String(s.ready) },
      h('div', { class: 'stage' }, promptOf(it.text_ar),
        h('div', { class: 'model', id: 'model' }, model),
        h('div', { class: 'tools' },
          h('button', { id: 'listen', 'aria-label': ui('button.listen'), on: { click: speakItem } }, '🔊'),
          !watch && !s.solved && !cards && h('button', { id: 'help', disabled: !s.ready, on: { click: help } },
            kind === 'shown' ? '🧰 ' + ui('button.tool') : '✋ ' + ui('button.help')),
          s.solved && h('span', { class: 'note', id: 'ok' }, '✓'),
          canNext && h('button', { class: 'next', id: 'next', on: { click: next } }, STR.next + ' ←'))),
      h('div', { class: 'side' },
        cards ? h('div', { class: 'cards', id: 'cards' }, cards.map((k) => h('button', { 'data-card': k,
          class: s.solved && k === it.answer ? 'right' : s.picked === k ? 'picked' : null, disabled: !s.ready || s.solved,
          on: { click: () => pick(k) } }, (s.solved && k === it.answer ? '✓ ' : '') + pack.cards.compare[k].ar)))
          : [h('div', { class: 'answer', id: 'answer' }, watch ? String(it.answer) : s.typed),
            h('div', { class: 'pad' },
          ['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => h('button', { 'data-key': d, disabled: padOff,
            on: { click: () => key(d) } }, d)),
          h('button', { 'data-key': 'del', disabled: padOff, 'aria-label': 'حذف', on: { click: () => key('del') } }, '⌫'),
          h('button', { 'data-key': '0', disabled: padOff, on: { click: () => key('0') } }, '0'),
          h('button', { class: 'ok', 'data-key': 'ok', disabled: padOff || s.typed === '', 'aria-label': 'تأكيد',
            on: { click: confirm } }, '✓'))])),
      s.sheet && h('div', { class: 'sheet', id: 'sheet' }, s.sheet));
    showSave();
  }

  draw();
  const ok = await guard(() => link.shown(seq));     // يُحفظ معروضًا قبل أن يُقبل فيه شيء
  if (ok === null) return;
  if (ok === false) return after();
  s.ready = true;
  draw();
  const intro = want.activity !== lastActivity && pack.ui[want.activity + '.intro'];
  lastActivity = want.activity;
  say((intro ? intro.ar + ' ' : '') + it.audio_ar + (watch ? ' ' + it.answer : ''));
}

// ---------------------------------------------------------------- الختام
function endScreen() {
  const { answered } = link.summary();
  screen('end', strip(), h('section', { class: 'center' }, h('div', { class: 'icon' }, '⭐'),
    h('h1', { id: 'end-message' }, STR.answered(answered)), moreButton(),
    h('button', { id: 'exit', on: { click: who } }, STR.exit)));
  say(STR.answered(answered) + (link.more().length ? '. ' + STR.askMore : ''));
  showSave();
}

// ---------------------------------------------------------------- نادِ أحد الكبار
function callAdult(reason, detail = null) {
  screen('call', strip(), h('section', { class: 'center', 'data-reason': reason },
    h('div', { class: 'icon' }, '🧑‍🤝‍🧑'), h('h1', {}, STR.callAdult),
    h('button', { id: 'adult', on: { click: () => pinGate(() => adultPanel(reason, detail), () => callAdult(reason, detail)) } },
      STR.adults)));
  say(STR.callAdult);
}

// رمز البالغ: 4 أرقام (8.3). يُنشأ عند أول دخول. قفل للطفل، لا حماية بيانات
// back: الشاشة التي جاء منها. «رجوع» بلا رمز يعيد إليها هي، فلا يتجاوز الطفل بها «نادِ أحد الكبار»
function pinGate(then, back) {
  const fresh = dev.pin === null;
  const a = h('input', { id: 'pin', type: 'password', inputmode: 'numeric', maxlength: '4', autocomplete: 'off' });
  const b = fresh ? h('input', { id: 'pin2', type: 'password', inputmode: 'numeric', maxlength: '4', autocomplete: 'off' }) : null;
  const msg = h('p', { class: 'warn', id: 'pin-msg' });
  const go = async () => {
    if (!/^\d{4}$/.test(a.value)) { msg.textContent = 'الرمز 4 أرقام'; return; }
    if (fresh) {
      if (a.value !== b.value) { msg.textContent = 'الرمزان مختلفان'; return; }
      dev.salt = String((T.now ?? Date.now)());
      dev.pin = await pinHash(dev.salt, a.value);
      await saveDevice(db, dev);
    } else if (await pinHash(dev.salt, a.value) !== dev.pin) {
      msg.textContent = 'الرمز غير صحيح';
      return;
    }
    then();
  };
  screen('pin', strip(), h('section', { class: 'adultbox' }, h('h1', {}, fresh ? 'أنشئ رمز البالغ (4 أرقام)' : 'رمز البالغ'),
    h('section', {}, h('label', {}, 'الرمز', a), fresh && h('label', {}, 'أعد الرمز', b), msg,
      h('button', { id: 'pin-ok', on: { click: go } }, 'دخول'),
      h('button', { id: 'pin-cancel', on: { click: back } }, 'رجوع'))));
}

function resumeChild() {
  if (link && link.st !== null) return after();
  if (link && link.e !== null) return workshop();
  who();
}

function adultPanel(reason, detail = null) {
  const p = child ? PROFILES[child] : null;
  const msg = h('p', { class: 'warn', id: 'adult-msg' });
  const sections = [];
  if (reason === 'setup') {
    const name = h('input', { id: 'child-name', maxlength: '20', value: nameOf(child) });
    const why = h('textarea', { id: 'decision-reason', rows: '2' }, 'قرار الشريحة في 10.2');
    // القرارات لهذا الطفل وحده: يُسجَّل منها ما يختاره البالغ، ولا قرار مختار سلفًا
    const boxes = p.decisions.map((d, k) => h('input', { type: 'checkbox', id: 'dec-' + k, 'data-skill': d.skill }));
    sections.push(h('section', {}, h('label', {}, 'اسم الطفل كما يظهر له (يُحفظ على هذا الجهاز وحده)', name),
      h('p', {}, 'قرارات الفتح في الشريحة (10.2)، لهذا الطفل وحده. كل قرار يُسجَّل قرارًا للمعلم باسم مهارته، ولا يغيّر وصف الأدلة:'),
      p.decisions.map((d, k) => h('label', { class: 'pick' }, boxes[k], `فتح ${d.skill} متجاوزًا ${d.bypass.join(' و')}`)),
      h('label', {}, 'سبب القرار', why),
      h('button', { id: 'setup-ok', on: { click: async () => {
        const chosen = p.decisions.filter((_, k) => boxes[k].checked);
        if (!chosen.length) { msg.textContent = 'اختر قرارًا واحدًا على الأقل'; return; }
        if (!why.value.trim()) { msg.textContent = 'السبب مطلوب'; return; }
        try {
          dev.names[child] = name.value.trim();
          await saveDevice(db, dev);
          await link.setup(chosen, why.value.trim());
        } catch (err) { msg.textContent = String(err.detail ?? err.message ?? err); return; }
        await ready();
      } } }, 'سجّل وأنشئ الملف')));
  }
  if (reason === 'save') {
    sections.push(h('section', {}, h('p', {}, `سبب الفشل: ${detail}`),
      h('button', { id: 'save-retry', on: { click: async () => {
        try { await link.save(); } catch (err) { msg.textContent = `لم يُحفظ: ${err.detail ?? err.reason}`; return; }
        resumeChild();
      } } }, 'أعد المحاولة')));
  }
  if (reason === 'conflict' || reason === 'other_window') {
    sections.push(h('section', {}, h('button', { id: 'reload', on: { click: () => location.reload() } }, 'حمّل النسخة المحفوظة')));
  }
  if (reason === 'audio') {
    sections.push(h('section', {},
      h('button', { id: 'audio-retry', on: { click: ready } }, 'أعد فحص الصوت'),
      h('button', { id: 'audio-waive', on: { click: () => { audioWaived = true; workshop(); } } }, 'تابع بلا صوت: سأقرأ له')));
  }
  if (reason === 'menu') sections.push(backupSection(msg));
  if (reason === 'menu' && worker && worker.waiting) {    // إصدار جديد نُزّل وينتظر: يُطبَّق بطلب البالغ وحده
    sections.push(h('section', { id: 'update' }, h('p', {}, 'نسخة أحدث من التطبيق جاهزة.'),
      h('button', { id: 'update-now', on: { click: () => {
        navigator.serviceWorker.addEventListener('controllerchange', () => location.reload());
        worker.waiting.postMessage('update');
      } } }, 'حدّث الآن')));
  }
  if (detail && (reason === 'restore_rejected' || reason === 'content_changed')) sections.push(h('section', {}, h('p', {}, detail)));
  if (link && link.e !== null && p) {            // قرارات الفتح: المسجّل منها، وما لم يُسجَّل لهذا الطفل
    const made = link.decisions();
    const rest = p.decisions.filter((d) => !made.some((x) => x.skill === d.skill));
    const why2 = h('textarea', { id: 'decide-reason', rows: '2' });
    sections.push(h('section', { id: 'decisions' }, h('p', {}, 'قرارات الفتح في هذا الملف. قرار معلم يفتح التقدم، وليس دليل إتقان:'),
      made.map((x) => h('p', { class: 'made', 'data-skill': x.skill }, `${x.skill} متجاوزًا ${x.bypass.join(' و')}. السبب: ${x.reason}`)),
      rest.length ? [h('label', {}, 'سبب القرار الجديد', why2), rest.map((d) => h('button', { 'data-decide': d.skill,
        disabled: link.sc.cur !== null, on: { click: async () => {
          if (!why2.value.trim()) { msg.textContent = 'السبب مطلوب'; return; }
          try { await link.decide(d, why2.value.trim()); } catch (err) { msg.textContent = String(err.message ?? err); return; }
          adultPanel(reason, detail);
        } } }, `سجّل فتح ${d.skill} متجاوزًا ${d.bypass.join(' و')}`))] : null));
  }
  for (const f of (link ? link.flagged() : [])) {
    sections.push(h('section', { 'data-flag': f.session }, h('p', { class: 'warn' },
      `الجلسة ${f.session}: تاريخ الجهاز يومها بعيد عن آخر جلسة (9.1). القرارات المعتمدة على التاريخ معلّقة حتى تؤكده.`),
    h('button', { on: { click: async () => {
      try { await link.confirmDate(f.session); } catch (err) { msg.textContent = String(err.message); return; }
      adultPanel(reason, detail);
    } } }, 'تاريخ ذلك اليوم صحيح')));
  }
  if (link && link.sc) {
    for (const [ses, code, skill, kind] of link.sc.halts) {
      sections.push(h('section', {}, h('p', {}, `توقف نشاط (${kind}) للمهارة ${skill} في ${ses}: ${code}`)));
    }
  }
  screen('adult', strip(), h('section', { class: 'adultbox', 'data-reason': reason }, h('h1', {}, REASON[reason] ?? reason),
    sections, msg, h('button', { id: 'adult-back', on: { click: () => (reason === 'menu' ? resumeChild() : who()) } }, 'رجوع')));
}

// ---------------------------------------------------------------- النسخة الاحتياطية (9.2)
const BACKUP_NO = {
  not_backup: 'هذا الملف ليس نسخة احتياطية من هذا التطبيق.', version: 'صيغة النسخة أحدث من هذا التطبيق.',
  record: 'في الملف سجل تالف.', duplicate: 'في الملف سجلان لملف واحد.', device: 'سجل الجهاز في الملف تالف.',
  unknown_child: 'في الملف ملف طفل لا يعرفه هذا التطبيق.', restore_rejected: 'سجل في الملف لا يُقبل عند الفتح.',
  content_changed: 'في الملف نشاط جارٍ على محتوى غير المحتوى الحالي.', unreadable: 'تعذّرت قراءة الملف.',
};
const when = (ms) => new Date(ms).toLocaleString('ar-EG', { timeZone: TZ, dateStyle: 'medium', timeStyle: 'short' });
const nowMs = () => (T.now ?? Date.now)();

function backupSection(msg) {
  const box = h('section', { id: 'backup' });
  const pick = h('input', { type: 'file', id: 'backup-file', accept: 'application/json,.json' });
  const out = h('div', { id: 'backup-check' });
  pick.addEventListener('change', async () => {
    out.replaceChildren();
    let obj;
    try { obj = JSON.parse(await pick.files[0].text()); } catch { obj = undefined; }
    const r = obj === undefined ? { ok: false, code: 'unreadable' } : checkBackup(obj, { device: DEVICE,
      children: Object.keys(PROFILES),
      check: (rec) => checkRecord(rec, { profile: PROFILES[rec.child], pack, tz: TZ, now: nowMs }) });
    if (!r.ok) {
      out.append(h('p', { class: 'warn', id: 'backup-refused', 'data-code': r.code },
        `${BACKUP_NO[r.code] ?? r.code} لم يتغير شيء.`, r.detail ? ` (${r.detail})` : ''));
      return;
    }
    const names = (obj.records.find((x) => x.child === DEVICE) ?? { names: {} }).names;
    out.append(h('p', {}, `نسخة من ${when(obj.made_at)}، فيها: ${r.children.map((c) => names[c] || c).join('، ') || 'لا ملف طفل'}.`),
      h('p', { class: 'warn' }, 'ستحل محل كل ما على هذا الجهاز، ومعه رمز البالغ. يمكن التراجع مرة واحدة.'),
      h('button', { id: 'backup-import', on: { click: async () => {
        const w = await importBackup(db, obj, { made_at: nowMs() });
        if (!w.ok) { msg.textContent = `لم يُستعد: ${w.code}. لم يتغير شيء.`; return; }
        location.reload();
      } } }, 'استبدل ما على هذا الجهاز بهذه النسخة'));
  });
  const undo = h('div', { id: 'backup-undo' });
  undoInfo(db).then((u) => {
    if (u !== null) undo.append(h('button', { id: 'undo-import', on: { click: async () => {
      const w = await undoImport(db);
      if (!w.ok) { msg.textContent = `لم يُتراجع: ${w.code}`; return; }
      location.reload();
    } } }, `تراجع عن الاستيراد (أعد ما كان على الجهاز قبل ${when(u.made_at)})`));
  });
  box.append(h('p', {}, dev.backup_at ? `آخر نسخة احتياطية: ${when(dev.backup_at)}` : 'لم تُحفظ نسخة احتياطية من هذا الجهاز بعد.'),
    h('button', { id: 'backup-save', on: { click: async () => {
      if (link && link.saver && link.saver.state !== 'saved' && link.saver.state !== 'idle') {
        msg.textContent = 'في هذه النافذة ما لم يُحفظ بعد. احفظه أولًا.'; return;
      }
      const made = nowMs();
      const obj = makeBackup(await readAll(db), { content: { version: pack.version, digest: pack.digest }, made_at: made });
      const day = new Date(made).toLocaleDateString('en-CA', { timeZone: TZ });
      const a = h('a', { href: URL.createObjectURL(new Blob([JSON.stringify(obj)], { type: 'application/json' })),
        download: `mental-math-backup-${day}.json` });
      document.body.append(a);
      a.click();
      a.remove();
      dev.backup_at = made;
      try { await saveDevice(db, dev); } catch { /* التاريخ للتذكير وحده */ }
      adultPanel('menu');
    } } }, 'احفظ نسخة احتياطية'),
    h('label', {}, 'استعد من نسخة احتياطية', pick), out, undo);
  return box;
}

// ---------------------------------------------------------------- الإقلاع
document.addEventListener('visibilitychange', () => {   // إخفاء الصفحة ليس من زمن السقف (2.4)
  if (!link) return;
  if (document.hidden) link.pause();
  else link.resume();
});

try {
  pack = await (await fetch(new URL('../../slice-content.json', import.meta.url))).json();
  db = await openDB(T.db);
  dev = await loadDevice(db, DEVICE);
  speaker = T.speaker ?? browserSpeaker('ar');
  if ('serviceWorker' in navigator && !T.noWorker) {   // العمل دون اتصال (9.2). فشل التسجيل لا يوقف التطبيق
    navigator.serviceWorker.register(new URL('../sw.js', import.meta.url)).then((r) => { worker = r; }, () => {});
  }
  who();
} catch (err) {
  screen('broken', h('section', { class: 'center' }, h('h1', {}, STR.callAdult), h('p', {}, String(err))));
}
