#!/usr/bin/env python
"""
Windows Streamlit server entry point used by the packaged desktop executable.
"""

import multiprocessing
import os
import sys

from bootstrap_windows import PROJECT_ROOT, setup_windows_runtime


def main():
    setup_windows_runtime(patch_core=True)
    port = int(os.environ.get("STREAMLIT_PORT", "8501"))
    app_path = os.path.join(PROJECT_ROOT, "win", "app_windows.py")

    if not os.path.exists(app_path):
        print(f"Error: app_windows.py not found at {app_path}")
        sys.exit(1)

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode",
        "false",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--browser.serverAddress",
        "127.0.0.1",
        "--server.fileWatcherType",
        "none",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
        "--logger.level",
        "warning",
    ]
    stcli.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
