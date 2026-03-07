#!/usr/bin/env python3
"""
ETL Runner: extracts compressed archives and loads all OCDS JSON files into the database.
Usage: python scripts/run_etl.py [--source-dir PATH] [--batch-size N] [--skip-extract]
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from tqdm import tqdm
from database import init_db, SessionLocal
from etl.extractor import extract_7z_archives, iter_json_files, count_json_files
from etl.parser import parse_ocds_file
from etl.loader import load_parsed_records

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("etl.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

DEFAULT_SOURCE = str(Path(__file__).parent.parent.parent)  # Desktop/Mercado Publico 2025


def main():
    parser = argparse.ArgumentParser(description="Load Mercado Público OCDS data into database")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE, help="Directory containing JSON files and 7z archives")
    parser.add_argument("--batch-size", type=int, default=200, help="Records per DB commit batch")
    parser.add_argument("--skip-extract", action="store_true", help="Skip .7z extraction step")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files to process (0 = all)")
    args = parser.parse_args()

    source_dir = args.source_dir
    logger.info(f"Source directory: {source_dir}")

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Extract compressed archives
    if not args.skip_extract:
        logger.info("Checking for .7z archives to extract...")
        extract_7z_archives(source_dir)

    # Count files
    logger.info("Counting JSON files...")
    total_files = count_json_files(source_dir)
    logger.info(f"Found {total_files:,} JSON files to process")

    if args.limit:
        total_files = min(total_files, args.limit)
        logger.info(f"Limiting to {total_files:,} files")

    # Process files in batches
    db = SessionLocal()
    stats_total = {"procurements": 0, "parties": 0, "bids": 0, "awards": 0, "items": 0}
    batch = []
    files_processed = 0
    files_skipped = 0
    files_error = 0

    try:
        with tqdm(total=total_files, unit="files", ncols=80) as pbar:
            for json_path in iter_json_files(source_dir):
                if args.limit and files_processed >= args.limit:
                    break

                pbar.set_postfix({"procs": stats_total["procurements"], "alerts": "—"})

                try:
                    records = parse_ocds_file(json_path)
                    if records:
                        batch.extend(records)
                        files_processed += 1
                    else:
                        files_skipped += 1
                except Exception as e:
                    logger.debug(f"Error parsing {json_path.name}: {e}")
                    files_error += 1

                if len(batch) >= args.batch_size:
                    stats = load_parsed_records(db, batch)
                    for k, v in stats.items():
                        stats_total[k] = stats_total.get(k, 0) + v
                    batch = []

                pbar.update(1)

        # Final batch
        if batch:
            stats = load_parsed_records(db, batch)
            for k, v in stats.items():
                stats_total[k] = stats_total.get(k, 0) + v

    finally:
        db.close()

    logger.info("=" * 60)
    logger.info("ETL COMPLETE")
    logger.info(f"  Files processed: {files_processed:,}")
    logger.info(f"  Files skipped:   {files_skipped:,}")
    logger.info(f"  Files with errors: {files_error:,}")
    logger.info(f"  Procurements loaded: {stats_total['procurements']:,}")
    logger.info(f"  Parties loaded:      {stats_total['parties']:,}")
    logger.info(f"  Bids loaded:         {stats_total['bids']:,}")
    logger.info(f"  Awards loaded:       {stats_total['awards']:,}")
    logger.info(f"  Items loaded:        {stats_total['items']:,}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
