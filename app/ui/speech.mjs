// الصوت: نطق المتصفح، مؤقت (UI-PLAN.md، القسم 1). الصيغة المنطوقة للمعادلة تُشتق هنا مؤقتًا، ومكانها ملفات المحتوى (7.6).
const WORDS = { ar: { '+': ' زائد ', '−': ' ناقص ', '-': ' ناقص ', '=': ' يساوي ', '▢': ' كم ' },
  en: { '+': ' plus ', '−': ' minus ', '-': ' minus ', '=': ' equals ', '▢': ' what ' } };

export function spoken(text, lang = 'ar') {
  return text.replace(/[⁦-⁩]/g, '').replace(/[+−\-=▢]/g, (c) => WORDS[lang][c]).replace(/\s+/g, ' ').trim();
}

// يعيد { available(), say(text) }. available: هل للغة صوت على هذا الجهاز؟ الأصوات تُحمَّل متأخرة في بعض المتصفحات
export function browserSpeaker(lang = 'ar', synth = globalThis.speechSynthesis) {
  const voice = () => (synth ? synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang)) : undefined);
  return {
    async available() {
      if (!synth) return false;
      if (voice()) return true;
      await new Promise((r) => {
        const t = setTimeout(r, 1500);
        synth.addEventListener('voiceschanged', () => { clearTimeout(t); r(); }, { once: true });
      });
      return Boolean(voice());
    },
    say(text) {
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.voice = voice() ?? null;
      u.lang = lang;
      u.rate = 0.9;
      synth.speak(u);
    },
  };
}
