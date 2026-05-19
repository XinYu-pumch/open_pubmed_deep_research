#!/bin/bash
#
# Build Open Pubmed Deep Research as a self-contained macOS app bundle.
# Target: Apple Silicon (arm64)
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Open Pubmed Deep Research"
VERSION="1.0.0"
VERSION_LABEL="V1.0"
BUILD_SUBDIR="${ROOT_DIR}/build/build_macos"
DIST_DIR="${ROOT_DIR}/dist"
COLLECT_DIR="${DIST_DIR}/PubmedResearch"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_NAME="Open_Pubmed_Deep_Research-${VERSION}-arm64.dmg"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
DMG_STAGING="${ROOT_DIR}/build/dmg_staging"
VENV_PYTHON="${ROOT_DIR}/venv/bin/python"
PYINSTALLER="${ROOT_DIR}/venv/bin/pyinstaller"
PYINSTALLER_CONFIG_DIR="${ROOT_DIR}/build/pyinstaller-cache"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
  echo -e "${BLUE}================================================${NC}"
  echo -e "${BLUE}  Building ${APP_NAME} ${VERSION_LABEL} (${VERSION})${NC}"
  echo -e "${BLUE}  Target: macOS Apple Silicon (arm64)${NC}"
  echo -e "${BLUE}================================================${NC}"
  echo
}

require_file() {
  local path="$1"
  if [ ! -e "$path" ]; then
    echo -e "${RED}Missing required file: ${path}${NC}"
    exit 1
  fi
}

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo -e "${RED}Missing required tool: ${tool}${NC}"
    exit 1
  fi
}

print_step() {
  echo -e "${GREEN}$1${NC}"
}

print_header

if [ "$(uname -s)" != "Darwin" ]; then
  echo -e "${RED}This build script must be run on macOS.${NC}"
  exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
  echo -e "${RED}This build is configured only for Apple Silicon (arm64).${NC}"
  exit 1
fi

require_file "${ROOT_DIR}/build_macos.spec"
require_file "${ROOT_DIR}/desktop_app.py"
require_file "${ROOT_DIR}/streamlit_server.py"
require_file "${ROOT_DIR}/convert_same_directory.py"
require_file "${ROOT_DIR}/marker_converter.py"
require_file "${ROOT_DIR}/app.py"
require_file "${ROOT_DIR}/core_logic.py"
require_file "${ROOT_DIR}/workspace_manager.py"
require_file "${ROOT_DIR}/config_manager.py"
require_tool "hdiutil"

if [ ! -x "${VENV_PYTHON}" ]; then
  echo -e "${RED}Missing virtualenv Python: ${VENV_PYTHON}${NC}"
  echo "Create the project venv and install dependencies before building."
  exit 1
fi

if [ ! -x "${PYINSTALLER}" ]; then
  echo -e "${RED}Missing PyInstaller executable: ${PYINSTALLER}${NC}"
  echo "Install build dependencies into the project venv first."
  exit 1
fi

print_step "[1/6] Verifying build environment..."
"${VENV_PYTHON}" - <<'PY'
import importlib
import sys

required = [
    "PyInstaller",
    "webview",
    "streamlit",
    "chromadb",
    "httpx",
    "requests",
    "bs4",
    "lxml",
    "markdown",
    "docx",
    "pandas",
    "numpy",
    "torch",
    "transformers",
    "surya",
    "pdftext",
    "pypdfium2",
]

missing = []
for module in required:
    try:
        importlib.import_module(module)
    except Exception:
        missing.append(module)

if missing:
    print("Missing build/runtime modules:", ", ".join(missing))
    sys.exit(1)
PY

echo "  Checking current app wiring..."
"${VENV_PYTHON}" - <<'PY'
import config_manager
import core_logic

cfg = config_manager.load_config()
required_llm_keys = {"base_url", "api_key", "model", "temperature", "stream", "timeout", "read_timeout"}
missing_llm_keys = required_llm_keys - set(cfg.get("llm", {}))
if missing_llm_keys:
    raise SystemExit(f"Missing LLM config keys: {sorted(missing_llm_keys)}")

if "llm_presets" not in cfg or not isinstance(cfg["llm_presets"], dict):
    raise SystemExit("Invalid llm_presets config shape")

if core_logic.get_framework_filename("zh") != "review_framework_cn.csv":
    raise SystemExit("Chinese framework filename mismatch")
if core_logic.get_framework_filename("en") != "review_framework_eng.csv":
    raise SystemExit("English framework filename mismatch")
if not core_logic.get_review_parts_dir("__build_check__", "zh").endswith("review_parts_cn"):
    raise SystemExit("Chinese review parts directory mismatch")
if not core_logic.get_review_parts_dir("__build_check__", "en").endswith("review_parts_eng"):
    raise SystemExit("English review parts directory mismatch")

if not hasattr(config_manager, "normalize_llm_config"):
    raise SystemExit("Missing LLM preset normalization helper")
if not hasattr(core_logic, "run_fulltext_download_pipeline"):
    raise SystemExit("Missing one-click full-text processing pipeline")
PY

print_step "[2/6] Ensuring application icon exists..."
mkdir -p "${ROOT_DIR}/resources"
"${VENV_PYTHON}" "${ROOT_DIR}/generate_icon.py"
if [ ! -f "${ROOT_DIR}/resources/app_icon.icns" ]; then
  echo -e "${YELLOW}Warning: app_icon.icns was not generated. The bundle will use the default icon.${NC}"
fi

print_step "[3/6] Cleaning previous mac build artifacts..."
rm -rf "${BUILD_SUBDIR}" "${COLLECT_DIR}" "${APP_PATH}" "${DMG_PATH}" "${DMG_STAGING}"
mkdir -p "${PYINSTALLER_CONFIG_DIR}"

print_step "[4/6] Running PyInstaller..."
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR}" "${PYINSTALLER}" --clean --noconfirm "${ROOT_DIR}/build_macos.spec"

if [ ! -d "${APP_PATH}" ]; then
  echo -e "${RED}Build failed: app bundle not found at ${APP_PATH}${NC}"
  exit 1
fi

print_step "[5/6] Verifying bundle structure..."
for executable in PubmedResearch streamlit-server same-directory-converter marker-converter; do
  if [ ! -x "${APP_PATH}/Contents/MacOS/${executable}" ]; then
    echo -e "${RED}Missing bundled executable: ${APP_PATH}/Contents/MacOS/${executable}${NC}"
    exit 1
  fi
done

for resource in app.py core_logic.py workspace_manager.py config_manager.py marker_modified marker_config; do
  if ! find "${APP_PATH}/Contents" -maxdepth 3 -name "${resource}" | grep -q .; then
    echo -e "${RED}Missing bundled resource: ${resource}${NC}"
    exit 1
  fi
done

for resource in streamlit_server.py convert_same_directory.py marker_converter.py; do
  if ! find "${APP_PATH}/Contents" -maxdepth 3 -name "${resource}" | grep -q .; then
    echo -e "${YELLOW}Warning: bundled script resource not found: ${resource}${NC}"
  fi
done

for leaked_config in \
  "${APP_PATH}/Contents/Resources/config.json" \
  "${APP_PATH}/Contents/Frameworks/config.json" \
  "${APP_PATH}/Contents/MacOS/config.json" \
  "${APP_PATH}/Contents/MacOS/_internal/config.json"; do
  if [ -f "${leaked_config}" ]; then
    echo -e "${RED}Local config.json was bundled at ${leaked_config}.${NC}"
    echo -e "${RED}Refusing to ship API keys or local presets.${NC}"
    exit 1
  fi
done

APP_SIZE="$(du -sh "${APP_PATH}" | awk '{print $1}')"
echo "  App bundle: ${APP_PATH}"
echo "  Size: ${APP_SIZE}"

print_step "[6/6] Creating DMG..."
mkdir -p "${DMG_STAGING}"
cp -R "${APP_PATH}" "${DMG_STAGING}/"
rm -rf "${DMG_STAGING}/Applications"
ln -s /Applications "${DMG_STAGING}/Applications"

hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "${DMG_STAGING}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}" >/dev/null

print_step "Cleaning intermediate build artifacts..."
rm -rf "${DMG_STAGING}"
rm -rf "${BUILD_SUBDIR}" "${COLLECT_DIR}" "${PYINSTALLER_CONFIG_DIR}"

echo
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}Build Complete${NC}"
echo -e "${BLUE}================================================${NC}"
echo "App Bundle: ${APP_PATH}"
echo "DMG Installer: ${DMG_PATH}"
echo
echo -e "${YELLOW}First-launch note:${NC}"
echo "On a target Mac, right-click the app once and choose 'Open' if Gatekeeper blocks it."
