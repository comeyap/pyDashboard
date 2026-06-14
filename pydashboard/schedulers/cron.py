"""crontab 파싱 및 차기 실행 일시 계산 (Linux/macOS).

`crontab -l` 출력을 읽어 각 항목의 cron 표현식과 명령을 추출하고,
cronsim 으로 다음 실행 시각을 계산한다.

cronsim 선택 근거: croniter 는 EU Cyber Resilience Act(2026-06 발효)로 인해
2024-12 unmaintained 선언됨(Airflow/Buildbot 등도 제거 진행 중). cronsim 은
의존성이 없고 활발히 유지보수되며, cron 모니터링 서비스 Healthchecks 에서
실사용 중이라 본 도메인과 부합한다.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from typing import Any, Optional

try:
    from cronsim import CronSim, CronSimError
except ImportError:  # pragma: no cover - 의존성 미설치 시 graceful degrade
    CronSim = None  # type: ignore
    CronSimError = Exception  # type: ignore


def next_run_from_expr(expr: str, base: Optional[datetime] = None) -> Optional[datetime]:
    """cron 표현식으로부터 base 이후 가장 가까운 실행 시각을 계산한다."""
    if CronSim is None:
        return None
    base = base or datetime.now().astimezone()
    try:
        return next(CronSim(expr, base))
    except (CronSimError, StopIteration, ValueError):
        return None


def _read_user_crontab() -> str:
    """현재 사용자 crontab 내용을 반환한다. 없으면 빈 문자열."""
    if shutil.which("crontab") is None:
        return ""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    # crontab 미등록 시 exit code 1
    if result.returncode != 0:
        return ""
    return result.stdout


# cron 필드 5개(분 시 일 월 요일) 뒤가 명령
_CRON_FIELDS = 5


def parse_crontab_text(text: str) -> list[dict[str, Any]]:
    """crontab 텍스트를 파싱하여 항목 리스트로 반환한다."""
    entries: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 환경 변수 설정 라인 (FOO=bar) 은 건너뛴다
        if "=" in line.split()[0]:
            continue

        parts = line.split(None, _CRON_FIELDS)
        if len(parts) < _CRON_FIELDS + 1:
            continue

        expr = " ".join(parts[:_CRON_FIELDS])
        command = parts[_CRON_FIELDS]
        nxt = next_run_from_expr(expr)
        entries.append(
            {
                "source": "cron",
                "expr": expr,
                "command": command,
                "next_run": nxt,
            }
        )
    return entries


def list_cron_entries() -> list[dict[str, Any]]:
    """사용자 crontab 의 모든 스케줄 항목을 반환한다."""
    return parse_crontab_text(_read_user_crontab())
