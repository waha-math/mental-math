#!/bin/sh
# يشغّل حالات المراجعة الرابعة عشرة على كود التزام آخر، بالحالات ومشغّليها من الالتزام الحالي.
#     sh tests/run_r14_against.sh 11419f8
# 11419f8 فحصته المراجعة 14. حالات الاستعادة في النسختين، ثم اختبار المتصفح كله على تطبيق ذلك الالتزام: يُنسخ
# مجلد tests/browser الحالي فوق نسخة الالتزام، فتحمّل الصفحةُ وحداتِ app منه.
set -u
REV=${1:?اذكر الالتزام}
ROOT=$(git rev-parse --show-toplevel)
DIR=$(mktemp -d)
git -C "$ROOT" archive "$REV" | tar -x -C "$DIR"
MAP=$(ls "$ROOT"/mental-math-map-v*-single-file.md | sort -V | tail -n 1)
SHORT=$(git -C "$ROOT" rev-parse --short "$REV")
echo "الكود من الالتزام $SHORT، والحالات من الالتزام الحالي"
{ python3 "$ROOT/tests/test_r14.py" "$MAP" --code="$DIR"; node "$ROOT/tests/test_r14.mjs" "$DIR/app"; } 2>&1 \
  | sed "s#على الكود في [^ ]*#على الكود في الالتزام $SHORT#; s#على التطبيق في [^ ]*#على التطبيق في الالتزام $SHORT#"
rm -rf "$DIR/tests/browser"
cp -r "$ROOT/tests/browser" "$DIR/tests/browser"
ln -s "$ROOT/node_modules" "$DIR/node_modules"
echo "--- اختبار المتصفح على تطبيق الالتزام $SHORT"
node "$DIR/tests/browser/test_store_browser.mjs" 2>&1 | grep -E '^(===|  |        |نجحت|أخفق)'
rm -rf "$DIR"
exit 0
