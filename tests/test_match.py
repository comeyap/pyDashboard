"""스크립트↔시스템 스케줄 명령 매칭 테스트.

실제 사용자 크론 등록 형태(`cd <dir> && python <상대경로>`)를 정확히 재현한다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from pydashboard import schedulers
from pydashboard.schedulers import cron, launchagents

# 사용자가 다른 머신에 등록한 실제 크론 라인
REAL_CRON_LINE = (
    "0 10 * * 6 cd /Users/kylemacmini/dev/workspace/AutoLottery && "
    "/Users/kylemacmini/dev/workspace/AutoLottery/.venv/bin/python3 AutoLotteryKyle.py"
)
SCRIPT_ABS = "/Users/kylemacmini/dev/workspace/AutoLottery/AutoLotteryKyle.py"


@pytest.fixture
def real_cron(monkeypatch):
    entries = cron.parse_crontab_text(REAL_CRON_LINE)
    monkeypatch.setattr(cron, "list_cron_entries", lambda: entries)
    monkeypatch.setattr(launchagents, "list_launchagent_entries", lambda: [])
    return entries


def test_crontab_line_parsed():
    entries = cron.parse_crontab_text(REAL_CRON_LINE)
    assert len(entries) == 1
    assert entries[0]["expr"] == "0 10 * * 6"
    assert "AutoLotteryKyle.py" in entries[0]["command"]
    assert entries[0]["next_run"] is not None


def test_command_matches_cd_relative_pattern():
    # cd <dir> && python <상대경로> 형태 — 절대경로가 통째로 들어있지 않아도 매칭
    cmd = (
        "cd /Users/kylemacmini/dev/workspace/AutoLottery && "
        "/Users/kylemacmini/dev/workspace/AutoLottery/.venv/bin/python3 AutoLotteryKyle.py"
    )
    assert schedulers._command_matches_script(cmd, SCRIPT_ABS) is True


def test_command_matches_absolute():
    cmd = "/usr/bin/python3 /Users/kylemacmini/dev/workspace/AutoLottery/AutoLotteryKyle.py"
    assert schedulers._command_matches_script(cmd, SCRIPT_ABS) is True


def test_command_no_false_positive_same_basename_diff_dir():
    # 같은 파일명이지만 다른 디렉토리 → 매칭 안 됨
    cmd = "cd /other/place && python3 AutoLotteryKyle.py"
    assert schedulers._command_matches_script(cmd, SCRIPT_ABS) is False


def test_command_no_match_unrelated():
    cmd = "cd /Users/kylemacmini/dev/workspace/AutoLottery && python3 other.py"
    assert schedulers._command_matches_script(cmd, SCRIPT_ABS) is False


def test_find_system_schedule_with_real_line(real_cron):
    entry = schedulers.find_system_schedule(SCRIPT_ABS)
    assert entry is not None
    assert entry["expr"] == "0 10 * * 6"


def test_detect_for_script_with_real_line(real_cron):
    det = schedulers.detect_for_script(SCRIPT_ABS)
    assert det is not None
    assert det["scheduler_type"] == "cron"
    assert det["schedule_expr"] == "0 10 * * 6"
    assert det["next_run"] is not None


def test_detect_endpoint_with_real_line(client, real_cron):
    r = client.get(f"/api/system/detect?script_path={SCRIPT_ABS}")
    data = r.get_json()
    assert data["found"] is True
    assert data["schedule_expr"] == "0 10 * * 6"
