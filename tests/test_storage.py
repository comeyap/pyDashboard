"""storage 모듈 테스트 — 프로젝트 등록 CRUD 및 검증."""

from __future__ import annotations

import pytest

from pydashboard import storage


def test_add_and_list():
    p = storage.add_project({"name": "잡A", "script_path": "/tmp/a.py"})
    assert p["id"]
    assert p["name"] == "잡A"
    projects = storage.list_projects()
    assert len(projects) == 1
    assert projects[0]["id"] == p["id"]


def test_add_requires_name():
    with pytest.raises(ValueError):
        storage.add_project({"script_path": "/tmp/a.py"})


def test_add_requires_script_or_command():
    # 이름만 있고 script_path/command 둘 다 없으면 실패
    with pytest.raises(ValueError):
        storage.add_project({"name": "잡"})


def test_command_only_is_valid():
    # script_path 없어도 command 만 있으면 통과
    p = storage.add_project({"name": "스트림릿", "command": "streamlit run app.py"})
    assert p["command"] == "streamlit run app.py"
    assert p["script_path"] == ""


def test_args_string_is_split():
    p = storage.add_project(
        {"name": "잡", "script_path": "/tmp/a.py", "args": "--mode prod --x 1"}
    )
    assert p["args"] == ["--mode", "prod", "--x", "1"]


def test_invalid_scheduler_type_falls_back_to_manual():
    p = storage.add_project(
        {"name": "잡", "script_path": "/tmp/a.py", "scheduler_type": "weird"}
    )
    assert p["scheduler_type"] == "manual"


def test_get_update_delete():
    p = storage.add_project({"name": "원본", "script_path": "/tmp/a.py"})
    pid = p["id"]

    assert storage.get_project(pid)["name"] == "원본"

    updated = storage.update_project(pid, {"name": "수정", "script_path": "/tmp/b.py"})
    assert updated["name"] == "수정"
    assert updated["script_path"] == "/tmp/b.py"
    assert updated["id"] == pid  # id 보존
    assert updated["created_at"] == p["created_at"]  # 생성시각 보존

    assert storage.delete_project(pid) is True
    assert storage.get_project(pid) is None
    assert storage.delete_project(pid) is False  # 이미 삭제됨


def test_update_missing_returns_none():
    assert storage.update_project("nope", {"name": "x", "script_path": "/tmp/a.py"}) is None
