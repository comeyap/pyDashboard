"""schedulers 모듈 테스트 — cron/launchagent 파싱 및 차기 실행 계산."""

from __future__ import annotations

from datetime import datetime

from pydashboard.schedulers import cron, launchagents


# ---- cron ----

def test_cron_next_run_daily_midnight():
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    nxt = cron.next_run_from_expr("0 0 * * *", base)
    assert nxt is not None
    assert (nxt.year, nxt.month, nxt.day, nxt.hour, nxt.minute) == (2026, 6, 15, 0, 0)


def test_cron_next_run_every_15min():
    base = datetime(2026, 6, 14, 10, 3).astimezone()
    nxt = cron.next_run_from_expr("*/15 * * * *", base)
    assert (nxt.hour, nxt.minute) == (10, 15)


def test_cron_invalid_returns_none():
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    assert cron.next_run_from_expr("99 99 * * *", base) is None


def test_cron_next_run_is_timezone_aware():
    # 시스템 타임존 기준으로 계산되어야 한다 (tzinfo 존재 + offset 포함 ISO)
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    nxt = cron.next_run_from_expr("0 0 * * *", base)
    assert nxt.tzinfo is not None
    assert nxt.utcoffset() == base.utcoffset()
    # isoformat 에 오프셋 표기가 있어야 프론트가 로컬 타임존으로 렌더 가능
    assert "+" in nxt.isoformat() or "-" in nxt.isoformat()[11:]


def test_cron_saturday_lands_on_saturday():
    # `0 10 * * 6` 은 토요일 → weekday()==5 (월=0..일=6)
    base = datetime(2026, 6, 14, 10, 0).astimezone()  # 2026-06-14 는 일요일
    nxt = cron.next_run_from_expr("0 10 * * 6", base)
    assert nxt.weekday() == 5
    assert (nxt.hour, nxt.minute) == (10, 0)


def test_parse_crontab_text_skips_comments_and_env():
    text = "\n".join(
        [
            "# 주석",
            "SHELL=/bin/sh",
            "PATH=/usr/bin",
            "0 2 * * * /usr/bin/python3 /opt/job/backup.py",
            "*/15 * * * * /opt/venv/bin/python /opt/poll.py --fast",
        ]
    )
    entries = cron.parse_crontab_text(text)
    assert len(entries) == 2
    assert entries[0]["expr"] == "0 2 * * *"
    assert entries[0]["command"] == "/usr/bin/python3 /opt/job/backup.py"
    assert entries[0]["source"] == "cron"
    assert entries[0]["next_run"] is not None
    assert entries[1]["command"].endswith("--fast")


def test_parse_crontab_empty():
    assert cron.parse_crontab_text("") == []


# ---- launchagents ----

def test_calendar_interval_to_cron():
    expr = launchagents._calendar_interval_to_cron({"Hour": 3, "Minute": 5})
    assert expr == "5 3 * * *"


def test_launchagent_calendar_next_run():
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    nxt = launchagents._next_run_from_plist_data(
        {"StartCalendarInterval": {"Hour": 3, "Minute": 0}}, base
    )
    assert (nxt.year, nxt.month, nxt.day, nxt.hour) == (2026, 6, 15, 3)


def test_launchagent_calendar_list_takes_earliest():
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    nxt = launchagents._next_run_from_plist_data(
        {"StartCalendarInterval": [{"Hour": 23}, {"Hour": 12}]}, base
    )
    # 둘 중 가장 가까운 미래(오늘 12시)
    assert (nxt.day, nxt.hour) == (14, 12)


def test_launchagent_interval_approximation():
    base = datetime(2026, 6, 14, 10, 0).astimezone()
    nxt = launchagents._next_run_from_plist_data({"StartInterval": 3600}, base)
    assert (nxt.hour, nxt.minute) == (11, 0)


def test_launchagent_no_schedule_returns_none():
    assert launchagents._next_run_from_plist_data({"RunAtLoad": True}) is None


def test_command_from_plist():
    cmd = launchagents._command_from_plist(
        {"ProgramArguments": ["/bin/bash", "/opt/run.sh"]}
    )
    assert cmd == "/bin/bash /opt/run.sh"
    assert launchagents._command_from_plist({"Program": "/opt/x"}) == "/opt/x"


def test_next_run_from_missing_plist_returns_none():
    assert launchagents.next_run_from_plist("/nonexistent/x.plist") is None
