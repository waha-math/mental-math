#!/bin/sh
# يصنع tests/r11_fixtures.json بمحرك الالتزام 2509126 الذي فحصه المراجع.
set -eu
ROOT=$(git rev-parse --show-toplevel)
DIR=$(mktemp -d)
git -C "$ROOT" archive 2509126 | tar -x -C "$DIR"
MAP=$(ls "$ROOT"/mental-math-map-v*-single-file.md | sort -V | tail -n 1)
python3 "$ROOT/tests/make_r11_fixtures.py" "$MAP" --code="$DIR"
rm -rf "$DIR"
