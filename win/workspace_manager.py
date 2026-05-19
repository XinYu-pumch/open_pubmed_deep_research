"""
Windows-only workspace manager shim.

This module intentionally lives under win/ so the Windows entry points can put
win/ first on sys.path and use these platform paths without changing the mature
macOS code in the project root.
"""

import json
import os
import sys
import tempfile
from typing import List, Optional


APP_NAME = "PubmedResearch"
WIN_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WIN_DIR)


def _windows_app_support_dir() -> str:
    if not sys.platform.startswith("win"):
        return os.path.join(tempfile.gettempdir(), APP_NAME, "windows-shim")
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    return os.path.join(base, APP_NAME)


APP_SUPPORT_DIR = _windows_app_support_dir()
APP_LOG_DIR = os.path.join(APP_SUPPORT_DIR, "logs")
WORKSPACE_CONFIG_FILE = os.path.join(APP_SUPPORT_DIR, "workspace_config.json")


class WorkspaceManager:
    _instance = None
    _workspace_path: Optional[str] = None
    _is_bundled: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._is_bundled = getattr(sys, "frozen", False)
        os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
        os.makedirs(APP_LOG_DIR, exist_ok=True)
        self._load_workspace_config()

    def _load_workspace_config(self):
        if not os.path.exists(WORKSPACE_CONFIG_FILE):
            return
        try:
            with open(WORKSPACE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            path = config.get("workspace_path")
            if path and os.path.exists(path):
                self._workspace_path = path
        except (json.JSONDecodeError, OSError):
            pass

    def _save_workspace_config(self):
        try:
            os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
            with open(WORKSPACE_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"workspace_path": self._workspace_path}, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save workspace config: {e}")

    @property
    def is_bundled(self) -> bool:
        return self._is_bundled

    @property
    def workspace_path(self) -> Optional[str]:
        return self._workspace_path

    @property
    def is_configured(self) -> bool:
        return self._workspace_path is not None and os.path.exists(self._workspace_path)

    def set_workspace(self, path: str) -> bool:
        if not path:
            return False
        path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
        try:
            os.makedirs(os.path.join(path, "content"), exist_ok=True)
            self._workspace_path = path
            self._save_workspace_config()
            return True
        except OSError as e:
            print(f"Error setting workspace: {e}")
            return False

    def reload_workspace(self):
        self._load_workspace_config()

    def get_content_dir(self) -> str:
        if self._workspace_path:
            return os.path.join(self._workspace_path, "content")
        return os.path.join(PROJECT_ROOT, "content")

    def get_collection_path(self, collection_name: str) -> str:
        return os.path.join(self.get_content_dir(), collection_name)

    def get_resource_roots(self) -> List[str]:
        if not self._is_bundled:
            return [PROJECT_ROOT, WIN_DIR]

        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates = [
            getattr(sys, "_MEIPASS", None),
            os.path.join(exe_dir, "_internal"),
            exe_dir,
            PROJECT_ROOT,
            WIN_DIR,
        ]
        roots: List[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            abs_candidate = os.path.abspath(candidate)
            if abs_candidate not in roots and os.path.exists(abs_candidate):
                roots.append(abs_candidate)
        return roots or [exe_dir]

    def get_app_resource_path(self, relative_path: str) -> str:
        roots = self.get_resource_roots()
        if not relative_path:
            return roots[0]
        for root in roots:
            candidate = os.path.join(root, relative_path)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(roots[0], relative_path)

    def get_embedded_executable(self, executable_name: str) -> Optional[str]:
        filename = executable_name
        if sys.platform.startswith("win") and not filename.lower().endswith(".exe"):
            filename = f"{filename}.exe"

        search_dirs = []
        if self._is_bundled:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            search_dirs.extend([exe_dir, os.path.join(exe_dir, "_internal")])
            search_dirs.extend(self.get_resource_roots())
        else:
            search_dirs.extend([WIN_DIR, PROJECT_ROOT])

        seen = set()
        for search_dir in search_dirs:
            if not search_dir or search_dir in seen:
                continue
            seen.add(search_dir)
            candidate = os.path.join(search_dir, filename)
            if os.path.exists(candidate):
                return candidate
        return None

    def get_logs_dir(self) -> str:
        try:
            os.makedirs(APP_LOG_DIR, exist_ok=True)
            return APP_LOG_DIR
        except OSError:
            fallback = os.path.join(tempfile.gettempdir(), APP_NAME, "logs")
            os.makedirs(fallback, exist_ok=True)
            return fallback

    def get_bundled_python(self) -> str:
        if self._is_bundled:
            return sys.executable

        candidates = [
            os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe"),
            os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
            os.path.join(PROJECT_ROOT, "venv", "bin", "python"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return sys.executable

    def get_marker_script(self) -> str:
        return self.get_app_resource_path(os.path.join("marker_modified", "convert_single.py"))

    def get_marker_converter_executable(self) -> Optional[str]:
        return self.get_embedded_executable("marker-converter")

    def get_same_directory_converter_executable(self) -> Optional[str]:
        return self.get_embedded_executable("same-directory-converter")

    def get_streamlit_server_executable(self) -> Optional[str]:
        return self.get_embedded_executable("streamlit-server")

    def get_models_dir(self) -> str:
        if self._is_bundled:
            return self.get_app_resource_path("models")
        return os.path.join(os.path.expanduser("~"), ".cache", "huggingface")

    def setup_environment(self):
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("PYTHONUNBUFFERED", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

        # Windows V1 targets CPU-only Marker conversion.
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
        os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
        os.environ.setdefault("GLOG_minloglevel", "2")

        marker_root = self.get_app_resource_path("marker_modified")
        if marker_root and os.path.exists(marker_root) and marker_root not in sys.path:
            sys.path.insert(0, marker_root)


_manager = None


def get_workspace_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


def get_collection_path(collection_name: str) -> str:
    return get_workspace_manager().get_collection_path(collection_name)


def get_content_dir() -> str:
    return get_workspace_manager().get_content_dir()


def is_workspace_configured() -> bool:
    return get_workspace_manager().is_configured


def is_bundled_app() -> bool:
    return get_workspace_manager().is_bundled


def set_workspace(path: str) -> bool:
    return get_workspace_manager().set_workspace(path)


def reload_workspace():
    get_workspace_manager().reload_workspace()


def get_bundled_python() -> str:
    return get_workspace_manager().get_bundled_python()


def get_marker_script() -> str:
    return get_workspace_manager().get_marker_script()


def get_marker_converter_executable() -> Optional[str]:
    return get_workspace_manager().get_marker_converter_executable()


def get_same_directory_converter_executable() -> Optional[str]:
    return get_workspace_manager().get_same_directory_converter_executable()


def get_streamlit_server_executable() -> Optional[str]:
    return get_workspace_manager().get_streamlit_server_executable()


def get_app_resource_path(relative_path: str) -> str:
    return get_workspace_manager().get_app_resource_path(relative_path)


def get_log_dir() -> str:
    return get_workspace_manager().get_logs_dir()


def setup_app_environment():
    get_workspace_manager().setup_environment()


def get_config_file_path() -> str:
    return os.path.join(APP_SUPPORT_DIR, "config.json")
