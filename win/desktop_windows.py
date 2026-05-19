#!/usr/bin/env python
"""
Windows desktop launcher for the win-only build.
"""

import atexit
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing

from bootstrap_windows import PROJECT_ROOT, setup_windows_runtime


APP_NAME = "Open Pubmed Deep Research"
APP_VERSION_LABEL = "V1.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION_LABEL}"
STREAMLIT_PORT_START = 8501
STREAMLIT_PORT_END = 8520
SERVER_STARTUP_TIMEOUT = 90


def is_bundled() -> bool:
    return getattr(sys, "frozen", False)


def find_free_port(start=STREAMLIT_PORT_START, end=STREAMLIT_PORT_END):
    for port in range(start, end):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found between {start} and {end}")


def wait_for_server(url, timeout=SERVER_STARTUP_TIMEOUT, interval=0.5):
    start = time.time()
    last_error = None
    while time.time() - start < timeout:
        try:
            response = urllib.request.urlopen(url, timeout=2)
            if response.status == 200:
                return True
        except (urllib.error.URLError, ConnectionRefusedError, OSError) as e:
            last_error = e
            time.sleep(interval)
    print(f"Server startup timeout after {timeout}s. Last error: {last_error}")
    return False


class StreamlitServerManager:
    def __init__(self, port):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.process = None
        self.log_handle = None
        self.log_path = None

    def _open_log_handle(self):
        import workspace_manager

        log_dir = workspace_manager.get_log_dir()
        self.log_path = os.path.join(log_dir, "streamlit-server-windows.log")
        self.log_handle = open(self.log_path, "a", encoding="utf-8", buffering=1)
        self.log_handle.write(
            f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} start Windows server on {self.url} ===\n"
        )
        return self.log_handle

    def _close_log_handle(self):
        if not self.log_handle:
            return
        try:
            self.log_handle.write(f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} stop Windows server ===\n")
            self.log_handle.close()
        except Exception:
            pass
        self.log_handle = None

    def _server_command(self):
        if is_bundled():
            import workspace_manager

            executable = workspace_manager.get_streamlit_server_executable()
            if not executable:
                raise FileNotFoundError("streamlit-server.exe not found in bundled app")
            return [executable]
        return [sys.executable, "-u", os.path.join(PROJECT_ROOT, "win", "streamlit_server_windows.py")]

    def start(self):
        env = os.environ.copy()
        env["STREAMLIT_PORT"] = str(self.port)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["PYTHONPATH"] = os.pathsep.join([
            os.path.join(PROJECT_ROOT, "win"),
            PROJECT_ROOT,
            env.get("PYTHONPATH", ""),
        ]).strip(os.pathsep)

        log_target = self._open_log_handle()
        cmd = self._server_command()
        print(f"Starting Windows Streamlit server: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=log_target,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )

        if not wait_for_server(self.url):
            self.stop()
            raise RuntimeError(f"Streamlit server failed to start. See log: {self.log_path}")

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            except Exception:
                pass
        self._close_log_handle()


def run_desktop(server_manager):
    try:
        import webview

        def on_closing():
            server_manager.stop()

        window = webview.create_window(
            WINDOW_TITLE,
            server_manager.url,
            width=1400,
            height=900,
            min_size=(1024, 700),
            resizable=True,
            background_color="#f8f9fa",
        )
        window.events.closing += on_closing
        webview.start(debug=False)
        return True
    except Exception as e:
        print(f"pywebview failed: {e}")
        return False


def open_browser(server_manager):
    import webbrowser

    print(f"Opening browser fallback: {server_manager.url}")
    webbrowser.open(server_manager.url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server_manager.stop()


def main():
    setup_windows_runtime(patch_core=False)
    port = find_free_port()
    server_manager = StreamlitServerManager(port)
    atexit.register(server_manager.stop)

    def signal_handler(signum, frame):
        server_manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    server_manager.start()
    if not run_desktop(server_manager):
        open_browser(server_manager)
    server_manager.stop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
