# حزمة الحساب الذهني: الخريطة 2.13 والمواصفة والمحرك وطبقة البنود والمحتوى، وبداية التطبيق (16 نوفمبر 2026)

للمراجع: الرد على المراجعة الثانية عشرة في `R12-RESPONSE.md`، وعلى الحادية عشرة في `R11-RESPONSE.md`، وعلى العاشرة في `R10-RESPONSE.md`، ثم `state-transition-spec.md` (الأقسام 12 إلى 14). الخريطة في `mental-math-map-v2.13-single-file.md`. الأوامر من هذا المجلد، بـ Python 3 وحده، وبـ Node لجزأي التطبيق:

```
python3 test_transition_engine.py mental-math-map-v2.13-single-file.md      # 30 اختبارًا للمحرك المرجعي
python3 test_item_layer.py mental-math-map-v2.13-single-file.md             # 23 اختبارًا لطبقة البنود والمجدول والمسارات
python3 engine_sim.py mental-math-map-v2.13-single-file.md 400              # مطابقة المحاكاة على المحرك بالقديمة
python3 policy_sim.py mental-math-map-v2.13-single-file.md                  # تجارب المحاكاة كلها على المحرك: أرقام الخريطة
python3 policy_sim.py mental-math-map-v2.13-single-file.md 2000 --alt       # القاعدة السابقة لقرار ك4، للمقارنة
python3 placement_sim.py mental-math-map-v2.13-single-file.md --selftest    # اختبارات المحاكاة القديمة
python3 slice_content.py mental-math-map-v2.13-single-file.md               # يولّد المحتوى ويفحصه
python3 transition_engine.py mental-math-map-v2.13-single-file.md --table   # يطبع جدول الانتقالات

python3 export_conformance.py mental-math-map-v2.13-single-file.md          # يولّد بيانات محرك التطبيق ومتجهات المطابقة
node app/test_conformance.mjs                                               # يطابق محرك التطبيق بالمحرك المرجعي
node app/test_items_conformance.mjs                                         # يطابق طبقة البنود في التطبيق بالمرجعية

python3 tests/test_r10.py mental-math-map-v2.13-single-file.md              # حالات المراجعة العاشرة على بايثون
node tests/test_r10.mjs                                                     # الحالات نفسها على JavaScript
sh tests/run_r10_against.sh 2509126                                         # الحالات نفسها على الالتزام قبل الإصلاح

python3 tests/test_r11.py mental-math-map-v2.13-single-file.md              # حالات المراجعة الحادية عشرة: المجدول والترحيل
node tests/test_r11.mjs                                                     # حالات الترحيل على JavaScript
sh tests/run_r11_against.sh 16b124a                                         # الحالات نفسها على الالتزام قبل الإصلاح
sh tests/run_r11_against.sh 9aa40d5                                         # وعلى الالتزام قبل إصلاح المراجعة 12
sh tests/make_r11_fixtures.sh                                               # يعيد صنع الحالات القديمة بمحركي 2509126 و16b124a
```

المتجهات (`app/conformance_vectors.json` و`app/item_vectors.json`، نحو 22 ميغابايت) لا تُحفظ في المستودع لأنها مولَّدة: يولّدها `export_conformance.py` في نحو دقيقة، قبل تشغيل أمري Node. ومخرجات كل أمر مرفقة باسم ينتهي بـ `_output.txt`، لمن لا يستطيع تشغيله.
