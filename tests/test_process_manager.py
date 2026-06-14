"""process_manager 모듈 테스트 — 실행/중지/상태/식별."""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from pydashboard import process_manager as pm
from pydashboard import storage


def _wait_state(project, state, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = pm.get_status(project)
        if st["state"] == state:
            return st
        time.sleep(0.1)
    return pm.get_status(project)


def test_resolve_executable_path(tmp_path):
    f = tmp_path / "x.sh"
    f.write_text("#!/bin/sh\n")
    assert pm._resolve_executable(str(f), None) is True
    assert pm._resolve_executable("/no/such/file", None) is False
    # PATH 상의 명령
    assert pm._resolve_executable("python3", None) is True or pm._resolve_executable("python", None)


def test_start_stop_lifecycle(sleeper_script, py_executable):
    p = storage.add_project(
        {
            "name": "sleeper",
            "script_path": sleeper_script,
            "python_path": py_executable,
            "scheduler_type": "manual",
        }
    )
    assert pm.get_status(p)["state"] == pm.STATE_STOPPED

    pm.start(p)
    st = _wait_state(p, pm.STATE_RUNNING)
    assert st["state"] == pm.STATE_RUNNING
    assert st["detected_by"] == "pidfile"
    assert st["pid"]

    pm.stop(p)
    st = _wait_state(p, pm.STATE_STOPPED)
    assert st["state"] == pm.STATE_STOPPED


def test_duplicate_start_blocked(sleeper_script, py_executable):
    p = storage.add_project(
        {"name": "dup", "script_path": sleeper_script, "python_path": py_executable}
    )
    pm.start(p)
    _wait_state(p, pm.STATE_RUNNING)
    with pytest.raises(pm.ProcessError):
        pm.start(p)
    pm.stop(p)


def test_start_missing_script_raises(tmp_path, py_executable):
    p = storage.add_project(
        {"name": "missing", "script_path": str(tmp_path / "none.py"), "python_path": py_executable}
    )
    with pytest.raises(pm.ProcessError):
        pm.start(p)


def test_always_on_stopped_is_error(sleeper_script, py_executable):
    p = storage.add_project(
        {
            "name": "always",
            "script_path": sleeper_script,
            "python_path": py_executable,
            "scheduler_type": "always_on",
        }
    )
    # always_on 인데 미실행 => error
    assert pm.get_status(p)["state"] == pm.STATE_ERROR


def test_command_based_execution(tmp_path, sleeper_script, py_executable):
    # 쉘 래퍼로 sleeper 실행
    wrapper = tmp_path / "wrap.sh"
    wrapper.write_text(f"#!/usr/bin/env bash\nexec {py_executable} {sleeper_script}\n")
    os.chmod(wrapper, 0o755)

    p = storage.add_project(
        {
            "name": "cmd",
            "script_path": sleeper_script,  # 식별용
            "command": str(wrapper),
            "scheduler_type": "manual",
        }
    )
    pm.start(p)
    st = _wait_state(p, pm.STATE_RUNNING)
    assert st["state"] == pm.STATE_RUNNING
    pm.stop(p)
    _wait_state(p, pm.STATE_STOPPED)


def test_cmdline_detection_exact_match_no_false_positive(sleeper_script, py_executable):
    """외부 실행 프로세스를 정확 인자 일치로 감지하고, substring 오탐은 없어야 한다."""
    # 외부에서 직접 실행 (PID 파일 없음)
    proc = subprocess.Popen([py_executable, sleeper_script])
    try:
        time.sleep(0.8)
        p = storage.add_project(
            {"name": "ext", "script_path": sleeper_script, "scheduler_type": "manual"}
        )
        st = pm.get_status(p)
        assert st["state"] == pm.STATE_RUNNING
        assert st["detected_by"] == "cmdline"

        # 오탐 검증: 경로를 substring 으로만 포함하는(정확 인자 아님) 가짜 경로는 매칭 안 됨
        fake = dict(p)
        fake["script_path"] = sleeper_script + "_NONEXISTENT_SUFFIX"
        assert pm.get_status(fake)["state"] != pm.STATE_RUNNING
    finally:
        proc.terminate()
        proc.wait()


def test_cmdline_detection_relative_arg_with_cwd(tmp_path, py_executable):
    """`cd <dir> && python <상대경로>` 형태(상대 인자 + cwd)도 감지해야 한다."""
    import textwrap

    script_dir = tmp_path / "proj"
    script_dir.mkdir()
    script = script_dir / "worker.py"
    script.write_text(
        textwrap.dedent(
            """
            import time
            time.sleep(30)
            """
        ).strip()
    )
    script_abs = str(script)

    # cwd 를 프로젝트 폴더로 두고 상대경로(worker.py)로 실행 = 크론 패턴 재현
    proc = subprocess.Popen([py_executable, "worker.py"], cwd=str(script_dir))
    try:
        time.sleep(0.8)
        p = storage.add_project(
            {"name": "rel", "script_path": script_abs, "scheduler_type": "always_on"}
        )
        st = pm.get_status(p)
        assert st["state"] == pm.STATE_RUNNING
        assert st["detected_by"] == "cmdline"
    finally:
        proc.terminate()
        proc.wait()
