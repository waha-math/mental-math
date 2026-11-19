#!/bin/sh
# يشغّل حالات المرحلة 0 على كود التزام آخر، بالحالات ومشغّليها من الالتزام الحالي.
#     sh tests/run_phase0_against.sh 0189879
# 0189879 فحصته المراجعة 16.
set -u
REV=${1:?اذكر الالتزام}
ROOT=$(git rev-parse --show-toplevel)
DIR=$(mktemp -d)
git -C "$ROOT" archive "$REV" | tar -x -C "$DIR"
MAP=$(ls "$ROOT"/mental-math-map-v*-single-file.md | sort -V | tail -n 1)
SHORT=$(git -C "$ROOT" rev-parse --short "$REV")
echo "الكود من الالتزام $SHORT، والحالات من الالتزام الحالي"
{ python3 "$ROOT/tests/test_phase0.py" "$MAP" --code="$DIR"; node "$ROOT/tests/test_phase0.mjs" "$DIR/app"; } 2>&1 \
  | sed "s#على الكود في [^ ]*#على الكود في الالتزام $SHORT#; s#على التطبيق في [^ ]*#على التطبيق في الالتزام $SHORT#"
rm -rf "$DIR"
exit 0
