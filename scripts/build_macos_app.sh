#!/usr/bin/env bash
# 터미널 창 없이 더블클릭 실행되는 Pydashboard.app 번들을 생성한다.
# AppleScript 로 Pydashboard.command 를 백그라운드 실행만 하는 얇은 래퍼.
# 서버 출력은 data/logs/server.log 로 남긴다.
#
# 사용:  ./scripts/build_macos_app.sh
# 결과:  ./Pydashboard.app  (Finder 더블클릭 → 터미널 없이 단독앱 창 기동)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

APP="Pydashboard.app"
rm -rf "$APP"

# osacompile 로 AppleScript → .app 생성
osacompile -o "$APP" -e "do shell script \"mkdir -p '$DIR/data/logs'; '$DIR/Pydashboard.command' > '$DIR/data/logs/server.log' 2>&1 &\""

echo "생성 완료: $DIR/$APP"
echo "Finder 에서 더블클릭하면 터미널 없이 단독앱 창으로 실행됩니다."
echo "서버 로그: $DIR/data/logs/server.log"
