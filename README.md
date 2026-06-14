# 🐍 Pydashboard

로컬·서버 환경에서 개별적으로 구동되거나 스케줄링된 여러 **Python 프로젝트(프로세스)**를
한곳에서 모니터링하고 제어하는 웹 기반 대시보드입니다.

- **실시간 상태 모니터링** — 상시 실행(always-on) 프로세스의 생존 여부를 PID 기반으로 추적
- **스케줄 파싱·시각화** — 시스템 `crontab` 및 macOS `LaunchAgents(plist)`를 읽어 **다음 실행 예정 일시** 계산
- **기존 스케줄 자동 탐지** — 등록 시 Cron/LaunchAgent 선택하면 OS에 이미 등록된 스케줄을 조회해 자동 채움. 새로고침 시 라이브 재조회
- **프로세스 제어** — 대시보드에서 즉시 실행(Run Now) / 강제 중지(Stop), **중복 실행 자동 차단**
- **다양한 실행 형태** — `python script.py`뿐 아니라 **임의 실행 커맨드**(Streamlit, 쉘 래퍼, `python -m`, `uv run` 등) 지원
- **경로 찾아보기** — 절대경로를 직접 입력하거나 **📁 파일 탐색기**로 선택
- **오탐 방지 식별** — 실행 시 PID 파일 + 전용 환경변수(`PYDASHBOARD_PROJECT_ID`)를 주입하고,
  외부 실행 프로세스는 스크립트 경로 **정확 일치**(substring 금지)로 매칭

## 화면 구성

각 프로젝트는 카드로 표시되며 다음 정보를 포함합니다.

| 요소 | 설명 |
|------|------|
| 상태 태그 | `Running`(초록) / `Idle·Stopped`(회색) / `Error`(빨강) |
| 스케줄 정보 | 등록된 주기 (Cron 표현식, LaunchAgent 등) |
| 실행 예정 일시 | 파싱 결과 기반 다음 실행 시각 (예: `2026-06-15 00:00 예정`) |
| 제어 버튼 | 상태에 따라 `▶ 바로 실행` ↔ `■ 강제 중지` 동적 전환 |

## 기술 스택

| 영역 | 선택 | 비고 |
|------|------|------|
| 웹 프레임워크 | **Flask 3.x** | 가볍고 단순, 폴링 기반 실시간 갱신 |
| 프로세스 제어 | **psutil** | PID 추적, `terminate`/`kill`, `environ` 검증 |
| Cron 파싱 | **cronsim** | `croniter` 대체 — croniter는 EU Cyber Resilience Act로 유지보수 중단. cronsim은 의존성이 없고 활발히 유지보수되며 cron 모니터링 서비스 Healthchecks에서 실사용 |
| LaunchAgent 파싱 | **plistlib** (표준) | `StartCalendarInterval`/`StartInterval` → 다음 실행 시각 |
| 저장소 | JSON 파일 | `data/projects.json` (원자적 쓰기) |
| 프론트엔드 | Vanilla JS | 빌드 도구 불필요 |

## 설치

> 요구사항: **Python 3.10 이상** (cronsim 요구사항)

```bash
git clone https://github.com/comeyap/pyDashboard.git
cd pyDashboard

# 가상환경 생성 및 의존성 설치
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 실행

### 원클릭 실행 (macOS, 권장)

Finder 에서 **`Pydashboard.command`** 을 더블클릭하면 가상환경 준비 → 서버 시작 →
브라우저 자동 오픈까지 한 번에 진행됩니다. (터미널에서 `python app.py` 를 칠 필요 없음)

> 터미널 창 없이 앱처럼 띄우고 싶으면 한 번만 `./scripts/build_macos_app.sh` 를 실행해
> `Pydashboard.app` 을 만든 뒤, 그 앱을 더블클릭하세요.

### 터미널 실행

```bash
python app.py     # 기동 후 브라우저가 자동으로 열립니다
```

기본적으로 `http://127.0.0.1:8800` 에서 대시보드가 열립니다.
우측 상단 **`+ 프로젝트 추가`** 버튼으로 모니터링할 Python 프로젝트를 등록하세요.
브라우저 자동 열기를 끄려면 `PYDASHBOARD_NO_BROWSER=1` 을 설정합니다.

## 테스트

모든 로직은 `tests/` 의 pytest 스위트로 검증합니다.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

### 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `PYDASHBOARD_HOST` | `127.0.0.1` | 바인딩 호스트 |
| `PYDASHBOARD_PORT` | `8800` | 포트 |
| `PYDASHBOARD_UI_POLL` | `5` | UI 자동 갱신 주기(초) |
| `PYDASHBOARD_SCHEDULE_REFRESH` | `60` | 시스템 스케줄 재파싱 기준(초) |
| `PYDASHBOARD_DEBUG` | `0` | `1`이면 Flask 디버그 모드 |
| `PYDASHBOARD_NO_BROWSER` | `0` | `1`이면 시작 시 브라우저 자동 열기 끔 |

예시:

```bash
PYDASHBOARD_PORT=9000 PYDASHBOARD_UI_POLL=3 python app.py
```

## 프로젝트 등록 항목

| 항목 | 필수 | 설명 |
|------|------|------|
| 프로젝트 이름 | ✅ | 카드에 표시될 이름 |
| 설명 | | 간단한 설명 |
| 스크립트 경로 | △ | 식별/기본 실행용 `.py`·스크립트 경로. **📁 찾아보기** 버튼으로 선택 가능 |
| 실행 커맨드 | △ | 지정 시 이 커맨드로 실행 (Streamlit·쉘·`python -m` 등). 비우면 `Python 실행 경로 + 스크립트` 사용 |
| Python 실행 경로 | | 커맨드 미사용 시 (예: `/Users/me/proj/.venv/bin/python`, 기본 `python3`) |
| 작업 디렉토리 | | 비우면 스크립트 폴더 사용. **📁 찾아보기** 지원 |
| 실행 인자 | | 커맨드 미사용 시 공백 구분 (예: `--mode prod`) |
| 스케줄러 타입 | | `상시 실행` / `Cron` / `LaunchAgent` / `수동` |
| Cron 표현식 | | `Cron` 타입일 때 (예: `0 0 * * *`) |
| Plist 경로 | | `LaunchAgent` 타입일 때. **📁 찾아보기** 지원 |

> △ **스크립트 경로**와 **실행 커맨드** 중 최소 하나는 필요합니다.
> 경로는 직접 입력하거나 **📁 찾아보기** 버튼으로 서버 파일시스템을 탐색해 선택할 수 있습니다.

### 등록 예시

**일반 Python 스크립트**
- 스크립트 경로: `/Users/me/proj/main.py`
- Python 실행 경로: `/Users/me/proj/.venv/bin/python`

**Streamlit 앱** (`streamlit run app.py`)
- 스크립트 경로: `/Users/me/proj/app.py` *(실행 중 프로세스 식별용)*
- 실행 커맨드: `.venv/bin/streamlit run app.py`
- 작업 디렉토리: `/Users/me/proj`

**쉘 래퍼 / 스케줄 잡** (예: launchd가 호출하는 `run_live.sh`)
- 스크립트 경로: `/Users/me/proj/scripts/run_live.sh` *(식별용)*
- 실행 커맨드: `scripts/run_live.sh` *(대시보드에서 직접 실행 시)*
- 작업 디렉토리: `/Users/me/proj`
- 스케줄러 타입: `LaunchAgent`, Plist 경로: `~/Library/LaunchAgents/com.me.live.plist`

## 디렉토리 구조

```
pyDashboard/
├── app.py                       # 애플리케이션 진입점 (+ 브라우저 자동 열기)
├── Pydashboard.command          # macOS 원클릭 실행기 (더블클릭)
├── scripts/build_macos_app.sh   # (선택) .app 번들 생성
├── requirements.txt
├── requirements-dev.txt         # 테스트 의존성(pytest)
├── tests/                       # pytest 스위트 (storage/schedulers/process/api/detect/launcher)
├── pydashboard/
│   ├── config.py                # 경로·상수
│   ├── storage.py               # 프로젝트 등록 JSON CRUD
│   ├── process_manager.py       # 실행/중지/상태 추적 (PID·오탐 방지)
│   ├── api.py                   # Flask REST 라우트
│   └── schedulers/
│       ├── cron.py              # crontab 파싱 + 다음 실행 시각
│       └── launchagents.py      # plist 파싱 + 다음 실행 시각
├── templates/index.html
├── static/{style.css, app.js}
└── data/                        # 런타임 데이터 (gitignore)
    ├── projects.json            # 등록 정보
    ├── pids/                    # PID 파일
    └── logs/                    # 실행 로그
```

## 기술적 고려사항

- **권한** — 시스템 `crontab`·`LaunchAgents` 읽기와 프로세스 종료는 대시보드를 실행한
  사용자 권한으로 수행됩니다. 시스템 전역(`/Library/LaunchAgents`) 항목 제어에는
  적절한 권한이 필요할 수 있습니다.
- **프로세스 식별** — 단순 `grep` 오탐을 피하기 위해, 대시보드 실행분은 PID 파일 +
  `PYDASHBOARD_PROJECT_ID` 환경변수로 검증하고, 외부 실행분은 *인터프리터가 python이고
  인자가 스크립트 경로와 정확히 일치*하는 경우에만 매칭합니다.
- **스케줄 동기화** — UI는 `PYDASHBOARD_UI_POLL` 주기로 상태를 폴링하며,
  시스템 스케줄은 요청 시점에 다시 파싱하여 최신 상태를 반영합니다.

## API 요약

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/projects` | 프로젝트 목록 + 상태 + 다음 실행 시각 |
| `POST` | `/api/projects` | 프로젝트 등록 |
| `PUT` | `/api/projects/<id>` | 수정 |
| `DELETE` | `/api/projects/<id>` | 삭제 |
| `POST` | `/api/projects/<id>/run` | 즉시 실행 (중복 시 `409`) |
| `POST` | `/api/projects/<id>/stop` | 강제 중지 |
| `GET` | `/api/projects/<id>/logs` | 실행 로그 tail |
| `GET` | `/api/fs?path=<dir>` | 서버 파일시스템 탐색 (경로 선택용, 로컬 전용) |
| `GET` | `/api/system/detect?script_path=<path>` | 해당 스크립트로 OS에 등록된 스케줄 1회 탐지 |
| `GET` | `/api/system/schedules` | 시스템 cron + LaunchAgents 전체 파싱 |

## 라이선스

MIT
