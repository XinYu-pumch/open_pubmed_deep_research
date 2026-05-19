# Windows V1.0 Layer

This folder is intentionally self-contained. It adds Windows WebUI and Windows
packaging entry points without changing the macOS V1.0 source files in the
project root.

## Run WebUI From Source

From the project root on Windows:

```powershell
.\venv\Scripts\activate
streamlit run win/app_windows.py
```

The Windows layer stores app configuration under:

```text
%APPDATA%\PubmedResearch\config.json
```

If no workspace is configured, source mode uses:

```text
.\content
```

You can change the workspace from the Settings page.

## Marker Conversion

Windows V1.0 forces Marker conversion to CPU mode by setting:

```text
CUDA_VISIBLE_DEVICES=
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
```

The WebUI calls `win/convert_same_directory_windows.py`, which wraps the
existing root converter with the Windows shim loaded first.

## Build Windows EXE

From the project root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File win/build_windows.ps1
```

Output:

```text
dist\OpenPubmedDeepResearch\OpenPubmedDeepResearch.exe
```

This is a one-folder PyInstaller distribution. The folder also contains helper
executables and bundled runtime files required by Streamlit, Marker, Torch, and
ChromaDB. A true one-file exe is not recommended for the first Windows build
because these dependencies are large and slow to unpack.

## Rollback

Delete the `win/` folder to remove the Windows layer. The macOS Streamlit app
and macOS packaging files are not modified by this layer.
