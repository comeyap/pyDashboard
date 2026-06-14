"""시스템 스케줄 자동 탐지 테스트 (cron/launchagent 등록 자동 채움)."""

from __future__ import annotations

from datetime import datetime

import pytest

from pydashboard import schedulers
from pydashboard.schedulers import cron, launchagents


@pytest.fixture
def fake_system(monkeypatch):
    """list_cron_entries / list_launchagent_entries 를 가짜 데이터로 대체."""
    nxt = datetime(2026, 6, 20, 9, 0).astimezone()

    def fake_cron():
        return [
            {
                "source": "cron",
                "expr": "0 9 * * 6",
                "command": "/Users/me/proj/.venv/bin/python /Users/me/proj/lotto.py",
                "next_run": nxt,
            }
        ]

    def fake_la():
        return [
            {
                "source": "launchagent",
                "label": "com.me.job",
                "plist_path": "/Users/me/Library/LaunchAgents/com.me.job.plist",
                "command": "/bin/bash /Users/me/proj/run_live.sh",
                "next_run": nxt,
            }
        ]

    monkeypatch.setattr(cron, "list_cron_entries", fake_cron)
    monkeypatch.setattr(launchagents, "list_launchagent_entries", fake_la)


def test_detect_cron(fake_system):
    det = schedulers.detect_for_script("/Users/me/proj/lotto.py")
    assert det is not None
    assert det["scheduler_type"] == "cron"
    assert det["schedule_expr"] == "0 9 * * 6"
    assert det["next_run"] is not None


def test_detect_launchagent(fake_system):
    det = schedulers.detect_for_script("/Users/me/proj/run_live.sh")
    assert det["scheduler_type"] == "launchagent"
    assert det["plist_path"].endswith("com.me.job.plist")


def test_detect_no_match(fake_system):
    assert schedulers.detect_for_script("/Users/me/proj/unrelated.py") is None


def test_detect_empty_path(fake_system):
    assert schedulers.detect_for_script("") is None


def test_detect_endpoint_found(client, fake_system):
    r = client.get("/api/system/detect?script_path=/Users/me/proj/lotto.py")
    data = r.get_json()
    assert data["found"] is True
    assert data["scheduler_type"] == "cron"
    assert data["schedule_expr"] == "0 9 * * 6"


def test_detect_endpoint_not_found(client, fake_system):
    r = client.get("/api/system/detect?script_path=/nope.py")
    assert r.get_json() == {"found": False}


def test_project_view_includes_detected(client, fake_system):
    # cron 타입 프로젝트 등록 후, 조회(리프레시) 시 detected 반영
    pid = client.post(
        "/api/projects",
        json={
            "name": "lotto",
            "script_path": "/Users/me/proj/lotto.py",
            "scheduler_type": "cron",
        },
    ).get_json()["id"]

    view = client.get(f"/api/projects/{pid}").get_json()
    assert view["detected"] is not None
    assert view["detected"]["schedule_expr"] == "0 9 * * 6"
    assert view["next_run"] is not None  # 자동 매칭으로 다음 실행 계산됨
