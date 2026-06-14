"""스케줄러 파싱 패키지.

OS 레벨 스케줄러(cron, macOS LaunchAgents)를 파싱하여 차기 실행 일시를
계산하고, 등록된 프로젝트와 매칭한다.
"""

from __future__ import annotations

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


def find_system_schedule(script_path: str) -> Optional[dict[str, Any]]:
    """시스템 스케줄 전체에서 script_path 를 포함하는 첫 항목을 반환한다."""
    for entry in list_system_schedules():
        if script_path and script_path in entry.get("command", ""):
            return entry
    return None


def list_system_schedules() -> list[dict[str, Any]]:
    """OS 에 등록된 모든 스케줄(cron + LaunchAgents)을 통합 반환한다.

    F-301: 시스템 스케줄러 파싱 결과를 UI 가 그대로 보여줄 수 있도록 한다.
    """
    entries: list[dict[str, Any]] = []
    entries.extend(cron.list_cron_entries())
    entries.extend(launchagents.list_launchagent_entries())
    return entries
