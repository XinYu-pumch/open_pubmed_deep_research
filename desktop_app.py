#!/usr/bin/env python3
"""
Desktop Application Entry Point for Open Pubmed Deep Research.

Dual-Process Architecture:
- This process (main): Runs pywebview native window in main thread (macOS Cocoa requirement)
- Subprocess (streamlit-server): Runs Streamlit server in separate process
"""

import os
import sys

# CRITICAL: Prevent re-entry / infinite spawning
# If this env var is set, we're being spawned by ourselves - exit immediately
if os.environ.get('_PUBMED_DESKTOP_RUNNING') == '1':
    sys.exit(0)

# Set the guard for any child processes
os.environ['_PUBMED_DESKTOP_RUNNING'] = '1'

import time
import socket
import signal
import atexit
import subprocess
from contextlib import closing

from workspace_manager import get_log_dir, get_streamlit_server_executable

# Application configuration
APP_NAME = "Open Pubmed Deep Research"
APP_VERSION_LABEL = "V1.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION_LABEL}"
STREAMLIT_PORT_START = 8501
STREAMLIT_PORT_END = 8520
SERVER_STARTUP_TIMEOUT = 60  # seconds


def is_bundled():
    """Check if running as a bundled PyInstaller app."""
    return getattr(sys, 'frozen', False)


def find_free_port(start=STREAMLIT_PORT_START, end=STREAMLIT_PORT_END):
    """Find an available port in the given range."""
    for port in range(start, end):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found between {start} and {end}")


def get_server_executable():
    """Get the path to the streamlit-server executable."""
    if is_bundled():
        return get_streamlit_server_executable()
    return None


def wait_for_server(url, timeout=SERVER_STARTUP_TIMEOUT, interval=0.5):
    """Wait for the Streamlit server to be ready."""
    import urllib.request
    import urllib.error

    start_time = time.time()
    last_error = None

    while time.time() - start_time < timeout:
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
    """Manages the Streamlit server subprocess lifecycle."""

    def __init__(self, port):
        self.port = port
        self.process = None
        self.url = f"http://127.0.0.1:{port}"
        self.log_handle = None
        self.log_path = None

    def _open_log_handle(self):
        """Redirect subprocess output to an app-local log file."""
        log_dir = get_log_dir()
        self.log_path = os.path.join(log_dir, "streamlit-server.log")
        self.log_handle = open(self.log_path, "a", encoding="utf-8", buffering=1)
        self.log_handle.write(
            f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} start streamlit-server on {self.url} ===\n"
        )
        self.log_handle.flush()
        return self.log_handle

    def _close_log_handle(self):
        """Close the log file handle if it is open."""
        if self.log_handle is None:
            return

        try:
            self.log_handle.write(
                f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} stop streamlit-server ===\n"
            )
            self.log_handle.flush()
        except Exception:
            pass

        try:
            self.log_handle.close()
        except Exception:
            pass

        self.log_handle = None

    def start(self):
        """Start the Streamlit server subprocess."""
        env = os.environ.copy()
        env['STREAMLIT_PORT'] = str(self.port)
        env['PYTHONUNBUFFERED'] = '1'
        # Remove re-entry guard so subprocess can run normally
        env.pop('_PUBMED_DESKTOP_RUNNING', None)

        if is_bundled():
            server_path = get_server_executable()
            if not server_path or not os.path.exists(server_path):
                raise FileNotFoundError(f"Server executable not found: {server_path}")

            log_target = self._open_log_handle()
            print(f"Starting bundled server: {server_path}")
            self.process = subprocess.Popen(
                [server_path],
                env=env,
                stdout=log_target,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(script_dir, 'streamlit_server.py')

            print(f"Starting development server: {server_script}")
            self.process = subprocess.Popen(
                [sys.executable, server_script],
                env=env,
                stdout=None,
                stderr=None,
                start_new_session=True
            )

        print(f"Server process started with PID: {self.process.pid}")
        return self.process

    def wait_ready(self, timeout=SERVER_STARTUP_TIMEOUT):
        """Wait for server to be ready to accept connections."""
        print(f"Waiting for server at {self.url}...")
        if wait_for_server(self.url, timeout=timeout):
            print("Server is ready!")
            return True
        else:
            print("Server failed to start in time")
            if self.log_path:
                print(f"See server log: {self.log_path}")
            return False

    def stop(self):
        """Stop the Streamlit server subprocess."""
        if self.process is None:
            return

        print(f"Stopping server (PID: {self.process.pid})...")

        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("Server terminated gracefully")
            except subprocess.TimeoutExpired:
                print("Server didn't respond to SIGTERM, sending SIGKILL...")
                self.process.kill()
                self.process.wait(timeout=3)
                print("Server killed")
        except Exception as e:
            print(f"Error stopping server: {e}")

        self.process = None
        self._close_log_handle()

    def is_running(self):
        """Check if the server process is still running."""
        if self.process is None:
            return False
        return self.process.poll() is None


def run_with_pywebview(server_manager):
    """Run the application with a native pywebview window."""
    try:
        import webview

        def on_closing():
            """Handle window close event."""
            print("Window closing...")
            server_manager.stop()

        window = webview.create_window(
            WINDOW_TITLE,
            server_manager.url,
            width=1400,
            height=900,
            min_size=(1024, 700),
            resizable=True,
            background_color='#f8f9fa'
        )

        window.events.closing += on_closing

        # CRITICAL: Use gui='cef' or specify no multiprocessing
        # On macOS, default is Cocoa which should be single-process
        webview.start()

        return True

    except ImportError as e:
        print(f"pywebview not available: {e}")
        return False
    except Exception as e:
        print(f"pywebview error: {e}")
        return False


def run_with_browser(server_manager):
    """Fallback: open in system browser and keep server running."""
    import webbrowser

    print(f"Opening {server_manager.url} in default browser...")
    webbrowser.open(server_manager.url)

    print("Press Ctrl+C to stop the server...")
    try:
        while server_manager.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


def main():
    """Main entry point."""
    print(f"Starting {APP_NAME}...")
    print(f"Bundled mode: {is_bundled()}")

    # Find available port
    try:
        port = find_free_port()
        print(f"Using port: {port}")
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Create server manager
    server_manager = StreamlitServerManager(port)

    # Register cleanup on exit
    def cleanup():
        server_manager.stop()

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

    # Start server subprocess
    try:
        server_manager.start()
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)

    # Wait for server to be ready
    if not server_manager.wait_ready():
        print("Error: Server failed to start")
        server_manager.stop()
        sys.exit(1)

    # Try pywebview first (native window), fall back to browser
    if not run_with_pywebview(server_manager):
        run_with_browser(server_manager)

    # Cleanup
    server_manager.stop()
    print("Application closed.")


if __name__ == '__main__':
    # macOS multiprocessing fix - MUST be inside __main__ guard
    import multiprocessing
    multiprocessing.freeze_support()

    main()
