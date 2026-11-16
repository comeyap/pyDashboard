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

# 런처는 Dock 에 띄우지 않는다 (LSUIElement).
# 런처(.app)와 파이썬 프로세스가 별개라 둘 다 Dock 에 뜨는데, 런처는 창이 없어
# 하얀 두루마리 아이콘으로만 남아 두 개로 보인다. 런처를 숨기면 뱀 아이콘(파이썬) 하나만 남는다.
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$APP/Contents/Info.plist" 

# 앱 아이콘을 🐍 아이콘으로 교체 (기본 AppleScript applet 아이콘 대체)
# static/pydashboard.icns 는 scripts/make_icon.py 로 생성되어 repo 에 커밋돼 있다.
if [[ -f "static/pydashboard.icns" ]]; then
  cp "static/pydashboard.icns" "$APP/Contents/Resources/applet.icns"
  touch "$APP"   # Finder 아이콘 캐시 갱신
fi

# Info.plist·아이콘 교체 뒤에는 서명이 깨지므로, 마지막에 다시 서명한다.
# 서명이 깨진 채로 두면 macOS가 교체한 아이콘을 무시하고 기본 두루마리 아이콘을 보여줄 수 있다.
codesign --force --deep --sign - "$APP"

echo "생성 완료: $DIR/$APP"
echo "Finder 에서 더블클릭하면 터미널 없이 단독앱 창으로 실행됩니다."
echo "서버 로그: $DIR/data/logs/server.log"
