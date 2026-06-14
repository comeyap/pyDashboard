"""스케줄러 파싱 패키지.

OS 레벨 스케줄러(cron, macOS LaunchAgents)를 파싱하여 차기 실행 일시를
계산하고, 등록된 프로젝트와 매칭한다.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from . import cron, launchagents


def next_run_for_project(project: dict[str, Any]) -> Optional[datetime]:
    """프로젝트의 차기 실행 일시를 계산한다.

    우선순위:
      1) 명시적 schedule_expr (cron) / plist_path (launchagent)
      2) 시스템 스케줄에서 script_path 로 자동 매칭
    """
    stype = project.get("scheduler_type", "manual")

    if stype == "cron":
        expr = project.get("schedule_expr", "").strip()
        if expr:
            return cron.next_run_from_expr(expr)

    if stype == "launchagent":
        plist = project.get("plist_path", "").strip()
        if plist:
            return launchagents.next_run_from_plist(plist)

    # 자동 매칭: 시스템 스케줄을 훑어 script_path 가 포함된 항목을 찾는다.
    script_path = project.get("script_path", "").strip()
    if script_path:
        match = find_system_schedule(script_path)
        if match and match.get("next_run"):
            return match["next_run"]

    return None


def _command_matches_script(command: str, script_path: str) -> bool:
    """스케줄 명령(command)이 해당 스크립트를 실행하는지 판정한다.

    단순히 절대경로가 통째로 들어있는 경우뿐 아니라, crontab 에서 흔한
    `cd <dir> && python <상대경로>` 형태도 매칭한다.

    규칙:
      1) 절대경로(또는 realpath)가 명령에 그대로 포함 → 매칭
      2) 스크립트 '파일명'과 '디렉토리'가 둘 다 명령에 포함 → 매칭
         (cd <dir> 로 이동 후 상대경로로 실행하는 패턴)
    같은 파일명이라도 디렉토리가 다르면 매칭되지 않아 오탐을 막는다.
    """
    if not command or not script_path:
        return False

    if script_path in command:
        return True

    real = os.path.realpath(script_path)
    if real != script_path and real in command:
        return True

    base = os.path.basename(script_path)
    dirn = os.path.dirname(script_path)
    if base and dirn and base in command and dirn in command:
        return True

    return False


def find_system_schedule(script_path: str) -> Optional[dict[str, Any]]:
    """시스템 스케줄 전체에서 script_path 를 실행하는 첫 항목을 반환한다."""
    if not script_path:
        return None
    for entry in list_system_schedules():
        if _command_matches_script(entry.get("command", ""), script_path):
            return entry
    return None


def detect_for_script(script_path: str) -> Optional[dict[str, Any]]:
    """script_path 로 OS 에 이미 등록된 스케줄을 탐지해 정규화 반환한다.

    프로젝트 등록 시 'cron/launchagent 선택 → 로컬 1회 조회 후 자동 채움'에 사용.
    매칭 항목이 없으면 None.
    """
    if not script_path:
        return None
    entry = find_system_schedule(script_path)
    if not entry:
        return None

    result: dict[str, Any] = {
        "source": entry.get("source"),
        "command": entry.get("command"),
        "next_run": entry.get("next_run"),
    }
    if entry.get("source") == "cron":
        result["scheduler_type"] = "cron"
        result["schedule_expr"] = entry.get("expr", "")
    elif entry.get("source") == "launchagent":
        result["scheduler_type"] = "launchagent"
        result["plist_path"] = entry.get("plist_path", "")
        result["label"] = entry.get("label", "")
    return result


def list_system_schedules() -> list[dict[str, Any]]:
    """OS 에 등록된 모든 스케줄(cron + LaunchAgents)을 통합 반환한다.

    F-301: 시스템 스케줄러 파싱 결과를 UI 가 그대로 보여줄 수 있도록 한다.
    """
    entries: list[dict[str, Any]] = []
    entries.extend(cron.list_cron_entries())
    entries.extend(launchagents.list_launchagent_entries())
    return entries
