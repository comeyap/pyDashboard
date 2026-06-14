"""프로젝트 등록 정보 저장소 (JSON 파일 기반 CRUD).

대시보드에 등록된 Python 프로젝트 메타데이터를 data/projects.json 에 보관한다.
동시 쓰기 충돌을 막기 위해 모듈 레벨 Lock 으로 직렬화하고, 임시 파일 + rename
으로 원자적 쓰기를 보장한다.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from . import config

_LOCK = threading.Lock()

# 등록 가능한 스케줄러 타입
SCHEDULER_TYPES = ("always_on", "cron", "launchagent", "manual")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_all() -> list[dict[str, Any]]:
    if not config.PROJECTS_FILE.exists():
        return []
    try:
        with config.PROJECTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write_all(projects: list[dict[str, Any]]) -> None:
    config.ensure_dirs()
    # 같은 디렉토리에 임시 파일을 만든 뒤 atomic rename
    fd, tmp_path = tempfile.mkstemp(dir=str(config.DATA_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, config.PROJECTS_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def list_projects() -> list[dict[str, Any]]:
    with _LOCK:
        return _read_all()


def get_project(project_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        for p in _read_all():
            if p.get("id") == project_id:
                return p
    return None


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """입력 payload 를 저장 스키마로 정규화한다."""
    scheduler_type = payload.get("scheduler_type", "manual")
    if scheduler_type not in SCHEDULER_TYPES:
        scheduler_type = "manual"

    args = payload.get("args", [])
    if isinstance(args, str):
        # 공백 구분 문자열도 허용
        args = args.split()
    if not isinstance(args, list):
        args = []

    return {
        "name": (payload.get("name") or "").strip(),
        "description": (payload.get("description") or "").strip(),
        "script_path": (payload.get("script_path") or "").strip(),
        "python_path": (payload.get("python_path") or "python3").strip() or "python3",
        "working_dir": (payload.get("working_dir") or "").strip(),
        "args": [str(a) for a in args],
        # 임의 실행 커맨드. 지정 시 python_path+script_path 대신 이 커맨드로 실행한다.
        # 예: "streamlit run app.py", "scripts/run_live.sh", "uv run python -m live"
        "command": (payload.get("command") or "").strip(),
        "scheduler_type": scheduler_type,
        # cron 표현식 (scheduler_type == cron). 예: "0 0 * * *"
        "schedule_expr": (payload.get("schedule_expr") or "").strip(),
        # plist 경로 (scheduler_type == launchagent)
        "plist_path": (payload.get("plist_path") or "").strip(),
    }


def _validate(data: dict[str, Any]) -> None:
    if not data["name"]:
        raise ValueError("프로젝트 이름은 필수입니다.")
    # 실행/식별을 위해 스크립트 경로 또는 커맨드 중 최소 하나는 필요하다.
    if not data["script_path"] and not data["command"]:
        raise ValueError("스크립트 경로 또는 실행 커맨드 중 하나는 필수입니다.")


def add_project(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize(payload)
    _validate(data)

    data["id"] = uuid.uuid4().hex
    data["created_at"] = _now_iso()

    with _LOCK:
        projects = _read_all()
        projects.append(data)
        _write_all(projects)
    return data


def update_project(project_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    data = _normalize(payload)
    _validate(data)

    with _LOCK:
        projects = _read_all()
        for i, p in enumerate(projects):
            if p.get("id") == project_id:
                data["id"] = project_id
                data["created_at"] = p.get("created_at", _now_iso())
                projects[i] = data
                _write_all(projects)
                return data
    return None


def delete_project(project_id: str) -> bool:
    with _LOCK:
        projects = _read_all()
        new = [p for p in projects if p.get("id") != project_id]
        if len(new) == len(projects):
            return False
        _write_all(new)
    return True
