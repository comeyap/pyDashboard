"""Flask API 라우트 (REST).

프로젝트 CRUD, 상태 조회, 실행/중지, 시스템 스케줄 조회를 제공한다.
"""

from __future__ import annotations

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
