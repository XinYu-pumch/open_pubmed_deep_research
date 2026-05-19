#!/usr/bin/env python
"""
Windows Streamlit entry point.

Run on Windows with:
    streamlit run win/app_windows.py
"""

import os
import runpy

from bootstrap_windows import PROJECT_ROOT, setup_windows_runtime


setup_windows_runtime(patch_core=True)

APP_PATH = os.path.join(PROJECT_ROOT, "app.py")
runpy.run_path(APP_PATH, run_name="__main__")
