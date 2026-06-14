#!/usr/bin/env bash
# (선택) 터미널 창 없이 더블클릭 실행되는 Pydashboard.app 번들을 생성한다.
# AppleScript 로 Pydashboard.command 를 백그라운드 실행만 하는 얇은 래퍼.
#
# 사용:  ./scripts/build_macos_app.sh
# 결과:  ./Pydashboard.app  (Finder 더블클릭 → 터미널 없이 서버 기동 + 브라우저 오픈)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

APP="Pydashboard.app"
rm -rf "$APP"

# osacompile 로 AppleScript → .app 생성
osacompile -o "$APP" -e "do shell script \"'$DIR/Pydashboard.command' > /dev/null 2>&1 &\""

echo "생성 완료: $DIR/$APP"
echo "Finder 에서 더블클릭하면 터미널 없이 실행됩니다."
