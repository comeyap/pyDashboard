"""pytest 공용 fixture.

모든 테스트는 실제 사용자 데이터(data/projects.json 등)를 건드리지 않도록
config 의 데이터 경로를 tmp_path 로 격리한다.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# 프로젝트 루트를 import 경로에 추가
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydashboard import config  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path, monkeypatch):
    """config 의 런타임 경로를 테스트별 임시 디렉토리로 교체한다."""
    data = tmp_path / "data"
    pid = data / "pids"
    log = data / "logs"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "PID_DIR", pid)
    monkeypatch.setattr(config, "LOG_DIR", log)
    monkeypatch.setattr(config, "PROJECTS_FILE", data / "projects.json")
    config.ensure_dirs()
    yield


@pytest.fixture
def client():
    """Flask 테스트 클라이언트."""
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture
def sleeper_script(tmp_path):
    """잠깐 sleep 하는 더미 파이썬 스크립트 경로를 만든다."""
    script = tmp_path / "sleeper.py"
    script.write_text(
        textwrap.dedent(
            """
            import time
            print("sleeper up", flush=True)
            time.sleep(30)
            """
        ).strip()
    )
    return str(script)


@pytest.fixture
def py_executable():
    """현재 파이썬 인터프리터 절대경로."""
    return sys.executable
