"""원클릭 실행 관련 테스트 — 브라우저 자동 열기 + 런처 스크립트 무결성."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parent.parent


def test_should_open_browser_default(monkeypatch):
    monkeypatch.delenv("PYDASHBOARD_NO_BROWSER", raising=False)
    assert app_module._should_open_browser() is True


def test_should_open_browser_disabled(monkeypatch):
    monkeypatch.setenv("PYDASHBOARD_NO_BROWSER", "1")
    assert app_module._should_open_browser() is False


def test_open_browser_later_calls_webbrowser(monkeypatch):
    monkeypatch.delenv("PYDASHBOARD_NO_BROWSER", raising=False)
    opened = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda url: opened.append(url))
    timer = app_module.open_browser_later("http://127.0.0.1:8800", delay=0.01)
    assert timer is not None
    timer.join(2)
    assert opened == ["http://127.0.0.1:8800"]


def test_open_browser_later_respects_disable(monkeypatch):
    monkeypatch.setenv("PYDASHBOARD_NO_BROWSER", "1")
    opened = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda url: opened.append(url))
    assert app_module.open_browser_later("http://x", delay=0.01) is None
    assert opened == []


def test_launcher_command_exists_and_executable():
    cmd = ROOT / "Pydashboard.command"
    assert cmd.is_file()
    assert os.access(cmd, os.X_OK), "Pydashboard.command 는 실행 권한이 있어야 한다"


def test_launcher_command_valid_bash_syntax():
    cmd = ROOT / "Pydashboard.command"
    # bash -n: 실행하지 않고 문법만 검사
    result = subprocess.run(["bash", "-n", str(cmd)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_build_app_script_valid_syntax():
    script = ROOT / "scripts" / "build_macos_app.sh"
    assert script.is_file()
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
