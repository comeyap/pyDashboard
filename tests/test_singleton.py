"""단일 인스턴스 보장 테스트 — 이미 실행 중이면 브라우저만 열기."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import app as app_module


class _PingHandler(BaseHTTPRequestHandler):
    """테스트용 미니 서버: /api/ping 에 지정된 JSON 을 응답."""

    payload = {"app": "pydashboard", "version": "test"}

    def do_GET(self):
        if self.path == "/api/ping":
            body = json.dumps(self.payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # 테스트 로그 소음 제거
        pass


@pytest.fixture
def ping_server():
    """app=='pydashboard' 로 응답하는 임시 서버."""
    _PingHandler.payload = {"app": "pydashboard", "version": "test"}
    srv = HTTPServer(("127.0.0.1", 0), _PingHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


@pytest.fixture
def foreign_server():
    """Pydashboard 가 아닌 다른 앱처럼 응답하는 임시 서버."""
    _PingHandler.payload = {"app": "something-else"}
    srv = HTTPServer(("127.0.0.1", 0), _PingHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


# ---- /api/ping 엔드포인트 ----

def test_ping_endpoint(client):
    data = client.get("/api/ping").get_json()
    assert data["app"] == "pydashboard"
    assert "version" in data


# ---- is_pydashboard_running ----

def test_running_true_for_our_instance(ping_server):
    assert app_module.is_pydashboard_running("127.0.0.1", ping_server) is True


def test_running_false_for_foreign_app(foreign_server):
    assert app_module.is_pydashboard_running("127.0.0.1", foreign_server) is False


def test_running_false_when_nothing(tmp_path):
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert app_module.is_pydashboard_running("127.0.0.1", port) is False


# ---- lock 파일 ----

def test_lock_roundtrip():
    app_module._write_lock("127.0.0.1", 8800)
    assert app_module._read_lock()["port"] == 8800
    app_module._clear_lock()
    assert app_module._read_lock() == {}


# ---- find_existing_instance ----

def test_find_existing_via_lock(ping_server):
    app_module._write_lock("127.0.0.1", ping_server)
    assert app_module.find_existing_instance("127.0.0.1", 9999) == ping_server


def test_find_existing_via_preferred(ping_server):
    # lock 없음 + preferred 포트에 우리 인스턴스
    assert app_module.find_existing_instance("127.0.0.1", ping_server) == ping_server


def test_find_existing_none_when_not_running():
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert app_module.find_existing_instance("127.0.0.1", port) is None


def test_stale_lock_is_cleared():
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    dead_port = s.getsockname()[1]
    s.close()

    app_module._write_lock("127.0.0.1", dead_port)
    # 그 포트엔 아무도 없음 → None 반환 + stale lock 제거
    assert app_module.find_existing_instance("127.0.0.1", dead_port) is None
    assert app_module._read_lock() == {}
