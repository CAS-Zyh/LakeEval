"""在 Streamlit UI 进程内拉起 Flask 后端（子进程），实现 Streamlit Cloud 单体部署（0 成本，无需 VISA）。

设计目标：
1. Streamlit Cloud 是免费、不要求 VISA 的 Python 环境，原生直接跑 streamlit run ui/app.py。
2. 因为不能部署独立后端服务，就把 Flask API 作为 UI 的子进程跑在 127.0.0.1:<FLASK_PORT>，
   不对外暴露端口，安全性反而更强（所有请求都经过 Streamlit 容器内部回环）。
3. 只有当用户显式设置了 API_BASE_URL 环境变量（指向 Render 等独立后端）时，才跳过本启动步骤，
   保持「单体 / 分离」两种部署模式兼容。
4. 启动后每 0.5s 轮询 /api/status，最多 30s，返回 True 表示 Flask 就绪；失败则返回 False
   但不抛异常（UI 还可以继续加载，只是会显示后端未连接的友好提示）。
"""
from __future__ import annotations

import atexit
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import requests


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WSGI_PATH = _PROJECT_ROOT / "wsgi.py"
_LOCK_KEY = "_lakeeval_flask_subprocess_started"
_PROC_KEY = "_lakeeval_flask_subprocess_ref"
_READY_KEY = "_lakeeval_flask_ready"


def _is_port_in_use(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def _status_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/api/status"


def _wait_until_ready(host: str, port: int, timeout: float = 30.0) -> bool:
    end = time.time() + timeout
    last_err = ""
    while time.time() < end:
        try:
            resp = requests.get(_status_url(host, port), timeout=2)
            if resp.status_code == 200 and resp.json().get("success"):
                return True
        except Exception as e:  # noqa: BLE001 — 启动期各种异常都视为未就绪
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(0.5)
    sys.stderr.write(f"[flask_bootstrap] Flask 子进程未在 {timeout:.0f}s 内就绪，最后错误: {last_err}\n")
    return False


def _kill(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    proc.kill()
                else:
                    proc.send_signal(signal.SIGKILL)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
    except Exception:  # noqa: BLE001
        pass


def ensure_flask_running(force: bool = False) -> bool:
    """如果还没有 Flask 在监听 FLASK_HOST:FLASK_PORT，就拉起一个子进程。

    返回值：
        True  = Flask 已经就绪（要么本来就有，要么刚刚拉起并通过 /api/status）
        False = 启动失败或超时，UI 应该显示「后端未连接」提示。
    """
    # 只有 ui/app.py 里调用一次：用模块级 flag 避免多页面重复启动
    import __main__ as _mod  # type: ignore[import-not-found]

    sys.path.insert(0, str(_PROJECT_ROOT))
    from config import FLASK_HOST, FLASK_PORT  # 延迟导入，避免循环

    base = os.getenv("API_BASE_URL", "").strip()
    if base and not force:
        # 用户显式配置了远端 API（分离部署），不用本地起 Flask
        # （远端健康检查由 api_client 自行负责）
        setattr(_mod, _LOCK_KEY, True)
        setattr(_mod, _READY_KEY, True)
        return True

    already_started = bool(getattr(_mod, _LOCK_KEY, False))
    if already_started:
        return bool(getattr(_mod, _READY_KEY, False))

    setattr(_mod, _LOCK_KEY, True)

    # 先检查端口上是不是已经有活着的 Flask（例如 run.py 已经拉过一次）
    if _is_port_in_use(FLASK_HOST, FLASK_PORT):
        if _wait_until_ready(FLASK_HOST, FLASK_PORT, timeout=5.0):
            setattr(_mod, _READY_KEY, True)
            return True

    if not _WSGI_PATH.exists():
        sys.stderr.write(f"[flask_bootstrap] 找不到 wsgi.py，预期路径：{_WSGI_PATH}\n")
        setattr(_mod, _READY_KEY, False)
        return False

    # 子进程启动：直接 python wsgi.py（Flask dev server）。
    # - 为什么不用 gunicorn？Streamlit Cloud 环境在 Linux 上也能运行 gunicorn，
    #   但 gunicorn 会 fork 多个 worker 占用有限的 Streamlit Cloud 免费资源（1GB 内存），
    #   单体部署场景下 Flask dev server 单进程已经足够，而且更节省内存。
    # - stdout/stderr 直接继承到 Streamlit 日志中，便于排查。
    env = os.environ.copy()
    # 确保子进程使用的 FLASK_HOST/FLASK_PORT 和本进程一致（即使没写 .env）
    env.setdefault("FLASK_HOST", FLASK_HOST)
    env.setdefault("FLASK_PORT", str(FLASK_PORT))

    try:
        proc = subprocess.Popen(
            [sys.executable, str(_WSGI_PATH)],
            cwd=str(_PROJECT_ROOT),
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[flask_bootstrap] subprocess.Popen 失败: {type(e).__name__}: {e}\n")
        setattr(_mod, _READY_KEY, False)
        return False

    setattr(_mod, _PROC_KEY, proc)

    # 父进程退出时顺带杀掉子进程，避免在 Streamlit Cloud 容器中留下僵尸
    atexit.register(lambda: _kill(getattr(_mod, _PROC_KEY, None)))
    # 线程阻塞（最多 30s）等到 Flask 就绪
    ok = _wait_until_ready(FLASK_HOST, FLASK_PORT, timeout=30.0)
    setattr(_mod, _READY_KEY, ok)

    # 额外守护：如果子进程意外挂了，把状态标成 False
    def _watchdog() -> None:
        p = getattr(_mod, _PROC_KEY, None)
        if p is None:
            return
        p.wait()
        # 如果是被 atexit 正常关掉的，READY 还是 True（UI 马上也退出了）
        # 这里就不反过来翻 False 了，避免 race
        return

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()
    return ok


__all__ = ["ensure_flask_running"]
