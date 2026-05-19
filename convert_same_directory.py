#!/usr/bin/env python3
"""
Convert PDF files in the same directory to markdown with same filename.
Specifically designed for the use case: content/1214/ -> PDF -> MD in same directory.
Supports both development and bundled Mac App environments.
"""

import os
import sys
import argparse
import gc
import json
import shutil
import time
import subprocess
import threading
from pathlib import Path
from typing import List, Optional, Tuple

# Import workspace manager for bundled app support
try:
    from workspace_manager import (
        get_app_resource_path,
        get_bundled_python,
        get_marker_converter_executable,
        get_marker_script,
        is_bundled_app,
        setup_app_environment,
    )
except ImportError:
    # Fallback for standalone usage
    def is_bundled_app():
        return getattr(sys, 'frozen', False)

    def get_app_resource_path(relative_path: str):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path) if relative_path else base_dir

    def get_bundled_python():
        base_dir = os.path.dirname(__file__)
        venv_python = os.path.join(base_dir, 'venv', 'bin', 'python')
        if os.path.exists(venv_python):
            return venv_python
        return sys.executable

    def get_marker_script():
        base_dir = os.path.dirname(__file__)
        return os.path.join(base_dir, 'marker_modified', 'convert_single.py')

    def get_marker_converter_executable():
        return None

    def setup_app_environment():
        return None


class SameDirectoryConverter:
    def __init__(self):
        self.base_dir = os.path.dirname(get_app_resource_path("app.py"))
        # Use workspace manager for bundled app support
        self.venv_python = get_bundled_python()
        self.marker_script = get_marker_script()
        self.marker_executable = get_marker_converter_executable()
        self._marker_api = None

    def _stream_process_output(self, pipe, target_stream, collected_lines):
        """Forward child process output line-by-line to the parent process."""
        buffer = ""
        try:
            while True:
                chunk = pipe.read(1)
                if chunk == '':
                    break

                if chunk in ('\n', '\r'):
                    if buffer:
                        collected_lines.append(buffer + '\n')
                        print(buffer, file=target_stream, flush=True)
                        buffer = ""
                    continue

                buffer += chunk

            if buffer:
                collected_lines.append(buffer)
                print(buffer, file=target_stream, flush=True)
        finally:
            pipe.close()

    def _run_command_streaming(self, cmd, timeout):
        """Run a subprocess and stream stdout/stderr in real time."""
        env = os.environ.copy()
        env.setdefault('PYTHONUNBUFFERED', '1')

        process = subprocess.Popen(
            cmd,
            cwd=self.base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        stdout_lines = []
        stderr_lines = []
        stdout_thread = threading.Thread(
            target=self._stream_process_output,
            args=(process.stdout, sys.stdout, stdout_lines),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._stream_process_output,
            args=(process.stderr, sys.stderr, stderr_lines),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            return_code = process.wait()
        finally:
            stdout_thread.join()
            stderr_thread.join()

        return return_code, ''.join(stdout_lines), ''.join(stderr_lines), timed_out

    def _cleanup_accelerator_cache(self):
        """Release unused accelerator cache without requiring torch at startup."""
        try:
            import torch

            if hasattr(torch, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _load_marker_api(self):
        """Import Marker in-process so models can be reused across a batch."""
        if self._marker_api is not None:
            return self._marker_api

        setup_app_environment()

        marker_root = get_app_resource_path("marker_modified")
        if marker_root and os.path.exists(marker_root) and marker_root not in sys.path:
            sys.path.insert(0, marker_root)

        os.environ.setdefault("PYTHONUNBUFFERED", "1")
        os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
        os.environ.setdefault("GLOG_minloglevel", "2")
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

        from marker.config.parser import ConfigParser
        from marker.models import create_model_dict
        from marker.output import save_output

        self._marker_api = {
            "ConfigParser": ConfigParser,
            "create_model_dict": create_model_dict,
            "save_output": save_output,
        }
        return self._marker_api

    def _create_marker_config_json(self, pdf_dir: str, pdf_name: str, kwargs: dict) -> Optional[str]:
        """Mirror the old CLI path for pdftext_workers > 1."""
        workers = kwargs.get('pdftext_workers')
        if not workers or workers <= 1:
            return None

        config_json = os.path.join(pdf_dir, f".{pdf_name}_config.json")
        with open(config_json, 'w', encoding='utf-8') as f:
            json.dump({"pdftext_workers": workers}, f)
        return config_json

    def _build_marker_cli_options(self, temp_output_dir: str, config_json: Optional[str], kwargs: dict):
        """Build the same Marker options the legacy subprocess path passes."""
        cli_options = {
            "output_dir": temp_output_dir,
            "output_format": kwargs.get('output_format') or "markdown",
            "disable_ocr": True,
        }

        if kwargs.get('pdftext_workers') == 1:
            cli_options["disable_multiprocessing"] = True
        if kwargs.get('debug'):
            cli_options["debug"] = True
        if config_json:
            cli_options["config_json"] = config_json

        return cli_options

    def _convert_single_pdf_with_models(self, pdf_path: str, models: dict, marker_api: dict, **kwargs):
        """Convert one PDF using already-loaded Marker models."""
        pdf_path = os.path.abspath(pdf_path)
        pdf_dir = os.path.dirname(pdf_path)
        pdf_name = Path(pdf_path).stem
        md_path = os.path.join(pdf_dir, f"{pdf_name}.md")
        temp_output_dir = os.path.join(pdf_dir, f".temp_{pdf_name}")
        config_json = None
        start_time = time.time()

        print(f"Converting: {os.path.basename(pdf_path)}")

        if not os.path.exists(pdf_path):
            print(f"❌ Error: File not found: {pdf_path}")
            return False

        if os.path.exists(md_path) and not kwargs.get('overwrite', False):
            print(f"⚠️  Skipping {pdf_name}.md - already exists")
            return True

        try:
            if os.path.exists(temp_output_dir):
                shutil.rmtree(temp_output_dir, ignore_errors=True)
            os.makedirs(temp_output_dir, exist_ok=True)

            config_json = self._create_marker_config_json(pdf_dir, pdf_name, kwargs)
            cli_options = self._build_marker_cli_options(temp_output_dir, config_json, kwargs)

            ConfigParser = marker_api["ConfigParser"]
            save_output = marker_api["save_output"]

            config_parser = ConfigParser(cli_options)
            converter_cls = config_parser.get_converter_cls()
            converter = converter_cls(
                config=config_parser.generate_config_dict(),
                artifact_dict=models,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service()
            )
            rendered = converter(pdf_path)
            out_folder = config_parser.get_output_folder(pdf_path)
            save_output(rendered, out_folder, config_parser.get_base_filename(pdf_path))

            temp_md = os.path.join(out_folder, f"{pdf_name}.md")
            if not os.path.exists(temp_md):
                print(f"❌ Failed to find output for {pdf_name}")
                return False

            os.replace(temp_md, md_path)
            file_size = os.path.getsize(md_path)
            print(f"✅ {pdf_name}.md ({file_size:,} bytes, {time.time() - start_time:.1f}s)")
            return True

        except Exception as e:
            print(f"❌ Error converting {pdf_name}: {e}")
            return False
        finally:
            for name in ("rendered", "converter", "config_parser"):
                if name in locals():
                    del locals()[name]
            self._cleanup_temp_dir(temp_output_dir, None, config_json)
            gc.collect()
            self._cleanup_accelerator_cache()

    def convert_single_pdf_to_same_dir(self, pdf_path: str, **kwargs):
        """Convert single PDF to markdown in the same directory."""
        pdf_path = os.path.abspath(pdf_path)
        pdf_dir = os.path.dirname(pdf_path)
        pdf_name = Path(pdf_path).stem

        print(f"Converting: {os.path.basename(pdf_path)}")

        # Check if file exists
        if not os.path.exists(pdf_path):
            print(f"❌ Error: File not found: {pdf_path}")
            return False

        # Check if markdown already exists
        md_path = os.path.join(pdf_dir, f"{pdf_name}.md")
        if os.path.exists(md_path) and not kwargs.get('overwrite', False):
            print(f"⚠️  Skipping {pdf_name}.md - already exists")
            return True

        try:
            # Create temporary output directory
            temp_output_dir = os.path.join(pdf_dir, f".temp_{pdf_name}")
            os.makedirs(temp_output_dir, exist_ok=True)

            # Build command with parameters
            if is_bundled_app() and self.marker_executable and os.path.exists(self.marker_executable):
                cmd = [self.marker_executable, pdf_path]
            else:
                cmd = [self.venv_python, self.marker_script, pdf_path]
            cmd.extend(['--output_dir', temp_output_dir])
            cmd.extend(['--disable_ocr'])

            # Handle multiprocessing based on pdftext_workers parameter
            if kwargs.get('pdftext_workers') == 1:
                cmd.append('--disable_multiprocessing')
            else:
                # For pdftext_workers > 1, we need to pass this via config
                pass

            # Add optional parameters
            if kwargs.get('debug'):
                cmd.append('--debug')

            if kwargs.get('output_format'):
                cmd.extend(['--output_format', kwargs['output_format']])

            # Create config JSON for pdftext_workers if needed
            config_json = None
            if kwargs.get('pdftext_workers') and kwargs.get('pdftext_workers') > 1:
                config_json = os.path.join(pdf_dir, f".{pdf_name}_config.json")
                with open(config_json, 'w') as f:
                    import json
                    json.dump({"pdftext_workers": kwargs['pdftext_workers']}, f)
                cmd.extend(['--config_json', config_json])

            # Run the command
            start_time = time.time()
            return_code, stdout_text, stderr_text, timed_out = self._run_command_streaming(
                cmd,
                kwargs.get('timeout', 600),
            )
            end_time = time.time()

            if timed_out:
                print(f"❌ Timeout converting {pdf_name}")
                self._cleanup_temp_dir(temp_output_dir, None, config_json)
                return False

            if return_code == 0:
                # Find the generated markdown file and move it to target location
                temp_subdir = os.path.join(temp_output_dir, pdf_name)
                temp_md = os.path.join(temp_subdir, f"{pdf_name}.md")

                if os.path.exists(temp_md):
                    # Move the markdown file to the target location
                    os.rename(temp_md, md_path)

                    # Clean up temp directory
                    self._cleanup_temp_dir(temp_output_dir, temp_subdir, config_json)

                    # Move images if they exist
                    self._move_images_if_needed(temp_subdir, pdf_dir, pdf_name)

                    file_size = os.path.getsize(md_path)
                    print(f"✅ {pdf_name}.md ({file_size:,} bytes, {end_time - start_time:.1f}s)")
                    return True
                else:
                    print(f"❌ Failed to find output for {pdf_name}")
                    self._cleanup_temp_dir(temp_output_dir, None, config_json)
                    return False
            else:
                print(f"❌ Failed to convert {pdf_name}")
                if stderr_text.strip():
                    print("Error:", stderr_text)
                elif stdout_text.strip():
                    print("Output:", stdout_text)
                self._cleanup_temp_dir(temp_output_dir, None, config_json)
                return False

        except subprocess.TimeoutExpired:
            print(f"❌ Timeout converting {pdf_name}")
            self._cleanup_temp_dir(temp_output_dir, None, config_json)
            return False
        except Exception as e:
            print(f"❌ Error converting {pdf_name}: {e}")
            self._cleanup_temp_dir(temp_output_dir, None, config_json)
            return False

    def _cleanup_temp_dir(self, temp_dir: str, keep_subdir: str = None, config_json: str = None):
        """Clean up temporary directory."""
        try:
            # Clean up config JSON file
            if config_json and os.path.exists(config_json):
                os.remove(config_json)

            if keep_subdir and os.path.exists(keep_subdir):
                # Remove all files except the ones we need
                for file in os.listdir(keep_subdir):
                    file_path = os.path.join(keep_subdir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(keep_subdir)

            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isdir(file_path):
                        for subfile in os.listdir(file_path):
                            subfile_path = os.path.join(file_path, subfile)
                            if os.path.isfile(subfile_path):
                                os.remove(subfile_path)
                        os.rmdir(file_path)
                    elif os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(temp_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temp directory: {e}")

    def _move_images_if_needed(self, temp_dir: str, target_dir: str, pdf_name: str):
        """Move image files to target directory if they exist."""
        try:
            if not os.path.exists(temp_dir):
                return

            # Create images subdirectory in target directory
            images_dir = os.path.join(target_dir, f"{pdf_name}_images")

            # Move image files
            moved_count = 0
            for file in os.listdir(temp_dir):
                if file.lower().endswith(('.jpeg', '.jpg', '.png', '.gif', '.bmp')):
                    os.makedirs(images_dir, exist_ok=True)
                    src_path = os.path.join(temp_dir, file)
                    dst_path = os.path.join(images_dir, file)
                    os.rename(src_path, dst_path)
                    moved_count += 1

            if moved_count > 0:
                print(f"📁 Moved {moved_count} image files to {pdf_name}_images/")

        except Exception as e:
            print(f"Warning: Could not move images: {e}")

    def _convert_files_legacy(self, pdf_files: List[Tuple[int, Path]], total_files: int, **kwargs):
        """Convert PDFs with the original one-subprocess-per-PDF path."""
        success_count = 0
        failed_files = []

        for display_index, pdf_file in pdf_files:
            print(f"\n[{display_index}/{total_files}] ", end="")
            if self.convert_single_pdf_to_same_dir(str(pdf_file), **kwargs):
                success_count += 1
            else:
                failed_files.append(pdf_file.name)

        return success_count, failed_files

    def _convert_files_with_model_reuse(self, pdf_files: List[Tuple[int, Path]], total_files: int, **kwargs):
        """Convert PDFs in chunks, reusing Marker models within each chunk."""
        marker_batch_size = max(1, int(kwargs.get('marker_batch_size') or 10))
        success_count = 0
        failed_files = []

        try:
            marker_api = self._load_marker_api()
        except Exception as e:
            print(f"⚠️  Could not start in-process Marker conversion: {e}")
            print("↩️  Falling back to legacy per-PDF conversion.")
            return self._convert_files_legacy(pdf_files, total_files, **kwargs)

        create_model_dict = marker_api["create_model_dict"]
        batch_count = (len(pdf_files) + marker_batch_size - 1) // marker_batch_size

        for batch_index in range(batch_count):
            start = batch_index * marker_batch_size
            end = min(start + marker_batch_size, len(pdf_files))
            batch_files = pdf_files[start:end]
            models = None

            print(f"\n📦 Marker model batch {batch_index + 1}/{batch_count}: {len(batch_files)} PDF(s)")
            try:
                load_start = time.time()
                models = create_model_dict()
                print(f"✅ Marker models loaded once for this batch ({time.time() - load_start:.1f}s)")
            except Exception as e:
                print(f"❌ Failed to load Marker models for batch {batch_index + 1}: {e}")
                print("↩️  Falling back to legacy per-PDF conversion for this batch.")
                batch_success, batch_failed = self._convert_files_legacy(batch_files, total_files, **kwargs)
                success_count += batch_success
                failed_files.extend(batch_failed)
                continue

            try:
                for display_index, pdf_file in batch_files:
                    print(f"\n[{display_index}/{total_files}] ", end="")
                    if self._convert_single_pdf_with_models(str(pdf_file), models, marker_api, **kwargs):
                        success_count += 1
                    else:
                        print(f"↩️  Retrying {pdf_file.name} with legacy per-PDF conversion.")
                        if self.convert_single_pdf_to_same_dir(str(pdf_file), **kwargs):
                            success_count += 1
                        else:
                            failed_files.append(pdf_file.name)
            finally:
                del models
                gc.collect()
                self._cleanup_accelerator_cache()
                print(f"🧹 Released Marker models for batch {batch_index + 1}/{batch_count}")

        return success_count, failed_files

    def convert_directory_to_same_dir(self, directory: str, **kwargs):
        """Convert all PDFs in directory to markdown in the same directory."""
        directory = os.path.abspath(directory)

        if not os.path.exists(directory):
            print(f"❌ Error: Directory not found: {directory}")
            return False

        # Find all PDF files
        pdf_files = []
        for ext in ['*.pdf', '*.PDF']:
            pdf_files.extend(Path(directory).glob(ext))

        if not pdf_files:
            print(f"❌ No PDF files found in {directory}")
            return False

        print(f"📚 Found {len(pdf_files)} PDF files in {os.path.basename(directory)}")

        # Count existing MD files
        existing_md = 0
        for pdf_file in pdf_files:
            md_path = os.path.join(directory, f"{pdf_file.stem}.md")
            if os.path.exists(md_path):
                existing_md += 1

        if existing_md > 0 and not kwargs.get('overwrite', False):
            print(f"⚠️  {existing_md} markdown files already exist (use --overwrite to replace)")
            pending = len(pdf_files) - existing_md
            print(f"📄 Will convert {pending} new files")
        elif existing_md > 0 and kwargs.get('overwrite', False):
            print(f"🔄 Will overwrite {existing_md} existing markdown files")

        # Convert each PDF
        skipped_files = []
        pending_files = []
        total_start_time = time.time()

        for i, pdf_file in enumerate(pdf_files, 1):
            # Check if markdown already exists
            md_path = os.path.join(directory, f"{pdf_file.stem}.md")
            if os.path.exists(md_path) and not kwargs.get('overwrite', False):
                skipped_files.append(pdf_file.name)
                continue

            pending_files.append((i, pdf_file))

        if pending_files and kwargs.get('output_format', 'markdown') == 'markdown':
            success_count, failed_files = self._convert_files_with_model_reuse(
                pending_files,
                len(pdf_files),
                **kwargs,
            )
        else:
            success_count, failed_files = self._convert_files_legacy(
                pending_files,
                len(pdf_files),
                **kwargs,
            )

        total_end_time = time.time()

        print(f"\n🎉 Batch conversion completed!")
        print(f"✅ Successfully converted: {success_count} files")
        if skipped_files:
            print(f"⏭️  Skipped (already exists): {len(skipped_files)} files")
        if failed_files:
            print(f"❌ Failed: {len(failed_files)} files")
            for file in failed_files:
                print(f"   - {file}")
        print(f"⏱️  Total time: {total_end_time - total_start_time:.1f} seconds")
        print(f"📁 Output directory: {directory}")

        return success_count > 0


def main():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True, write_through=True)

    parser = argparse.ArgumentParser(
        description='Convert PDF files to markdown in the same directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all PDFs in content/1214 to markdown in the same directory
  python convert_same_directory.py content/1214

  # Convert with debug info and overwrite existing files
  python convert_same_directory.py content/1214 --debug --overwrite

  # Convert to JSON format
  python convert_same_directory.py content/1214 --output_format json

  # Convert with more workers for faster processing
  python convert_same_directory.py content/1214 --pdftext_workers 4

  # High performance conversion (multiple workers + debug + overwrite)
  python convert_same_directory.py content/1214 --pdftext_workers 8 --debug --overwrite

Worker Configuration:
  - pdftext_workers 1: Single thread, most stable (default)
  - pdftext_workers 2-4: Faster processing, moderate memory usage
  - pdftext_workers 8+: Maximum speed, high memory usage
  - Note: More workers require more RAM and CPU cores
        """
    )

    parser.add_argument(
        'directory',
        help='Directory containing PDF files to convert'
    )

    parser.add_argument(
        '--output_format',
        choices=['markdown', 'json', 'html'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug mode'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing markdown files'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Timeout per file in seconds (default: 600)'
    )

    parser.add_argument(
        '--pdftext_workers',
        type=int,
        default=1,
        help='Number of pdftext workers (1-16, default: 1). More workers = faster processing but more memory usage.'
    )

    parser.add_argument(
        '--marker_batch_size',
        type=int,
        default=10,
        help='Number of PDFs to process per Marker model-loading session (default: 10).'
    )

    args = parser.parse_args()

    # Create converter instance
    converter = SameDirectoryConverter()

    # Extract parameters
    params = {
        'output_format': args.output_format,
        'debug': args.debug,
        'overwrite': args.overwrite,
        'timeout': args.timeout,
        'pdftext_workers': args.pdftext_workers,
        'marker_batch_size': args.marker_batch_size
    }

    # Convert
    success = converter.convert_directory_to_same_dir(args.directory, **params)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
