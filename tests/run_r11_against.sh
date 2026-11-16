#!/bin/sh
# يشغّل حالات المراجعة الحادية عشرة على كود التزام آخر، بالحالات ومشغّليها من الالتزام الحالي.
#     sh tests/run_r11_against.sh 16b124a
# الالتزام 16b124a هو الذي فحصه المراجع: يُتوقع أن تفشل فيه حالات العيبين وتنجح حالات الحماية من التراجع.
set -u
REV=${1:?اذكر الالتزام}
ROOT=$(git rev-parse --show-toplevel)
DIR=$(mktemp -d)
git -C "$ROOT" archive "$REV" | tar -x -C "$DIR"
MAP=$(ls "$ROOT"/mental-math-map-v*-single-file.md | sort -V | tail -n 1)
echo "الكود من الالتزام $(git -C "$ROOT" rev-parse --short "$REV")، والحالات من الالتزام الحالي"
SHORT=$(git -C "$ROOT" rev-parse --short "$REV")
{ python3 "$ROOT/tests/test_r11.py" "$MAP" --code="$DIR"; node "$ROOT/tests/test_r11.mjs" "$DIR/app"; } 2>&1 \
  | sed "s#على الكود في [^ ]*#على الكود في الالتزام $SHORT#; s#على التطبيق في [^ ]*#على التطبيق في الالتزام $SHORT#"
rm -rf "$DIR"
exit 0
