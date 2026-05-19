#!/usr/bin/env python3
"""
Streamlit Server - Independent Process Entry Point.

This is a standalone executable that runs the Streamlit server.
It is launched as a subprocess by the main desktop_app (pywebview) process.

Architecture:
- This process runs Streamlit in its main thread
- Parent process (desktop_app) runs pywebview in its main thread
- Communication via STREAMLIT_PORT environment variable
"""

import os
import sys

from workspace_manager import get_app_resource_path, setup_app_environment


def setup_environment():
    """Configure environment for bundled Mac App."""
    setup_app_environment()
    app_root = os.path.dirname(get_app_path())

    if app_root not in sys.path:
        sys.path.insert(0, app_root)

    os.chdir(app_root)

    # Set Streamlit config via environment
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'
    os.environ['STREAMLIT_GLOBAL_DEVELOPMENT_MODE'] = 'false'


def get_app_path():
    """Get the path to app.py based on environment."""
    return get_app_resource_path('app.py')


def main():
    """Main entry point for the Streamlit server."""
    # Get port from environment (set by parent process)
    port = int(os.environ.get('STREAMLIT_PORT', '8501'))

    # Get app path
    app_path = get_app_path()

    print(f"Streamlit Server starting...")
    print(f"  Port: {port}")
    print(f"  App path: {app_path}")
    print(f"  Frozen: {getattr(sys, 'frozen', False)}")

    # Verify app.py exists
    if not os.path.exists(app_path):
        print(f"Error: app.py not found at {app_path}")
        sys.exit(1)

    # Import and run Streamlit
    from streamlit.web import cli as stcli

    # Set up Streamlit arguments
    sys.argv = [
        'streamlit', 'run',
        app_path,
        '--global.developmentMode', 'false',
        '--server.port', str(port),
        '--server.address', '127.0.0.1',
        '--server.headless', 'true',
        '--browser.gatherUsageStats', 'false',
        '--browser.serverAddress', '127.0.0.1',
        '--server.fileWatcherType', 'none',
        '--server.enableCORS', 'false',
        '--server.enableXsrfProtection', 'false',
        '--logger.level', 'warning',
    ]

    # Run Streamlit (blocking call)
    stcli.main()


if __name__ == '__main__':
    # macOS multiprocessing fix
    import multiprocessing
    multiprocessing.freeze_support()

    setup_environment()
    main()
