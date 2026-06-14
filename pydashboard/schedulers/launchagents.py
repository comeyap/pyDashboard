"""macOS LaunchAgents(plist) 파싱 및 차기 실행 일시 계산.

~/Library/LaunchAgents 와 /Library/LaunchAgents 의 .plist 를 읽어
StartCalendarInterval / StartInterval 기반으로 다음 실행 시각을 계산한다.
"""

from __future__ import annotations

import plistlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .cron import next_run_from_expr

# 파싱 대상 LaunchAgents 디렉토리
LAUNCH_AGENT_DIRS = [
    Path.home() / "Library" / "LaunchAgents",
    Path("/Library/LaunchAgents"),
]


def _calendar_interval_to_cron(ci: dict[str, Any]) -> str:
    """StartCalendarInterval dict 를 cron 표현식으로 변환한다.

    LaunchAgent 키: Minute, Hour, Day(일), Month, Weekday → cron 5필드 매핑.
    누락 필드는 '*'.
    """
    minute = ci.get("Minute", "*")
    hour = ci.get("Hour", "*")
    day = ci.get("Day", "*")
    month = ci.get("Month", "*")
    weekday = ci.get("Weekday", "*")
    return f"{minute} {hour} {day} {month} {weekday}"


def _next_from_calendar(ci_value: Any, base: Optional[datetime] = None) -> Optional[datetime]:
    """StartCalendarInterval(dict 또는 list[dict])의 다음 실행 시각."""
    base = base or datetime.now().astimezone()
    intervals = ci_value if isinstance(ci_value, list) else [ci_value]

    candidates: list[datetime] = []
    for ci in intervals:
        if not isinstance(ci, dict):
            continue
        nxt = next_run_from_expr(_calendar_interval_to_cron(ci), base)
        if nxt:
            candidates.append(nxt)
    return min(candidates) if candidates else None


def next_run_from_plist(plist_path: str, base: Optional[datetime] = None) -> Optional[datetime]:
    """plist 파일에서 다음 실행 시각을 계산한다."""
    path = Path(plist_path).expanduser()
    if not path.is_file():
        return None
    # 시스템 plist 는 통제 불가 — 손상/비표준 파일(ExpatError 등)에도 견디도록
    # 파싱 예외를 폭넓게 흡수한다.
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None

    return _next_run_from_plist_data(data, base)


def _next_run_from_plist_data(data: dict[str, Any], base: Optional[datetime] = None) -> Optional[datetime]:
    base = base or datetime.now().astimezone()

    if "StartCalendarInterval" in data:
        return _next_from_calendar(data["StartCalendarInterval"], base)

    if "StartInterval" in data:
        # N초마다 실행. 마지막 실행 시각을 알 수 없으므로 now + interval 로 근사.
        try:
            interval = int(data["StartInterval"])
            return base + timedelta(seconds=interval)
        except (TypeError, ValueError):
            return None

    # RunAtLoad 만 있거나 keep-alive 형태는 예정 시각 개념이 없음
    return None


def _command_from_plist(data: dict[str, Any]) -> str:
    """plist 의 ProgramArguments / Program 을 명령 문자열로 합친다."""
    if "ProgramArguments" in data and isinstance(data["ProgramArguments"], list):
        return " ".join(str(a) for a in data["ProgramArguments"])
    if "Program" in data:
        return str(data["Program"])
    return ""


def list_launchagent_entries() -> list[dict[str, Any]]:
    """LaunchAgents 디렉토리의 모든 plist 항목을 반환한다."""
    entries: list[dict[str, Any]] = []
    for d in LAUNCH_AGENT_DIRS:
        if not d.is_dir():
            continue
        for plist in sorted(d.glob("*.plist")):
            # 손상/비표준 plist 한 개가 전체 목록을 깨뜨리지 않도록 개별 흡수
            try:
                with plist.open("rb") as f:
                    data = plistlib.load(f)
            except Exception:
                continue
            entries.append(
                {
                    "source": "launchagent",
                    "label": data.get("Label", plist.stem),
                    "plist_path": str(plist),
                    "command": _command_from_plist(data),
                    "next_run": _next_run_from_plist_data(data),
                }
            )
    return entries
