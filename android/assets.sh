#!/usr/bin/env bash
# أصول التطبيق في الحزمة: app/ بلا اختبارات المطابقة، والمحتوى. يُشغَّل من جذر المستودع
set -euo pipefail
A=android/app/src/main/assets
rm -rf $A && mkdir -p $A/app
cp -r app/index.html app/manifest.webmanifest app/icons app/ui $A/app/
cp app/*.mjs $A/app/
rm -f $A/app/test_*.mjs
cp slice-content.json $A/
