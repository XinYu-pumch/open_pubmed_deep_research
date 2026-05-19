# Mac App Build Guide

Release label: `V1.0`  
Bundle version: `1.0.0`

## Goal

Build `Open Pubmed Deep Research.app` as a self-contained macOS desktop app that runs on an Apple Silicon Mac without requiring Python on the target machine.

This build keeps the existing Streamlit application and business logic intact. The packaging layer wraps the current app in a native macOS shell and bundles the Python runtime plus all runtime dependencies.

## Packaging Architecture

The macOS bundle contains four executables:

- `PubmedResearch`
  - Main GUI process.
  - Starts the local Streamlit server and opens it in a pywebview Cocoa window.
- `streamlit-server`
  - Runs `streamlit run app.py` as a local-only server on `127.0.0.1`.
- `same-directory-converter`
  - Batch PDF -> Markdown worker used by the UI's Markdown conversion step.
- `marker-converter`
  - Single-file marker worker invoked by `same-directory-converter`.

This extra converter layer is required because the packaged app cannot rely on a system Python interpreter when `core_logic.py` launches conversion jobs.

## Bundle Layout

After a successful build, the important structure is:

```text
dist/
├── Open Pubmed Deep Research.app
│   └── Contents
│       ├── MacOS
│       │   ├── PubmedResearch
│       │   ├── streamlit-server
│       │   ├── same-directory-converter
│       │   └── marker-converter
│       └── ...
└── Open_Pubmed_Deep_Research-1.0.0-arm64.dmg
```

The bundle also includes:

- `app.py`
- `core_logic.py`
- `config_manager.py`
- `workspace_manager.py`
- `convert_same_directory.py`
- `marker_modified/`
- `marker_config/`

`marker_config/` is large, so expect the final app and DMG to be large as well.

## User Data and Logs

The packaged app does not store user data inside the app bundle.

Runtime data locations:

- Config: `~/Library/Application Support/PubmedResearch/config.json`
- Workspace setting: `~/Library/Application Support/PubmedResearch/workspace_config.json`
- Desktop wrapper logs: `~/Library/Application Support/PubmedResearch/logs/streamlit-server.log`

Research data continues to live in the user-selected workspace directory.

## Build Prerequisites

Build on:

- macOS
- Apple Silicon (`arm64`)
- Project-local `venv`

The project `venv` must already contain the runtime dependencies and build tools.

Required modules inside `venv`:

- `PyInstaller`
- `pywebview`
- `streamlit`
- `chromadb`
- `torch`
- `transformers`
- `surya`
- `pdftext`
- `pypdfium2`

## Build Command

Run from the project root:

```bash
./build_app.sh
```

The script does the following:

1. Verifies the platform and the project `venv`
2. Verifies required Python modules
3. Regenerates the `.icns` icon if needed
4. Cleans previous mac build artifacts
5. Runs PyInstaller with `build_macos.spec`
6. Verifies the final app bundle structure
7. Creates a DMG with an `Applications` shortcut

## Smoke Test Checklist

Validate the packaged app on a Mac without Python:

1. Launch the `.app`
2. Confirm the workspace selection screen appears on first launch
3. Save a workspace and relaunch the app
4. Save LLM and embedding config
5. Run a small PubMed search
6. Generate a framework
7. Run Markdown conversion on at least one downloaded PDF
8. Run vectorization
9. Generate at least one section
10. Export Word and HTML

Also verify:

- Closing the app stops the `streamlit-server` subprocess
- The app listens only on `127.0.0.1`
- `streamlit-server.log` is written under Application Support

## Internal Distribution

This build flow is for internal distribution. The app is not signed or notarized.

Expected first-launch behavior on another Mac:

1. Copy the `.app` or install from the `.dmg`
2. Right-click the app and choose `Open`
3. Approve the Gatekeeper prompt once

## Troubleshooting

### App launches but no window appears

Check:

- `~/Library/Application Support/PubmedResearch/logs/streamlit-server.log`
- Whether the target machine is Apple Silicon

### Markdown conversion fails only in the packaged app

The packaged flow depends on the bundled helper executables:

- `same-directory-converter`
- `marker-converter`

Re-run the build and confirm both exist under:

```text
Open Pubmed Deep Research.app/Contents/MacOS/
```

### Bundle is extremely large

This is expected. `marker_config/` is bundled to preserve the current PDF/OCR behavior without changing features.
