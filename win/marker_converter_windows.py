#!/usr/bin/env python
"""
Windows CPU-only marker converter entry point for PyInstaller builds.
"""

import multiprocessing
import os
import runpy

from bootstrap_windows import PROJECT_ROOT, setup_windows_runtime


def main():
    setup_windows_runtime(patch_core=False)
    marker_converter_path = os.path.join(PROJECT_ROOT, "marker_converter.py")
    runpy.run_path(marker_converter_path, run_name="__main__")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
