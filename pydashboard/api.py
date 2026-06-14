"""Flask API 라우트 (REST).

프로젝트 CRUD, 상태 조회, 실행/중지, 시스템 스케줄 조회를 제공한다.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from . import config, process_manager, storage
from . import schedulers

api = Blueprint("api", __name__, url_prefix="/api")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def _project_view(project: dict[str, Any]) -> dict[str, Any]:
    """프로젝트 + 실시간 상태 + 차기 실행 일시를 합친 응답 뷰."""
    status = process_manager.get_status(project)
    next_run = schedulers.next_run_for_project(project)
    return {
        **project,
        "status": status,
        "next_run": _iso(next_run),
    }


@api.get("/config")
def get_config() -> Any:
    return jsonify(
        {
            "ui_poll_sec": config.UI_POLL_SEC,
            "schedule_refresh_sec": config.SCHEDULE_REFRESH_SEC,
        }
    )


@api.get("/projects")
def list_projects() -> Any:
    views = [_project_view(p) for p in storage.list_projects()]
    return jsonify(views)


@api.post("/projects")
def create_project() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        project = storage.add_project(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_project_view(project)), 201


@api.get("/projects/<project_id>")
def get_project(project_id: str) -> Any:
    project = storage.get_project(project_id)
    if not project:
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    return jsonify(_project_view(project))


@api.put("/projects/<project_id>")
def update_project(project_id: str) -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        project = storage.update_project(project_id, payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not project:
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    return jsonify(_project_view(project))


@api.delete("/projects/<project_id>")
def delete_project(project_id: str) -> Any:
    if not storage.delete_project(project_id):
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    return jsonify({"ok": True})


@api.post("/projects/<project_id>/run")
def run_project(project_id: str) -> Any:
    project = storage.get_project(project_id)
    if not project:
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    try:
        result = process_manager.start(project)
    except process_manager.ProcessError as exc:
        # 중복 실행 등은 409 Conflict
        return jsonify({"error": str(exc)}), 409
    return jsonify(result)


@api.post("/projects/<project_id>/stop")
def stop_project(project_id: str) -> Any:
    project = storage.get_project(project_id)
    if not project:
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    try:
        result = process_manager.stop(project)
    except process_manager.ProcessError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(result)


@api.get("/projects/<project_id>/logs")
def project_logs(project_id: str) -> Any:
    project = storage.get_project(project_id)
    if not project:
        return jsonify({"error": "프로젝트를 찾을 수 없습니다."}), 404
    lines = request.args.get("lines", default=100, type=int)
    return jsonify({"log": process_manager.tail_log(project, lines=lines)})


@api.get("/fs")
def browse_fs() -> Any:
    """서버측 파일시스템 탐색 (경로 선택용 '찾아보기').

    로컬 대시보드(127.0.0.1 바인딩) 전용 편의 기능. 주어진 디렉토리의
    하위 폴더와 파일 목록을 반환한다. path 미지정 시 홈 디렉토리.
    """
    raw = request.args.get("path", "").strip()
    base = os.path.expanduser(raw) if raw else os.path.expanduser("~")
    base = os.path.abspath(base)

    # 파일이 지정되면 그 부모 디렉토리를 보여준다.
    if os.path.isfile(base):
        base = os.path.dirname(base)
    if not os.path.isdir(base):
        return jsonify({"error": f"디렉토리가 아닙니다: {base}"}), 400

    dirs: list[dict[str, str]] = []
    files: list[dict[str, str]] = []
    try:
        with os.scandir(base) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue  # 숨김 항목 제외
                full = os.path.join(base, entry.name)
                try:
                    if entry.is_dir():
                        dirs.append({"name": entry.name, "path": full})
                    elif entry.is_file():
                        files.append({"name": entry.name, "path": full})
                except OSError:
                    continue
    except PermissionError:
        return jsonify({"error": f"접근 권한이 없습니다: {base}"}), 403

    dirs.sort(key=lambda d: d["name"].lower())
    files.sort(key=lambda f: f["name"].lower())
    parent = os.path.dirname(base)
    return jsonify(
        {
            "path": base,
            "parent": parent if parent != base else None,
            "dirs": dirs,
            "files": files,
        }
    )


@api.get("/system/schedules")
def system_schedules() -> Any:
    """OS 에 등록된 cron + LaunchAgents 스케줄 전체 (F-301)."""
    entries = []
    for e in schedulers.list_system_schedules():
        entries.append(
            {
                "source": e.get("source"),
                "label": e.get("label"),
                "expr": e.get("expr"),
                "command": e.get("command"),
                "plist_path": e.get("plist_path"),
                "next_run": _iso(e.get("next_run")),
            }
        )
    return jsonify(entries)
