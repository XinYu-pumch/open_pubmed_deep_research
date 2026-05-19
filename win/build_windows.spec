# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Windows-only distribution layer.

Build from the project root on Windows:
    powershell -ExecutionPolicy Bypass -File win/build_windows.ps1
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


SPEC_DIR = os.path.abspath(os.path.dirname(SPEC))
BASE_DIR = os.path.dirname(SPEC_DIR)
WIN_DIR = os.path.join(BASE_DIR, "win")
MARKER_PATH = os.path.join(BASE_DIR, "marker_modified")

APP_NAME = "OpenPubmedDeepResearch"
APP_VERSION = "1.0.0"

MAIN_SCRIPT = os.path.join(WIN_DIR, "desktop_windows.py")
SERVER_SCRIPT = os.path.join(WIN_DIR, "streamlit_server_windows.py")
SAME_DIR_CONVERTER_SCRIPT = os.path.join(WIN_DIR, "convert_same_directory_windows.py")
MARKER_CONVERTER_SCRIPT = os.path.join(WIN_DIR, "marker_converter_windows.py")


def optional_copy_metadata(dist_name, recursive=False):
    try:
        return copy_metadata(dist_name, recursive=recursive)
    except Exception:
        return []


def optional_collect_data_files(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []


def optional_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


datas = [
    (os.path.join(BASE_DIR, "app.py"), "."),
    (os.path.join(BASE_DIR, "core_logic.py"), "."),
    (os.path.join(BASE_DIR, "config_manager.py"), "."),
    (os.path.join(BASE_DIR, "convert_same_directory.py"), "."),
    (os.path.join(BASE_DIR, "marker_converter.py"), "."),
    (os.path.join(WIN_DIR, "app_windows.py"), "win"),
    (os.path.join(WIN_DIR, "bootstrap_windows.py"), "win"),
    (os.path.join(WIN_DIR, "workspace_manager.py"), "win"),
    (os.path.join(WIN_DIR, "streamlit_server_windows.py"), "win"),
    (os.path.join(WIN_DIR, "convert_same_directory_windows.py"), "win"),
    (os.path.join(WIN_DIR, "marker_converter_windows.py"), "win"),
    (os.path.join(BASE_DIR, "marker_modified"), "marker_modified"),
    (os.path.join(BASE_DIR, "marker_config"), "marker_config"),
]

for metadata_name, recursive in [
    ("streamlit", False),
    ("altair", False),
    ("pydeck", False),
    ("tornado", False),
    ("click", False),
    ("rich", False),
    ("packaging", False),
    ("toml", False),
    ("GitPython", False),
    ("tenacity", False),
    ("pyarrow", False),
    ("protobuf", False),
    ("pywebview", False),
    ("requests", False),
    ("httpx", False),
    ("httpcore", False),
    ("beautifulsoup4", False),
    ("lxml", False),
    ("markdown", False),
    ("pandas", False),
    ("numpy", False),
    ("chromadb", False),
    ("curl_cffi", False),
    ("python-docx", False),
    ("marker-pdf", False),
    ("surya-ocr", False),
    ("pdftext", False),
    ("pypdfium2", False),
]:
    datas += optional_copy_metadata(metadata_name, recursive=recursive)

for package_name in [
    "streamlit",
    "altair",
    "pydeck",
]:
    datas += optional_collect_data_files(package_name)


hidden_imports = [
    "streamlit",
    "streamlit.web",
    "streamlit.web.cli",
    "streamlit.runtime",
    "streamlit.runtime.scriptrunner",
    "streamlit.runtime.caching",
    "streamlit.runtime.state",
    "streamlit.components.v1",
    "webview",
    "webview.platforms",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "pandas",
    "numpy",
    "requests",
    "chromadb",
    "pyarrow",
    "pyarrow.lib",
    "httpx",
    "httpcore",
    "curl_cffi",
    "curl_cffi.requests",
    "docx",
    "docx.shared",
    "docx.enum.text",
    "docx.oxml",
    "docx.oxml.ns",
    "markdown",
    "markdown.extensions",
    "pdftext",
    "pypdfium2",
    "transformers",
    "torch",
    "safetensors",
    "surya",
    "PIL",
    "PIL.Image",
    "bs4",
    "bs4.builder",
    "bs4.builder._lxml",
    "lxml",
    "lxml.etree",
    "xml.etree.ElementTree",
    "altair",
    "pydeck",
    "tornado",
    "tornado.web",
    "tornado.websocket",
    "tornado.ioloop",
    "click",
    "rich",
    "toml",
    "git",
    "tenacity",
    "packaging",
    "packaging.version",
    "importlib_metadata",
]

for package_name in [
    "streamlit",
    "chromadb",
    "altair",
    "pydeck",
    "webview",
    "marker",
    "surya",
    "pdftext",
]:
    hidden_imports += optional_collect_submodules(package_name)


excludes = [
    "cuda",
    "cudnn",
    "nvidia",
    "pytest",
    "IPython",
    "jupyter",
    "notebook",
    "matplotlib",
    "scipy.tests",
]

analysis_kwargs = dict(
    pathex=[WIN_DIR, BASE_DIR, MARKER_PATH],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

a_main = Analysis([MAIN_SCRIPT], **analysis_kwargs)
a_server = Analysis([SERVER_SCRIPT], **analysis_kwargs)
a_same_dir = Analysis([SAME_DIR_CONVERTER_SCRIPT], **analysis_kwargs)
a_marker = Analysis([MARKER_CONVERTER_SCRIPT], **analysis_kwargs)

MERGE(
    (a_main, "OpenPubmedDeepResearch", "OpenPubmedDeepResearch"),
    (a_server, "streamlit-server", "streamlit-server"),
    (a_same_dir, "same-directory-converter", "same-directory-converter"),
    (a_marker, "marker-converter", "marker-converter"),
)

pyz_main = PYZ(a_main.pure, a_main.zipped_data)
pyz_server = PYZ(a_server.pure, a_server.zipped_data)
pyz_same_dir = PYZ(a_same_dir.pure, a_same_dir.zipped_data)
pyz_marker = PYZ(a_marker.pure, a_marker.zipped_data)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

exe_server = EXE(
    pyz_server,
    a_server.scripts,
    [],
    exclude_binaries=True,
    name="streamlit-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

exe_same_dir = EXE(
    pyz_same_dir,
    a_same_dir.scripts,
    [],
    exclude_binaries=True,
    name="same-directory-converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

exe_marker = EXE(
    pyz_marker,
    a_marker.scripts,
    [],
    exclude_binaries=True,
    name="marker-converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe_main,
    a_main.binaries,
    a_main.zipfiles,
    a_main.datas,
    exe_server,
    a_server.binaries,
    a_server.zipfiles,
    a_server.datas,
    exe_same_dir,
    a_same_dir.binaries,
    a_same_dir.zipfiles,
    a_same_dir.datas,
    exe_marker,
    a_marker.binaries,
    a_marker.zipfiles,
    a_marker.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
