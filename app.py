"""Pydashboard 애플리케이션 진입점.

실행:
    python app.py
    PYDASHBOARD_PORT=8800 python app.py

원클릭 실행:
    Finder 에서 Pydashboard.command 더블클릭 (macOS)
"""

from __future__ import annotations

import atexit
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import psutil
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
    """해당 host:port 에 바인드할 수 있으면 True(사용 가능).

    bind 시도로 판정한다 → app.run(Werkzeug) 이 실제로 띄울 수 있는지와 동일 기준.
    Werkzeug 처럼 SO_REUSEADDR 를 설정해 TIME_WAIT 잔여 소켓은 '사용 가능'으로 보되,
    활성 리스너가 있으면 EADDRINUSE 로 '사용 중' 판정된다.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((_bind_host(host), port))
            return True
        except OSError:
            return False


def resolve_port(host: str, preferred: int, max_tries: int = 20) -> int:
    """preferred 가 사용 중이면 그 다음 빈 포트를 찾아 반환한다."""
    for p in range(preferred, preferred + max_tries):
        if is_port_free(host, p):
            return p
    # 모두 사용 중이면 OS 가 임의의 빈 포트를 할당하도록 한다.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((_bind_host(host), 0))
        return s.getsockname()[1]


def is_pydashboard_running(host: str, port: int, timeout: float = 0.5) -> bool:
    """host:port 에 떠 있는 서버가 'Pydashboard' 인스턴스인지 확인한다.

    /api/ping 응답의 app 필드로 식별 → 다른 프로그램(예: 8800을 쓰는 무관한 앱)을
    우리 인스턴스로 오인하지 않는다.
    """
    url = f"http://{_bind_host(host)}:{port}/api/ping"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("app") == "pydashboard"
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return False


def _read_lock() -> dict:
    try:
        with open(config.SERVER_LOCK, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_lock(host: str, port: int) -> None:
    config.ensure_dirs()
    try:
        with open(config.SERVER_LOCK, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "host": host, "port": port}, f)
    except OSError:
        pass


def _clear_lock() -> None:
    try:
        os.remove(config.SERVER_LOCK)
    except OSError:
        pass


def find_existing_instance(host: str, preferred: int) -> int | None:
    """이미 실행 중인 Pydashboard 인스턴스의 포트를 반환한다. 없으면 None.

    1) lock 파일에 기록된 포트를 우선 확인 (포트 자동전환된 경우 대응)
    2) 그래도 없으면 preferred 포트를 확인
    살아있지 않은(stale) lock 은 정리한다.
    """
    lock = _read_lock()
    locked_port = lock.get("port")
    if isinstance(locked_port, int) and is_pydashboard_running(host, locked_port):
        return locked_port
    if locked_port is not None:
        _clear_lock()  # stale

    if is_pydashboard_running(host, preferred):
        return preferred
    return None


def _terminate_pid(pid: int, timeout: float = 5.0) -> bool:
    """pid(및 자식)를 SIGTERM→SIGKILL 로 종료한다. 종료 시도했으면 True."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False
    try:
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []
    targets = [proc, *children]
    for p in targets:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(targets, timeout=timeout)
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return True


def stop_existing_instance(host: str, preferred: int, timeout: float = 5.0) -> bool:
    """실행 중인 Pydashboard 인스턴스를 종료한다. 실제로 종료했으면 True.

    lock 의 pid/port 와 /api/ping 식별로 '우리 인스턴스'만 종료한다.
    살아있는 인스턴스가 없으면 stale lock 을 정리하고 False.
    """
    lock = _read_lock()
    pid = lock.get("pid")
    locked_port = lock.get("port")

    target_port = None
    if isinstance(locked_port, int) and is_pydashboard_running(host, locked_port):
        target_port = locked_port
    elif is_pydashboard_running(host, preferred):
        target_port = preferred

    if target_port is None:
        if lock:
            _clear_lock()
        return False

    killed = bool(isinstance(pid, int) and _terminate_pid(pid, timeout))
    _clear_lock()
    return killed


def wait_until_port_free(host: str, port: int, timeout: float = 5.0) -> bool:
    """port 가 비워질 때까지 대기. 비면 True, 타임아웃이면 False."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_free(host, port):
            return True
        time.sleep(0.1)
    return is_port_free(host, port)


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

    # 단일 인스턴스(재시작 방식): 기존 인스턴스가 있으면 종료하고 새로 시작한다.
    # → git pull 등으로 갱신된 최신 코드가 항상 반영되도록 보장.
    if stop_existing_instance(host, preferred):
        print("[Pydashboard] 기존 인스턴스를 종료하고 새로 시작합니다.")
        wait_until_port_free(host, preferred)

    # 포트가 (무관한 프로그램에 의해) 사용 중이면 자동으로 빈 포트를 찾는다.
    port = resolve_port(host, preferred)
    if port != preferred:
        print(f"[Pydashboard] 포트 {preferred} 사용 중 → {port} 으로 시작합니다.")

    url = f"http://{_bind_host(host)}:{port}"
    print(f"[Pydashboard] {url}")

    # 실행 중 표시(lock) 기록 + 종료 시 정리
    _write_lock(host, port)
    atexit.register(_clear_lock)

    # 디버그(리로더) 모드에서는 중복 오픈을 피하기 위해 자동 열기 생략
    if not debug:
        open_browser_later(url)

    app.run(host=host, port=port, debug=debug)
