"""api 모듈 테스트 — REST 엔드포인트."""

from __future__ import annotations

import time


def test_empty_projects(client):
    assert client.get("/api/projects").get_json() == []


def test_config_endpoint(client):
    cfg = client.get("/api/config").get_json()
    assert "ui_poll_sec" in cfg
    assert "schedule_refresh_sec" in cfg


def test_crud_flow(client):
    r = client.post("/api/projects", json={"name": "잡", "script_path": "/tmp/a.py"})
    assert r.status_code == 201
    pid = r.get_json()["id"]

    assert client.get(f"/api/projects/{pid}").status_code == 200

    r = client.put(f"/api/projects/{pid}", json={"name": "수정", "script_path": "/tmp/b.py"})
    assert r.status_code == 200
    assert r.get_json()["name"] == "수정"

    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_create_validation_error(client):
    assert client.post("/api/projects", json={"script_path": "/x"}).status_code == 400
    assert client.post("/api/projects", json={"name": "x"}).status_code == 400


def test_run_missing_script_409(client):
    pid = client.post(
        "/api/projects", json={"name": "bad", "script_path": "/nonexistent/x.py"}
    ).get_json()["id"]
    assert client.post(f"/api/projects/{pid}/run").status_code == 409


def test_run_stop_lifecycle(client, sleeper_script, py_executable):
    pid = client.post(
        "/api/projects",
        json={"name": "s", "script_path": sleeper_script, "python_path": py_executable},
    ).get_json()["id"]

    assert client.post(f"/api/projects/{pid}/run").status_code == 200
    time.sleep(1.0)
    st = client.get(f"/api/projects/{pid}").get_json()["status"]
    assert st["state"] == "running"
    # 중복 실행 차단
    assert client.post(f"/api/projects/{pid}/run").status_code == 409

    log = client.get(f"/api/projects/{pid}/logs").get_json()["log"]
    assert "sleeper up" in log

    assert client.post(f"/api/projects/{pid}/stop").status_code == 200


def test_run_nonexistent_project_404(client):
    assert client.post("/api/projects/nope/run").status_code == 404


# ---- 파일 탐색기 ----

def test_fs_browse_tmp(client, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "file.py").write_text("x")
    data = client.get(f"/api/fs?path={tmp_path}").get_json()
    assert data["path"] == str(tmp_path)
    assert any(d["name"] == "sub" for d in data["dirs"])
    assert any(f["name"] == "file.py" for f in data["files"])


def test_fs_default_is_home(client):
    import os

    data = client.get("/api/fs").get_json()
    assert data["path"] == os.path.expanduser("~")


def test_fs_file_path_goes_to_parent(client, tmp_path):
    f = tmp_path / "x.py"
    f.write_text("y")
    data = client.get(f"/api/fs?path={f}").get_json()
    assert data["path"] == str(tmp_path)


def test_fs_invalid_dir_400(client):
    assert client.get("/api/fs?path=/no/such/dir/xyz").status_code == 400


def test_system_schedules_ok(client):
    # 실제 시스템 파싱 — 예외 없이 200 + 리스트
    r = client.get("/api/system/schedules")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)
