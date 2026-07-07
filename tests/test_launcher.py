"""원클릭 실행 관련 테스트 — 브라우저 자동 열기 + 단독앱 창 모드 + 런처 스크립트 무결성."""

from __future__ import annotations

import os
import subprocess
import threading
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


def test_should_use_window_default(monkeypatch):
    monkeypatch.delenv("PYDASHBOARD_WINDOW", raising=False)
    assert app_module._should_use_window() is True


def test_should_use_window_disabled(monkeypatch):
    monkeypatch.setenv("PYDASHBOARD_WINDOW", "0")
    assert app_module._should_use_window() is False


def test_import_webview_missing_falls_back_to_none(monkeypatch):
    def raise_import_error(name):
        raise ImportError(name)

    monkeypatch.setattr(app_module.importlib, "import_module", raise_import_error)
    assert app_module._import_webview() is None


def test_import_webview_present(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(app_module.importlib, "import_module", lambda name: sentinel)
    assert app_module._import_webview() is sentinel


def test_run_window_creates_window_then_starts():
    calls = []

    class FakeWebview:
        def create_window(self, title, url, **kwargs):
            calls.append(("create", title, url))

        def start(self):
            calls.append(("start",))

    app_module.run_window(FakeWebview(), "http://127.0.0.1:8800")
    assert calls == [("create", "Pydashboard", "http://127.0.0.1:8800"), ("start",)]


def test_start_server_thread_runs_flask_app_as_daemon():
    ran = threading.Event()

    class FakeApp:
        def run(self, host, port, use_reloader):
            assert use_reloader is False, "창 모드에서 리로더는 꺼져야 한다"
            ran.set()

    thread = app_module.start_server_thread(FakeApp(), "127.0.0.1", 0)
    assert ran.wait(2)
    thread.join(2)
    assert thread.daemon is True


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
