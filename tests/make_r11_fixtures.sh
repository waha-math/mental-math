#!/bin/sh
# يصنع tests/r11_fixtures.json بمحرك الالتزام 2509126، ثم يمرّر كل حالة بمحرك 16b124a (قراءة وحفظ).
set -eu
ROOT=$(git rev-parse --show-toplevel)
DIR=$(mktemp -d)
VIA=$(mktemp -d)
git -C "$ROOT" archive 2509126 | tar -x -C "$DIR"
git -C "$ROOT" archive 16b124a | tar -x -C "$VIA"
MAP=$(ls "$ROOT"/mental-math-map-v*-single-file.md | sort -V | tail -n 1)
python3 "$ROOT/tests/make_r11_fixtures.py" "$MAP" --code="$DIR" --via="$VIA"
rm -rf "$DIR" "$VIA"
