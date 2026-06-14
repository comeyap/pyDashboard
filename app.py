"""Pydashboard 애플리케이션 진입점.

실행:
    python app.py
    PYDASHBOARD_PORT=8800 python app.py

원클릭 실행:
    Finder 에서 Pydashboard.command 더블클릭 (macOS)
"""

from __future__ import annotations

import os
import socket
import threading
import webbrowser

from flask import Flask, render_template

from pydashboard import config
from pydashboard.api import api


def create_app() -> Flask:
    config.ensure_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.register_blueprint(api)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    return app


def _bind_host(host: str) -> str:
    """연결 테스트용 호스트. 0.0.0.0/빈 값은 127.0.0.1 로 본다."""
    return "127.0.0.1" if host in ("0.0.0.0", "") else host


def is_port_free(host: str, port: int) -> bool:
    """해당 host:port 에 리스닝 중인 서버가 없으면 True(사용 가능)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        # connect_ex == 0 이면 누군가 리스닝 중(=사용 중)
        return s.connect_ex((_bind_host(host), port)) != 0


def resolve_port(host: str, preferred: int, max_tries: int = 20) -> int:
    """preferred 가 사용 중이면 그 다음 빈 포트를 찾아 반환한다."""
    for p in range(preferred, preferred + max_tries):
        if is_port_free(host, p):
            return p
    # 모두 사용 중이면 OS 가 임의의 빈 포트를 할당하도록 한다.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((_bind_host(host), 0))
        return s.getsockname()[1]


def _should_open_browser() -> bool:
    """브라우저 자동 열기 여부. PYDASHBOARD_NO_BROWSER=1 이면 끈다."""
    return os.environ.get("PYDASHBOARD_NO_BROWSER", "0") != "1"


def open_browser_later(url: str, delay: float = 1.2):
    """서버 기동 후 url 을 기본 브라우저로 연다. 끈 경우 None 반환."""
    if not _should_open_browser():
        return None
    timer = threading.Timer(delay, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()
    return timer


app = create_app()


if __name__ == "__main__":
    preferred = int(os.environ.get("PYDASHBOARD_PORT", "8800"))
    host = os.environ.get("PYDASHBOARD_HOST", "127.0.0.1")
    debug = os.environ.get("PYDASHBOARD_DEBUG", "0") == "1"

    # 포트가 이미 사용 중이면 자동으로 빈 포트를 찾는다.
    port = resolve_port(host, preferred)
    if port != preferred:
        print(f"[Pydashboard] 포트 {preferred} 사용 중 → {port} 으로 시작합니다.")

    url = f"http://{_bind_host(host)}:{port}"
    print(f"[Pydashboard] {url}")

    # 디버그(리로더) 모드에서는 중복 오픈을 피하기 위해 자동 열기 생략
    if not debug:
        open_browser_later(url)

    app.run(host=host, port=port, debug=debug)
