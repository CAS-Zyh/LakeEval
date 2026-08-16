"""
LakeEval 一键启动器
同时拉起 Flask 后端 API 与 Streamlit 前端 UI。

用法:
    python run.py              # 启动后端 + 前端
    python run.py --backend    # 仅启动后端
    python run.py --frontend   # 仅启动前端
    python run.py --init-db    # 仅初始化数据库与默认 admin
按 Ctrl+C 一次性关闭两个服务。
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config import FLASK_PORT, FLASK_HOST, STREAMLIT_PORT, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD  # noqa: E402


def _python_exe() -> str:
    return sys.executable or "python"


def _streamlit_exe() -> str:
    # 优先使用当前解释器 Scripts 目录下的 streamlit（Windows）
    scripts_dir = Path(sys.executable).parent / "Scripts"
    candidates = [
        scripts_dir / "streamlit.exe",
        scripts_dir / "streamlit.cmd",
        scripts_dir / "streamlit",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "streamlit"


def init_db_only() -> int:
    """仅初始化数据库与默认 admin，便于首次部署使用。"""
    from api import create_app

    app = create_app()  # create_app 内部已调用 _init_default_admin()
    print(f"[init] 数据库已就绪，默认管理员账号: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    return 0


def start_backend() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        _python_exe(), "-c",
        "from api import create_app; app=create_app(); "
        f"app.run(host='{FLASK_HOST}', port={FLASK_PORT}, debug=False, use_reloader=False)"
    ]
    print(f"[backend] 启动 Flask: http://127.0.0.1:{FLASK_PORT}/api  (PID 将在下方显示)")
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env)


def start_frontend() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        _streamlit_exe(), "run", "ui/app.py",
        "--server.port", str(STREAMLIT_PORT),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    print(f"[frontend] 启动 Streamlit: http://127.0.0.1:{STREAMLIT_PORT}  (PID 将在下方显示)")
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env)


def _wait_for_http(url: str, timeout: float = 30.0) -> bool:
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1.5)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def run_full() -> int:
    procs: list[subprocess.Popen] = []
    try:
        backend = start_backend()
        procs.append(backend)

        if not _wait_for_http(f"http://127.0.0.1:{FLASK_PORT}/api/tli/grades", timeout=30):
            print(f"[warn] 后端 {FLASK_PORT} 在 30s 内未响应，继续启动前端（请稍后检查日志）")
        else:
            print(f"[ok] 后端就绪: http://127.0.0.1:{FLASK_PORT}/api")

        frontend = start_frontend()
        procs.append(frontend)

        print("\n" + "=" * 60)
        print("  LakeEval 已启动")
        print(f"  前端 UI : http://127.0.0.1:{STREAMLIT_PORT}")
        print(f"  后端 API: http://127.0.0.1:{FLASK_PORT}/api")
        print(f"  默认账号: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
        print("  按 Ctrl+C 关闭所有服务")
        print("=" * 60 + "\n")

        # 主循环：任一子进程退出即结束
        while True:
            for p in procs:
                rc = p.poll()
                if rc is not None:
                    print(f"[warn] 子进程 PID={p.pid} 退出，返回码={rc}")
                    raise SystemExit(1)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[shutdown] 收到 Ctrl+C，正在关闭服务...")
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    if os.name == "nt":
                        p.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        p.terminate()
                except Exception:
                    pass
        # 给进程 3 秒优雅退出，再强制 kill
        deadline = time.time() + 3
        for p in procs:
            remaining = max(0.1, deadline - time.time())
            try:
                p.wait(timeout=remaining)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("[shutdown] 已关闭。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LakeEval 一键启动器")
    parser.add_argument("--backend", action="store_true", help="仅启动后端 Flask")
    parser.add_argument("--frontend", action="store_true", help="仅启动前端 Streamlit")
    parser.add_argument("--init-db", action="store_true", help="仅初始化数据库与默认 admin 账号")
    args = parser.parse_args()

    if args.init_db:
        return init_db_only()

    procs: list[subprocess.Popen] = []
    try:
        if args.backend:
            procs.append(start_backend())
        elif args.frontend:
            procs.append(start_frontend())
        else:
            return run_full()

        # 单进程模式：等待退出
        while True:
            for p in procs:
                rc = p.poll()
                if rc is not None:
                    print(f"[warn] 子进程 PID={p.pid} 退出，返回码={rc}")
                    raise SystemExit(rc)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[shutdown] 收到 Ctrl+C，正在关闭...")
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
                try:
                    p.wait(timeout=3)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
