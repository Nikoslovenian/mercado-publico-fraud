"""
Extractor: discovers all OCDS JSON files in the source directory.
Handles both already-extracted folders and .7z compressed archives.
"""
import os
import glob
import logging
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


def extract_7z_archives(source_dir: str) -> None:
    """Extract all .7z archives in source_dir that haven't been extracted yet."""
    try:
        import py7zr
    except ImportError:
        logger.warning("py7zr not installed. Skipping .7z extraction.")
        return

    archives = list(Path(source_dir).glob("*.7z"))
    if not archives:
        logger.info("No .7z archives found.")
        return

    for archive_path in archives:
        # Derive output folder name from archive stem (e.g., 202501.7z → 202501/)
        out_dir = archive_path.parent / archive_path.stem
        if out_dir.exists() and any(out_dir.glob("*.json")):
            logger.info(f"Already extracted: {archive_path.name} → {out_dir}")
            continue
        out_dir.mkdir(exist_ok=True)
        logger.info(f"Extracting {archive_path.name} → {out_dir} ...")
        try:
            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                z.extractall(path=out_dir)
            logger.info(f"Done: {archive_path.name}")
        except Exception as e:
            logger.error(f"Failed to extract {archive_path.name}: {e}")


def iter_json_files(source_dir: str) -> Iterator[Path]:
    """
    Yield paths to all JSON files recursively under source_dir,
    skipping the project folder itself.
    """
    source_path = Path(source_dir)
    project_dir = source_path / "mercado-publico-fraud"

    for json_file in sorted(source_path.rglob("*.json")):
        # Skip any files inside our own project directory
        try:
            json_file.relative_to(project_dir)
            continue  # It's inside the project dir, skip it
        except ValueError:
            pass
        yield json_file


def count_json_files(source_dir: str) -> int:
    return sum(1 for _ in iter_json_files(source_dir))
