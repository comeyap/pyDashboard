#!/usr/bin/env bash
# Pydashboard 원클릭 실행기 (macOS).
# Finder 에서 이 파일을 더블클릭하면 가상환경 준비 → 서버 시작 → 브라우저 자동 오픈.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1) 가상환경 보장
if [[ ! -x ".venv/bin/python" ]]; then
  echo "[Pydashboard] 가상환경(.venv) 생성 중..."
  python3 -m venv .venv
fi

# 2) 의존성 보장 (핵심 패키지 import 실패 시에만 설치)
if ! .venv/bin/python -c "import flask, psutil, cronsim" >/dev/null 2>&1; then
  echo "[Pydashboard] 의존성 설치 중..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

# 3) 서버 시작 (app.py 가 브라우저를 자동으로 연다)
echo "[Pydashboard] 서버를 시작합니다. 브라우저가 자동으로 열립니다."
echo "[Pydashboard] 종료하려면 이 창에서 Ctrl+C 를 누르세요."
exec .venv/bin/python app.py
