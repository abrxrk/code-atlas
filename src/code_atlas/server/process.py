from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time

import httpx

from code_atlas import __version__
from code_atlas.config.paths import CONFIG_DIR, ensure_config_dir, ensure_log_dir

SERVER_LOCK_FILE = CONFIG_DIR / "server.json"
LOG_FILE_NAME = "server.log"

_HOST = "127.0.0.1"
_FIRST_PORT = 8420
_HEALTH_TIMEOUT_S = 5.0
_HEALTH_POLL_INTERVAL_S = 0.2
_TERMINATE_TIMEOUT_S = 5.0


def ensure_server_running() -> int:
    """Return the port of a live local server, reusing one if already running.

    Checks the pidfile+port lockfile under the config dir; if the recorded
    process is alive, answers /health on the recorded port, AND reports the
    currently-installed code-atlas version, reuses it. A version mismatch
    means a stale detached server survived a code-atlas upgrade (or, during
    development, an in-place code edit) — that process is killed and a
    fresh one spawned rather than silently serving outdated behavior.
    """
    lock = _read_lock()
    if lock is not None:
        pid, port = lock["pid"], lock["port"]
        if _pid_alive(pid):
            health = _health_check(port)
            if health is not None and health.get("version") == __version__:
                return port
            _terminate(pid)

    return _spawn_server()


def _read_lock() -> dict | None:
    if not SERVER_LOCK_FILE.exists():
        return None
    try:
        data = json.loads(SERVER_LOCK_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if "pid" not in data or "port" not in data:
        return None
    return data


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _health_check(port: int) -> dict | None:
    try:
        response = httpx.get(f"http://{_HOST}:{port}/health", timeout=1.0)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + _TERMINATE_TIMEOUT_S
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(_HEALTH_POLL_INTERVAL_S)
    if _pid_alive(pid):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((_HOST, port)) == 0


def _pick_port() -> int:
    port = _FIRST_PORT
    while _port_in_use(port):
        port += 1
    return port


def _spawn_server() -> int:
    ensure_config_dir()
    log_dir = ensure_log_dir()
    port = _pick_port()

    log_path = log_dir / LOG_FILE_NAME
    log_fh = open(log_path, "ab")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "code_atlas.server.app:create_app",
            "--factory",
            "--host",
            _HOST,
            "--port",
            str(port),
        ],
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )

    SERVER_LOCK_FILE.write_text(json.dumps({"pid": process.pid, "port": port}))

    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        if _health_check(port) is not None:
            return port
        time.sleep(_HEALTH_POLL_INTERVAL_S)

    return port
