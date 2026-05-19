"""
Workspace Manager - Singleton module for managing workspace directory paths.
Supports both development environment and packaged Mac App environment.
"""

import os
import sys
import json
import tempfile
from typing import List, Optional

# Application Support directory for Mac
APP_NAME = "PubmedResearch"
APP_SUPPORT_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
APP_LOG_DIR = os.path.join(APP_SUPPORT_DIR, "logs")

# Workspace config file
WORKSPACE_CONFIG_FILE = os.path.join(APP_SUPPORT_DIR, "workspace_config.json")


class WorkspaceManager:
    """Singleton class to manage workspace directory."""

    _instance = None
    _workspace_path: Optional[str] = None
    _is_bundled: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the workspace manager."""
        # Check if running as a bundled app
        self._is_bundled = getattr(sys, 'frozen', False)

        # Ensure App Support directory exists
        try:
            os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
            os.makedirs(APP_LOG_DIR, exist_ok=True)
        except OSError:
            # In restricted environments (for example sandboxes), App Support may
            # not be writable. The app still works in development mode without it.
            pass

        # Load workspace path from config
        self._load_workspace_config()

    def _load_workspace_config(self):
        """Load workspace path from config file."""
        if os.path.exists(WORKSPACE_CONFIG_FILE):
            try:
                with open(WORKSPACE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    path = config.get('workspace_path')
                    if path and os.path.exists(path):
                        self._workspace_path = path
            except (json.JSONDecodeError, IOError):
                pass

    def _save_workspace_config(self):
        """Save workspace path to config file."""
        try:
            with open(WORKSPACE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'workspace_path': self._workspace_path}, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save workspace config: {e}")

    @property
    def is_bundled(self) -> bool:
        """Check if running as a bundled application."""
        return self._is_bundled

    @property
    def workspace_path(self) -> Optional[str]:
        """Get the current workspace path."""
        return self._workspace_path

    @property
    def is_configured(self) -> bool:
        """Check if workspace is configured."""
        return self._workspace_path is not None and os.path.exists(self._workspace_path)

    def set_workspace(self, path: str) -> bool:
        """
        Set the workspace directory.

        Args:
            path: Path to the workspace directory

        Returns:
            True if successful, False otherwise
        """
        if not path:
            return False

        # Expand user path
        path = os.path.expanduser(path)

        # Create directory if it doesn't exist
        try:
            os.makedirs(path, exist_ok=True)

            # Create content subdirectory
            content_dir = os.path.join(path, "content")
            os.makedirs(content_dir, exist_ok=True)

            self._workspace_path = path
            self._save_workspace_config()
            return True
        except OSError as e:
            print(f"Error setting workspace: {e}")
            return False

    def reload_workspace(self):
        """
        Reload workspace configuration from disk.
        Call this after changing the workspace path to pick up changes.
        """
        self._load_workspace_config()

    def get_content_dir(self) -> str:
        """
        Get the content directory path.
        If workspace is configured: {workspace}/content
        Otherwise in development: ./content
        """
        if self._workspace_path:
            # Custom workspace is configured (works in both bundled and dev mode)
            return os.path.join(self._workspace_path, "content")
        else:
            # Development mode without custom workspace - use relative path
            return "content"

    def get_collection_path(self, collection_name: str) -> str:
        """
        Get the full path for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Full path to the collection directory
        """
        return os.path.join(self.get_content_dir(), collection_name)

    def get_app_resource_path(self, relative_path: str) -> str:
        """
        Get the path to an application resource.
        Handles both development and bundled environments.

        Args:
            relative_path: Relative path to the resource

        Returns:
            Full path to the resource
        """
        roots = self.get_resource_roots()
        if not relative_path:
            return roots[0]

        for root in roots:
            candidate = os.path.join(root, relative_path)
            if os.path.exists(candidate):
                return candidate

        return os.path.join(roots[0], relative_path)

    def get_resource_roots(self) -> List[str]:
        """Return bundle-aware search roots for application resources."""
        if not self._is_bundled:
            return [os.path.dirname(os.path.abspath(__file__))]

        roots: List[str] = []
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        contents_dir = os.path.dirname(exe_dir)
        candidates = [
            getattr(sys, '_MEIPASS', None),
            os.path.join(exe_dir, "_internal"),
            os.path.join(contents_dir, "Resources"),
            os.path.join(contents_dir, "Frameworks"),
            exe_dir,
        ]

        for candidate in candidates:
            if not candidate:
                continue
            abs_candidate = os.path.abspath(candidate)
            if abs_candidate not in roots and os.path.exists(abs_candidate):
                roots.append(abs_candidate)

        if not roots:
            roots.append(exe_dir)

        return roots

    def get_embedded_executable(self, executable_name: str) -> Optional[str]:
        """Resolve an auxiliary executable that ships inside the app bundle."""
        filename = executable_name
        if sys.platform.startswith("win") and not executable_name.endswith(".exe"):
            filename = f"{executable_name}.exe"

        search_dirs: List[str] = []
        if self._is_bundled:
            search_dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
            search_dirs.extend(self.get_resource_roots())
        else:
            search_dirs.append(os.path.dirname(os.path.abspath(__file__)))

        seen = set()
        for search_dir in search_dirs:
            if search_dir in seen:
                continue
            seen.add(search_dir)
            candidate = os.path.join(search_dir, filename)
            if os.path.exists(candidate):
                return candidate

        return None

    def get_logs_dir(self) -> str:
        """Return the application log directory."""
        try:
            os.makedirs(APP_LOG_DIR, exist_ok=True)
            return APP_LOG_DIR
        except OSError:
            fallback = os.path.join(tempfile.gettempdir(), APP_NAME, "logs")
            os.makedirs(fallback, exist_ok=True)
            return fallback

    def get_bundled_python(self) -> str:
        """
        Get the path to the Python executable.
        In bundled app: use the bundled Python
        In development: use venv Python
        """
        if self._is_bundled:
            # In bundled app, Python is bundled
            return sys.executable
        else:
            # Development mode - use venv
            base_dir = os.path.dirname(__file__)
            venv_python = os.path.join(base_dir, 'venv', 'bin', 'python')
            if os.path.exists(venv_python):
                return venv_python
            return sys.executable

    def get_marker_script(self) -> str:
        """Get the path to the marker conversion script."""
        return self.get_app_resource_path(os.path.join('marker_modified', 'convert_single.py'))

    def get_marker_converter_executable(self) -> Optional[str]:
        """Get the path to the bundled marker converter executable."""
        return self.get_embedded_executable('marker-converter')

    def get_same_directory_converter_executable(self) -> Optional[str]:
        """Get the path to the bundled same-directory converter executable."""
        return self.get_embedded_executable('same-directory-converter')

    def get_streamlit_server_executable(self) -> Optional[str]:
        """Get the path to the bundled Streamlit server executable."""
        return self.get_embedded_executable('streamlit-server')

    def get_models_dir(self) -> str:
        """
        Get the path to the models directory.
        For bundled app, models are in Resources/models
        """
        if self._is_bundled:
            return self.get_app_resource_path('models')
        else:
            # Development mode - use default HuggingFace cache
            return os.path.join(os.path.expanduser("~"), ".cache", "huggingface")

    def setup_environment(self):
        """
        Setup environment variables for the bundled app.
        Call this at application startup.
        """
        if self._is_bundled:
            # Set HuggingFace cache to bundled models
            models_dir = self.get_models_dir()
            if os.path.exists(models_dir):
                os.environ['HF_HOME'] = models_dir
                os.environ['TRANSFORMERS_CACHE'] = os.path.join(models_dir, 'transformers')

            # Disable telemetry
            os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'


# Singleton instance
_manager = None


def get_workspace_manager() -> WorkspaceManager:
    """Get the singleton workspace manager instance."""
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


# Convenience functions for common operations
def get_collection_path(collection_name: str) -> str:
    """Get the full path for a collection."""
    return get_workspace_manager().get_collection_path(collection_name)


def get_content_dir() -> str:
    """Get the content directory path."""
    return get_workspace_manager().get_content_dir()


def is_workspace_configured() -> bool:
    """Check if workspace is configured."""
    return get_workspace_manager().is_configured


def is_bundled_app() -> bool:
    """Check if running as a bundled application."""
    return get_workspace_manager().is_bundled


def set_workspace(path: str) -> bool:
    """Set the workspace directory."""
    return get_workspace_manager().set_workspace(path)


def reload_workspace():
    """Reload workspace configuration from disk."""
    get_workspace_manager().reload_workspace()


def get_bundled_python() -> str:
    """Get the path to the Python executable."""
    return get_workspace_manager().get_bundled_python()


def get_marker_script() -> str:
    """Get the path to the marker conversion script."""
    return get_workspace_manager().get_marker_script()


def get_marker_converter_executable() -> Optional[str]:
    """Get the path to the bundled marker converter executable."""
    return get_workspace_manager().get_marker_converter_executable()


def get_same_directory_converter_executable() -> Optional[str]:
    """Get the path to the bundled same-directory converter executable."""
    return get_workspace_manager().get_same_directory_converter_executable()


def get_streamlit_server_executable() -> Optional[str]:
    """Get the path to the bundled Streamlit server executable."""
    return get_workspace_manager().get_streamlit_server_executable()


def get_app_resource_path(relative_path: str) -> str:
    """Resolve an application resource for development or bundled mode."""
    return get_workspace_manager().get_app_resource_path(relative_path)


def get_log_dir() -> str:
    """Get the application log directory."""
    return get_workspace_manager().get_logs_dir()


def setup_app_environment():
    """Setup environment for the application."""
    get_workspace_manager().setup_environment()


# Config file path for config_manager
def get_config_file_path() -> str:
    """
    Get the path to the config file.
    In bundled app: ~/Library/Application Support/PubmedResearch/config.json
    In development: ./config.json
    """
    if get_workspace_manager().is_bundled:
        return os.path.join(APP_SUPPORT_DIR, "config.json")
    else:
        return "config.json"
