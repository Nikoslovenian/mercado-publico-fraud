#!/usr/bin/env python3
"""
Load items from OCDS JSON files for existing procurements.
Focused script to populate the items table without re-running full ETL.
Also fixes phone/email and derives party_type.
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import logging
from tqdm import tqdm
from database import init_db, SessionLocal, Item, Party
from etl.extractor import iter_json_files, count_json_files
from etl.parser import parse_ocds_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DIR = str(Path(__file__).parent.parent.parent)


def derive_party_type(rut: str) -> str:
    """Chilean RUT convention: < 50M = natural person, >= 50M = juridica."""
    if not rut:
        return None
    digits = re.sub(r'[^0-9]', '', rut)
    if not digits:
        return None
    try:
        num = int(digits[:-1]) if len(digits) > 1 else int(digits)
        return "natural" if num < 50000000 else "juridica"
    except ValueError:
        return None


def main():
    init_db()
    db = SessionLocal()

    total = count_json_files(SOURCE_DIR)
    logger.info(f"Found {total:,} JSON files")

    items_loaded = 0
    parties_updated = 0
    batch_items = []
    existing_item_ids = set()

    # Pre-load existing item IDs to avoid slow per-item lookups
    logger.info("Loading existing item IDs...")
    for row in db.query(Item.id).all():
        existing_item_ids.add(row[0])
    logger.info(f"Existing items: {len(existing_item_ids)}")

    try:
        with tqdm(total=total, unit="files", ncols=80) as pbar:
            for json_path in iter_json_files(SOURCE_DIR):
                pbar.set_postfix({"items": items_loaded, "parties": parties_updated})
                try:
                    records = parse_ocds_file(json_path)
                    if not records:
                        pbar.update(1)
                        continue

                    for rec in records:
                        # --- Load items ---
                        for item_data in rec.get("items", []):
                            item_id = item_data.get("id")
                            if not item_id or item_id in existing_item_ids:
                                continue
                            existing_item_ids.add(item_id)
                            batch_items.append(Item(**item_data))
                            items_loaded += 1

                        # --- Fix party phone/email/type ---
                        for party_data in rec.get("parties", []):
                            rut = party_data.get("rut")
                            if not rut:
                                continue
                            phone = party_data.get("phone", "").strip()
                            email = party_data.get("email", "").strip()
                            p_type = derive_party_type(rut)

                            party = db.get(Party, rut)
                            if party:
                                changed = False
                                if phone and not party.phone:
                                    party.phone = phone
                                    changed = True
                                if email and not party.email:
                                    party.email = email
                                    changed = True
                                if p_type and not party.party_type:
                                    party.party_type = p_type
                                    changed = True
                                if changed:
                                    parties_updated += 1

                except Exception as e:
                    logger.debug(f"Error: {json_path.name}: {e}")

                if len(batch_items) >= 5000:
                    db.add_all(batch_items)
                    db.commit()
                    batch_items = []

                pbar.update(1)

        # Final batch
        if batch_items:
            db.add_all(batch_items)
            db.commit()

        # Update party_type for ALL parties that don't have it yet
        logger.info("Updating party_type for remaining parties...")
        parties_no_type = db.query(Party).filter(Party.party_type.is_(None)).all()
        for p in parties_no_type:
            pt = derive_party_type(p.rut)
            if pt:
                p.party_type = pt
        db.commit()
        logger.info(f"Updated {len(parties_no_type)} party types")

    finally:
        db.close()

    logger.info("=" * 60)
    logger.info(f"Items loaded: {items_loaded:,}")
    logger.info(f"Parties updated (phone/email/type): {parties_updated:,}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
