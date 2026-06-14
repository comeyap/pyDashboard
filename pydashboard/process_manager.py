"""프로세스 실행/중지/상태 추적.

식별 전략 (오탐 방지):
  1) 대시보드가 실행한 프로세스는 PID 파일(data/pids/{id}.pid)로 추적하고,
     실행 시 환경 변수 PYDASHBOARD_PROJECT_ID 를 주입한다.
     상태 확인 시 PID 가 살아있는지 + 해당 프로세스의 environ 이 project id 와
     일치하는지 검증 → PID 재사용으로 인한 오탐 차단.
  2) OS 스케줄러(cron/launchagent)가 직접 실행한 프로세스는 PID 파일이 없으므로,
     psutil 로 cmdline 에 script_path 가 포함된 프로세스를 best-effort 매칭한다.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from datetime import datetime
from typing import Any, Optional

import psutil

from . import config

# 상태 상수
STATE_RUNNING = "running"
STATE_STOPPED = "stopped"
STATE_ERROR = "error"


def _resolve_executable(exe: str, working_dir: Optional[str]) -> bool:
    """커맨드 첫 토큰이 실행 가능한지 확인한다.

    절대/상대 경로 파일 존재, 또는 PATH 등록 여부(shutil.which)를 본다.
    상대 경로는 working_dir 기준으로도 검사한다.
    """
    if os.path.isabs(exe):
        return os.path.exists(exe)
    if os.sep in exe or (os.altsep and os.altsep in exe):
        base = working_dir or os.getcwd()
        return os.path.exists(os.path.join(base, exe))
    # PATH 탐색
    return shutil.which(exe) is not None


def _pid_file(project_id: str) -> str:
    return str(config.PID_DIR / f"{project_id}.pid")


def _log_file(project_id: str) -> str:
    return str(config.LOG_DIR / f"{project_id}.log")


def _read_pid(project_id: str) -> Optional[int]:
    path = _pid_file(project_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def _clear_pid(project_id: str) -> None:
    path = _pid_file(project_id)
    try:
        os.remove(path)
    except OSError:
        pass


def _proc_matches_project(proc: psutil.Process, project_id: str) -> bool:
    """프로세스 environ 에 우리가 주입한 project id 가 있는지 확인."""
    try:
        env = proc.environ()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
        # environ 조회 실패 시 PID 생존 여부만으로 판단 (best-effort)
        return True
    return env.get(config.ENV_PROJECT_KEY) == project_id


def _find_by_cmdline(identify_path: str) -> Optional[psutil.Process]:
    """OS 스케줄러 등 외부에서 실행된 프로세스를 cmdline 으로 best-effort 매칭한다.

    기술 고려사항 #2(오탐 방지)에 따라 단순 substring 매칭을 쓰지 않는다.
    - identify_path(보통 스크립트 절대경로)와 '정확히 일치'하는 인자(arg)가 있을 것
      (substring 금지 → 경로가 우연히 문자열에 포함된 프로세스는 매칭 안 됨)
    - 대시보드 자기 자신(PID)은 제외
    인터프리터 종류는 제한하지 않는다. python 직접 실행뿐 아니라 streamlit,
    쉘 래퍼(run_live.sh) 등 다양한 실행 형태를 지원하기 위함이다.
    정확 인자 일치만으로도 오탐은 충분히 차단된다(에디터로 파일을 '연' 경우 등
    극히 드문 케이스는 best-effort 한계로 둔다).
    """
    if not identify_path:
        return None
    try:
        target_real = os.path.realpath(identify_path)
    except OSError:
        target_real = identify_path
    target_base = os.path.basename(identify_path)
    self_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if proc.info.get("pid") == self_pid:
                continue
            cmdline = proc.info.get("cmdline") or []
            if len(cmdline) < 2:
                continue
            for arg in cmdline[1:]:
                if arg == identify_path:
                    return proc
                try:
                    if os.path.realpath(arg) == target_real:
                        return proc
                except OSError:
                    pass
                # `cd <dir> && python <상대경로>` 형태: 인자가 상대경로이고
                # 파일명이 같으면 프로세스 cwd 기준으로 절대경로를 복원해 비교.
                if (
                    target_base
                    and not os.path.isabs(arg)
                    and os.path.basename(arg) == target_base
                ):
                    try:
                        resolved = os.path.realpath(os.path.join(proc.cwd(), arg))
                        if resolved == target_real:
                            return proc
                    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                        continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def get_status(project: dict[str, Any]) -> dict[str, Any]:
    """프로젝트의 현재 상태를 계산한다.

    반환: {state, pid, detected_by, started_at}
    """
    project_id = project["id"]
    script_path = project.get("script_path", "")
    scheduler_type = project.get("scheduler_type", "manual")

    # 1) PID 파일 기반 (대시보드 실행분)
    pid = _read_pid(project_id)
    if pid is not None:
        if psutil.pid_exists(pid):
            try:
                proc = psutil.Process(pid)
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    if _proc_matches_project(proc, project_id):
                        return {
                            "state": STATE_RUNNING,
                            "pid": pid,
                            "detected_by": "pidfile",
                            "started_at": _iso(proc.create_time()),
                        }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        # PID 파일은 있으나 프로세스가 죽음 → stale 정리
        _clear_pid(project_id)

    # 2) cmdline 매칭 (OS 스케줄러 실행분)
    proc = _find_by_cmdline(script_path)
    if proc is not None:
        try:
            return {
                "state": STATE_RUNNING,
                "pid": proc.pid,
                "detected_by": "cmdline",
                "started_at": _iso(proc.create_time()),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 미실행. always_on 인데 죽어있으면 Error 로 표시.
    state = STATE_ERROR if scheduler_type == "always_on" else STATE_STOPPED
    return {"state": state, "pid": None, "detected_by": None, "started_at": None}


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


class ProcessError(Exception):
    """프로세스 제어 실패."""


def start(project: dict[str, Any]) -> dict[str, Any]:
    """스크립트를 백그라운드로 실행한다 (F-401).

    F-402: 이미 실행 중이면 거부하여 중복 실행을 방지한다.
    """
    config.ensure_dirs()
    project_id = project["id"]

    status = get_status(project)
    if status["state"] == STATE_RUNNING:
        raise ProcessError("이미 실행 중입니다 (중복 실행 방지).")

    command = (project.get("command") or "").strip()
    script_path = project.get("script_path", "")

    if command:
        # 임의 커맨드 실행 (streamlit / 쉘 래퍼 / python -m 등).
        # 셸 인젝션을 피하기 위해 shell=True 대신 shlex 로 토큰 분리.
        try:
            cmd = shlex.split(command)
        except ValueError as exc:
            raise ProcessError(f"커맨드 파싱 실패: {exc}") from exc
        if not cmd:
            raise ProcessError("실행 커맨드가 비어 있습니다.")
        # 첫 토큰(실행 파일)이 PATH 또는 working_dir 기준으로 존재하는지 확인
        working_dir = project.get("working_dir") or (
            os.path.dirname(script_path) if script_path else None
        )
        if not _resolve_executable(cmd[0], working_dir):
            raise ProcessError(f"실행 파일을 찾을 수 없습니다: {cmd[0]}")
    else:
        # 기본 모드: python <script.py> <args>
        if not script_path or not os.path.exists(script_path):
            raise ProcessError(f"스크립트를 찾을 수 없습니다: {script_path}")
        python_path = project.get("python_path") or "python3"
        args = project.get("args", [])
        working_dir = project.get("working_dir") or os.path.dirname(script_path) or None
        cmd = [python_path, script_path, *args]

    env = os.environ.copy()
    env[config.ENV_PROJECT_KEY] = project_id

    log_path = _log_file(project_id)
    try:
        log_fh = open(log_path, "ab")
    except OSError as exc:
        raise ProcessError(f"로그 파일을 열 수 없습니다: {exc}") from exc

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=working_dir,
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # 대시보드 종료와 무관하게 detach
        )
    except (OSError, ValueError) as exc:
        log_fh.close()
        raise ProcessError(f"프로세스 실행 실패: {exc}") from exc
    finally:
        log_fh.close()

    with open(_pid_file(project_id), "w", encoding="utf-8") as f:
        f.write(str(proc.pid))

    return {"state": STATE_RUNNING, "pid": proc.pid, "detected_by": "pidfile"}


def stop(project: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """실행 중인 프로세스를 안전하게 종료한다 (F-403).

    SIGTERM 후 timeout 내 미종료 시 SIGKILL. 자식 프로세스도 함께 정리한다.
    """
    project_id = project["id"]
    status = get_status(project)
    if status["state"] != STATE_RUNNING or not status.get("pid"):
        raise ProcessError("실행 중인 프로세스가 없습니다.")

    pid = status["pid"]
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        _clear_pid(project_id)
        return {"state": STATE_STOPPED, "pid": None}

    # 자식까지 수집 후 부모→자식 순으로 종료
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

    _clear_pid(project_id)
    return {"state": STATE_STOPPED, "pid": None}


def tail_log(project: dict[str, Any], lines: int = 50) -> str:
    """프로젝트 실행 로그의 마지막 N줄을 반환한다."""
    path = _log_file(project["id"])
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""
