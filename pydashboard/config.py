"""애플리케이션 경로 및 상수 정의."""

from __future__ import annotations

import os
from pathlib import Path

# 프로젝트 루트 (이 파일 기준 한 단계 위)
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
PID_DIR = DATA_DIR / "pids"
LOG_DIR = DATA_DIR / "logs"
PROJECTS_FILE = DATA_DIR / "projects.json"

# 프로세스를 대시보드가 실행했음을 표시하는 환경 변수 키.
# PID 재사용으로 인한 오탐을 막기 위해 실행 시 프로젝트 id 를 주입한다.
ENV_PROJECT_KEY = "PYDASHBOARD_PROJECT_ID"

# 스케줄러가 OS 레벨에서 변경됐을 때 대시보드가 다시 파싱하는 주기(초).
# UI 폴링과는 별개로, 시스템 스케줄 캐시 무효화 기준으로 사용한다.
SCHEDULE_REFRESH_SEC = int(os.environ.get("PYDASHBOARD_SCHEDULE_REFRESH", "60"))

# UI 기본 폴링 주기(초).
UI_POLL_SEC = int(os.environ.get("PYDASHBOARD_UI_POLL", "5"))


def ensure_dirs() -> None:
    """런타임에 필요한 디렉토리를 보장한다."""
    for d in (DATA_DIR, PID_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
