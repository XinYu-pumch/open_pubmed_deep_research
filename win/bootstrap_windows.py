"""
Windows runtime bootstrap for the win-only distribution layer.

No project-root source file depends on this module. Windows entry points import
it before running the existing app so platform shims can be applied safely.
"""

import asyncio
import locale
import os
import sys
from typing import Dict, Optional


def _resolve_resource_root() -> str:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates = [
            getattr(sys, "_MEIPASS", None),
            os.path.join(exe_dir, "_internal"),
            exe_dir,
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)
        return exe_dir

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_ROOT = _resolve_resource_root()
WIN_DIR = os.path.join(PROJECT_ROOT, "win")


def ensure_import_paths():
    for path in (PROJECT_ROOT, WIN_DIR):
        if path in sys.path:
            sys.path.remove(path)
    sys.path.insert(0, WIN_DIR)
    sys.path.insert(1, PROJECT_ROOT)


def configure_encoding_and_cpu():
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.setdefault("GLOG_minloglevel", "2")

    # Windows V1 intentionally keeps Marker conversion CPU-only.
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True, write_through=True)
            except Exception:
                pass

    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass


def _decode_process_output(raw: bytes) -> str:
    encodings = [
        "utf-8",
        locale.getpreferredencoding(False),
        sys.getfilesystemencoding(),
        "gb18030",
        "latin-1",
    ]
    seen = set()
    for enc in encodings:
        if not enc:
            continue
        enc_l = enc.lower()
        if enc_l in seen:
            continue
        seen.add(enc_l)
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _windows_marker_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["GRPC_VERBOSITY"] = "ERROR"
    env["GLOG_minloglevel"] = "2"

    pythonpath = os.pathsep.join([WIN_DIR, PROJECT_ROOT, env.get("PYTHONPATH", "")]).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    return env


def patch_core_logic_for_windows():
    import core_logic
    import workspace_manager

    async def run_marker_conversion_windows(content_dir: str, workers: int, log_callback, marker_batch_size: int = 10):
        if workspace_manager.is_bundled_app():
            converter_executable = workspace_manager.get_same_directory_converter_executable()
            if not converter_executable or not os.path.exists(converter_executable):
                log_callback("Error: bundled Windows same-directory converter not found.")
                return
            cmd = [
                converter_executable,
                content_dir,
                "--pdftext_workers",
                str(workers),
                "--marker_batch_size",
                str(marker_batch_size),
            ]
        else:
            script = os.path.join(WIN_DIR, "convert_same_directory_windows.py")
            if not os.path.exists(script):
                log_callback("Error: win/convert_same_directory_windows.py not found.")
                return
            cmd = [
                sys.executable,
                "-u",
                script,
                content_dir,
                "--pdftext_workers",
                str(workers),
                "--marker_batch_size",
                str(marker_batch_size),
            ]

        log_callback(f"Running: {' '.join(cmd)}")
        log_callback("Windows Marker mode: CPU only.")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_windows_marker_env(),
            )

            async def stream_pipe(pipe, prefix: str = ""):
                buffer = bytearray()

                def emit(raw: bytes):
                    msg = _decode_process_output(raw).strip()
                    if msg:
                        log_callback(f"{prefix}{msg}")

                while True:
                    chunk = await pipe.read(4096)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    while True:
                        newline_positions = [pos for pos in (buffer.find(b"\n"), buffer.find(b"\r")) if pos != -1]
                        if not newline_positions:
                            break
                        pos = min(newline_positions)
                        raw_line = bytes(buffer[:pos])
                        del buffer[:pos + 1]
                        if raw_line.strip():
                            emit(raw_line)

                if buffer.strip():
                    emit(bytes(buffer))

            await asyncio.gather(
                stream_pipe(proc.stdout),
                stream_pipe(proc.stderr, "stderr: "),
            )
            return_code = await proc.wait()
            if return_code == 0:
                log_callback("Markdown conversion finished.")
            else:
                log_callback(f"Marker converter exited with code {return_code}.")
        except Exception as e:
            log_callback(f"Marker failed: {e}")

    core_logic.run_marker_conversion = run_marker_conversion_windows


def setup_windows_runtime(patch_core: bool = True):
    ensure_import_paths()
    configure_encoding_and_cpu()

    import workspace_manager

    workspace_manager.setup_app_environment()
    if patch_core:
        patch_core_logic_for_windows()
