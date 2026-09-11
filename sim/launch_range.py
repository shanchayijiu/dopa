"""启动合成靶场：拉起本地服务 + 用 Edge/Chrome 以应用/全屏模式打开靶场画面。

用法:
  python -m sim.launch_range --size 320 --mode bounce --count 1
  python -m sim.launch_range --server-only --size 320
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

from .overlay_client import healthy

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if os.path.isfile(explicit) else shutil.which(explicit)
    for path in BROWSER_CANDIDATES:
        if os.path.isfile(path):
            return path
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


def wait_ready(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if healthy(port):
            return True
        time.sleep(0.2)
    return False


def main():
    parser = argparse.ArgumentParser(description="启动 DOPA 合成靶场")
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--mode", default="bounce")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--classes", default="32,29")
    parser.add_argument("--sens", type=float, default=1.0)
    parser.add_argument("--out", default=None)
    parser.add_argument("--browser", default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--server-only", action="store_true")
    parser.add_argument("--user-data-dir", default=None)
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_cmd = [
        sys.executable, "-m", "sim.range_server",
        "--size", str(args.size),
        "--port", str(args.port),
        "--mode", args.mode,
        "--count", str(args.count),
        "--classes", args.classes,
        "--sens", str(args.sens),
    ]
    if args.out:
        server_cmd += ["--out", args.out]

    proc = subprocess.Popen(server_cmd, cwd=root)
    try:
        if not wait_ready(args.port):
            print("[靶场] 服务器启动失败或超时")
            return 1
        url = f"http://127.0.0.1:{args.port}/?size={args.size}"
        print(f"[靶场] 就绪: {url}")
        if args.no_browser or args.server_only:
            print("[靶场] 未打开浏览器（--no-browser/--server-only），按 Ctrl+C 退出")
        else:
            browser = find_browser(args.browser)
            if not browser:
                print(f"[靶场] 未找到浏览器，请手动打开 {url}")
            else:
                udd = args.user_data_dir or os.path.join(
                    os.environ.get("TEMP", "."), f"dopa_range_profile_{args.port}"
                )
                if not args.user_data_dir:
                    shutil.rmtree(udd, ignore_errors=True)
                cmd = [
                    browser,
                    f"--app={url}",
                    "--start-fullscreen",
                    f"--user-data-dir={udd}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
                print(f"[靶场] 启动浏览器: {browser}")
                subprocess.Popen(cmd)
        if args.server_only:
            proc.wait()
        else:
            while proc.poll() is None:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[靶场] 正在停止...")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
