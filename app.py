"""Pydashboard 애플리케이션 진입점.

실행:
    python app.py
    PYDASHBOARD_PORT=8800 python app.py

원클릭 실행:
    Finder 에서 Pydashboard.command 더블클릭 (macOS)
"""

from __future__ import annotations

import os
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
    port = int(os.environ.get("PYDASHBOARD_PORT", "8800"))
    host = os.environ.get("PYDASHBOARD_HOST", "127.0.0.1")
    debug = os.environ.get("PYDASHBOARD_DEBUG", "0") == "1"

    # 디버그(리로더) 모드에서는 중복 오픈을 피하기 위해 자동 열기 생략
    if not debug:
        display_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
        open_browser_later(f"http://{display_host}:{port}")

    app.run(host=host, port=port, debug=debug)
