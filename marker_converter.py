#!/usr/bin/env python3
"""
Standalone marker converter entry point for bundled desktop builds.

This executable exists so the packaged app can perform PDF -> Markdown
conversion without relying on a system Python interpreter.
"""

import multiprocessing
import os
import sys

from workspace_manager import get_app_resource_path, setup_app_environment


def main():
    """Load the local marker package and forward to marker's CLI entry point."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True, write_through=True)

    marker_root = get_app_resource_path("marker_modified")
    if not os.path.exists(marker_root):
        raise FileNotFoundError(f"marker_modified not found: {marker_root}")

    if marker_root not in sys.path:
        sys.path.insert(0, marker_root)

    setup_app_environment()

    from marker.scripts.convert_single import convert_single_cli

    convert_single_cli()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
