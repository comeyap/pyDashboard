"""포트 자동 탐색 테스트 — 사용 중인 포트를 피해 시작."""

from __future__ import annotations

import socket

import pytest

import app as app_module


@pytest.fixture
def listening_socket():
    """임의의 빈 포트에 리스닝 소켓을 열어 '사용 중' 상태를 만든다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    yield port
    s.close()


def test_is_port_free_when_nothing_listening():
    # OS 가 준 임시 포트를 즉시 닫으면 free 여야 한다
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()
    assert app_module.is_port_free("127.0.0.1", free_port) is True


def test_is_port_free_false_when_in_use(listening_socket):
    assert app_module.is_port_free("127.0.0.1", listening_socket) is False


def test_resolve_port_returns_preferred_when_free():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()
    assert app_module.resolve_port("127.0.0.1", free_port) == free_port


def test_resolve_port_skips_busy_port(listening_socket):
    # 사용 중인 포트를 preferred 로 주면 다른(빈) 포트를 돌려줘야 한다
    resolved = app_module.resolve_port("127.0.0.1", listening_socket)
    assert resolved != listening_socket
    assert app_module.is_port_free("127.0.0.1", resolved) is True


def test_bind_host_normalizes_wildcard():
    assert app_module._bind_host("0.0.0.0") == "127.0.0.1"
    assert app_module._bind_host("") == "127.0.0.1"
    assert app_module._bind_host("192.168.0.5") == "192.168.0.5"
