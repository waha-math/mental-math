# حزمة الحساب الذهني: الخريطة 2.24 والمواصفة والمحرك وطبقة البنود والمحتوى، وبداية التطبيق (16 نوفمبر 2026)

للمراجع: الرد على المراجعة الثالثة والعشرين في `R23-RESPONSE.md`، والثانية والعشرين في `R22-RESPONSE.md`، والرد على المراجعة السادسة عشرة في `R16-RESPONSE.md`، وطلب مراجعة المرحلة 0 من الواجهة في `PHASE0-REVIEW.md` وخطتها في `UI-PLAN.md`، والرد على المراجعة الخامسة عشرة في `R15-RESPONSE.md`، والرابعة عشرة في `R14-RESPONSE.md`، وطلب الحفظ الذرّي في `ATOMIC-SAVE.md`، والرد على المراجعة الثالثة عشرة في `R13-RESPONSE.md`، وعلى الثانية عشرة في `R12-RESPONSE.md`، وعلى الحادية عشرة في `R11-RESPONSE.md`، وعلى العاشرة في `R10-RESPONSE.md`، ثم `state-transition-spec.md` (الأقسام 11.3 و12 إلى 17). الخريطة في `mental-math-map-v2.24-single-file.md`. الأوامر من هذا المجلد، بـ Python 3 وحده، وبـ Node لجزأي التطبيق:

```
python3 test_transition_engine.py mental-math-map-v2.24-single-file.md      # 30 اختبارًا للمحرك المرجعي
python3 test_item_layer.py mental-math-map-v2.24-single-file.md             # 23 اختبارًا لطبقة البنود والمجدول والمسارات
python3 engine_sim.py mental-math-map-v2.24-single-file.md 400              # مطابقة المحاكاة على المحرك بالقديمة
python3 policy_sim.py mental-math-map-v2.24-single-file.md                  # تجارب المحاكاة كلها على المحرك: أرقام الخريطة
python3 policy_sim.py mental-math-map-v2.24-single-file.md 2000 --alt       # القاعدة السابقة لقرار ك4، للمقارنة
python3 placement_sim.py mental-math-map-v2.24-single-file.md --selftest    # اختبارات المحاكاة القديمة
python3 slice_content.py mental-math-map-v2.24-single-file.md               # يولّد المحتوى ويفحصه
python3 transition_engine.py mental-math-map-v2.24-single-file.md --table   # يطبع جدول الانتقالات

python3 export_conformance.py mental-math-map-v2.24-single-file.md          # يولّد بيانات محرك التطبيق ومتجهات المطابقة
node app/test_conformance.mjs                                               # يطابق محرك التطبيق بالمحرك المرجعي
node app/test_items_conformance.mjs                                         # يطابق طبقة البنود في التطبيق بالمرجعية
python3 export_scheduler.py mental-math-map-v2.24-single-file.md           # يولّد متجهات المجدول
node app/test_scheduler_conformance.mjs                                     # يطابق المجدول في التطبيق بالمرجعي

python3 tests/test_r10.py mental-math-map-v2.24-single-file.md              # حالات المراجعة العاشرة على بايثون
node tests/test_r10.mjs                                                     # الحالات نفسها على JavaScript
sh tests/run_r10_against.sh 2509126                                         # الحالات نفسها على الالتزام قبل الإصلاح

python3 tests/test_r11.py mental-math-map-v2.24-single-file.md              # حالات المراجعة الحادية عشرة: المجدول والترحيل
node tests/test_r11.mjs                                                     # حالات الترحيل على JavaScript
sh tests/run_r11_against.sh 16b124a                                         # الحالات نفسها على الالتزام قبل الإصلاح
sh tests/run_r11_against.sh 9aa40d5                                         # وعلى الالتزام قبل إصلاح المراجعة 12
sh tests/make_r11_fixtures.sh                                               # يعيد صنع الحالات القديمة بمحركي 2509126 و16b124a

python3 tests/test_r13.py mental-math-map-v2.24-single-file.md              # حالتا المراجعة الثالثة عشرة: النشاط المحفوظ
node tests/test_r13.mjs                                                     # الحالتان نفسهما على مجدول التطبيق
sh tests/run_r13_against.sh 8b6f81d                                         # الحالتان على الالتزام قبل الإصلاح

python3 tests/test_persist.py mental-math-map-v2.24-single-file.md          # سياسة الحفظ والاستعادة (المرجع)
python3 export_persist.py mental-math-map-v2.24-single-file.md              # يولّد متجهات الاستعادة
node app/test_persist_conformance.mjs                                       # يطابق الاستعادة في التطبيق بالمرجع
npm install && node tests/browser/test_store_browser.mjs                    # الحفظ الذرّي في Chrome (IndexedDB)
python3 tests/test_r14.py mental-math-map-v2.24-single-file.md              # حالات المراجعة الرابعة عشرة: السجلات وقرار المعلم
node tests/test_r14.mjs                                                     # الحالات نفسها على التطبيق
sh tests/run_r14_against.sh 11419f8                                         # الحالات واختبار المتصفح على الالتزام قبل الإصلاح
python3 tests/test_r15.py mental-math-map-v2.24-single-file.md              # المراجعة الخامسة عشرة: الاستعادة المرفوضة لا تغيّر بيانات المستدعي
node tests/test_r15.mjs                                                     # الحالات نفسها على التطبيق
sh tests/run_r15_against.sh a0c363e                                         # الحالات على الالتزام قبل الإصلاح
python3 tests/test_phase0.py mental-math-map-v2.24-single-file.md           # المرحلة 0 من الواجهة: التوقف والإغلاق والاستعادة وتكملة الجلسة
node tests/test_phase0.mjs                                                  # الحالات نفسها على التطبيق
sh tests/run_phase0_against.sh 0189879                                      # الحالات على الالتزام الذي فحصته المراجعة 16
python3 tests/compare_vectors.py 5b70237                                    # المتجهات الحالية مقابل main قبل المرحلة 0 (أداة عرض للفروق، لا حكم)
python3 content_sequence.py                                                 # تتابع البنود كما يراها الطفل أثناء التشغيل (3.5)
python3 tests/test_content_sequence.py mental-math-map-v2.24-single-file.md # يختبر فحص التتابع وتغطيته لما يعرضه المجدول فعلًا
python3 tests/test_r22.py mental-math-map-v2.24-single-file.md              # المراجعة 22: التتابع بين الأنشطة، بشريط أحداث ثابت
node tests/test_r22.mjs                                                     # الشريط نفسه على التطبيق
python3 tests/verify.py --browser                                           # مسار التحقق المعتمد: مجلد مؤقت نظيف، ورمز خروجه هو الحكم
python3 tests/test_verify.py                                                # يختبر المسار نفسه: متجهات قديمة ومصدِّر مكسور
```

المتجهات (`app/conformance_vectors.json` و`app/item_vectors.json` و`app/scheduler_vectors.json`، نحو 65 ميغابايت) لا تُحفظ في المستودع لأنها مولَّدة: يولّدها `export_conformance.py` في نحو دقيقة ونصف و`export_scheduler.py` في أقل من دقيقة، قبل تشغيل أوامر Node. ومخرجات كل أمر مرفقة باسم ينتهي بـ `_output.txt`، لمن لا يستطيع تشغيله.
