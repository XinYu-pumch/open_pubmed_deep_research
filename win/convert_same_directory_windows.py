#!/usr/bin/env python
"""
Windows CPU-only wrapper for the existing PDF -> Markdown converter.
"""

import os
import importlib.util
import sys
import time
from pathlib import Path

from bootstrap_windows import PROJECT_ROOT, setup_windows_runtime


setup_windows_runtime(patch_core=False)

CONVERTER_PATH = os.path.join(PROJECT_ROOT, "convert_same_directory.py")


def _collect_pdf_files(directory: str):
    pdf_by_path = {}
    for item in Path(directory).iterdir():
        if item.is_file() and item.suffix.lower() == ".pdf":
            pdf_by_path[str(item.resolve()).lower()] = item
    return sorted(pdf_by_path.values(), key=lambda p: p.name.lower())


def _patch_converter_module(module):
    def convert_directory_to_same_dir(self, directory: str, **kwargs):
        directory = os.path.abspath(directory)

        if not os.path.exists(directory):
            print(f"Error: Directory not found: {directory}")
            return False

        pdf_files = _collect_pdf_files(directory)

        if not pdf_files:
            print(f"No PDF files found in {directory}")
            return False

        print(f"Found {len(pdf_files)} PDF files in {os.path.basename(directory)}")

        existing_md = 0
        for pdf_file in pdf_files:
            md_path = os.path.join(directory, f"{pdf_file.stem}.md")
            if os.path.exists(md_path):
                existing_md += 1

        if existing_md > 0 and not kwargs.get("overwrite", False):
            print(f"{existing_md} markdown files already exist (use --overwrite to replace)")
            pending = len(pdf_files) - existing_md
            print(f"Will convert {pending} new files")
        elif existing_md > 0 and kwargs.get("overwrite", False):
            print(f"Will overwrite {existing_md} existing markdown files")

        skipped_files = []
        pending_files = []
        total_start_time = time.time()

        for i, pdf_file in enumerate(pdf_files, 1):
            md_path = os.path.join(directory, f"{pdf_file.stem}.md")
            if os.path.exists(md_path) and not kwargs.get("overwrite", False):
                skipped_files.append(pdf_file.name)
                continue
            pending_files.append((i, pdf_file))

        if pending_files and kwargs.get("output_format", "markdown") == "markdown":
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

        print("\nBatch conversion completed!")
        print(f"Successfully converted: {success_count} files")
        if skipped_files:
            print(f"Skipped (already exists): {len(skipped_files)} files")
        if failed_files:
            print(f"Failed: {len(failed_files)} files")
            for file in failed_files:
                print(f"   - {file}")
        print(f"Total time: {total_end_time - total_start_time:.1f} seconds")
        print(f"Output directory: {directory}")

        return success_count > 0 or bool(skipped_files)

    module.SameDirectoryConverter.convert_directory_to_same_dir = convert_directory_to_same_dir


def main():
    spec = importlib.util.spec_from_file_location("root_convert_same_directory", CONVERTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _patch_converter_module(module)
    module.main()


if __name__ == "__main__":
    main()
