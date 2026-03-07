#!/usr/bin/env python3
"""
Enrich top suppliers with InfoLobby audiences (SPARQL/Open Data).
"""
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal, Party, ExternalData  # type: ignore
from integrations.infolobby import get_audiences  # type: ignore
from sqlalchemy import text  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_SUPPLIERS = 300  

def get_top_suppliers(db, limit=MAX_SUPPLIERS):
    rows = db.execute(text("""
        SELECT p.rut, p.name, 
               COALESCE(alert_stats.alert_count, 0) AS alert_count
        FROM parties p
        LEFT JOIN (
            SELECT supplier_rut, COUNT(*) AS alert_count
            FROM alerts WHERE supplier_rut IS NOT NULL AND supplier_rut NOT LIKE 'CL-MP-%'
            GROUP BY supplier_rut
        ) alert_stats ON alert_stats.supplier_rut = p.rut
        WHERE p.rut IS NOT NULL AND LENGTH(p.rut) >= 7
        ORDER BY COALESCE(alert_stats.alert_count, 0) DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return rows

def enrich_supplier(db, rut: str, name: str):
    audiencias = get_audiences(rut, name)
    if not audiencias:
        return 0

    try:
        ext = db.get(ExternalData, (rut, "infolobby"))
        if not ext:
            ext = ExternalData(rut=rut, source="infolobby")
        ext.raw_data = {"audiencias": audiencias, "total": len(audiencias)}
        ext.last_updated = datetime.utcnow()
        db.merge(ext)
        db.commit()
    except Exception as e:
        logger.error(f"  DB error for {rut}: {e}")
        db.rollback()

    return len(audiencias)

def main():
    db = SessionLocal()
    print("=" * 70)
    print("  INFOLOBBY Enrichment: Fetching Audiences")
    suppliers = get_top_suppliers(db, MAX_SUPPLIERS)
    print(f"  Found {len(suppliers)} suppliers to enrich")

    enriched_count: int = 0
    audiences_found: int = 0
    
    for i, s in enumerate(suppliers):
        found = enrich_supplier(db, s.rut, s.name)
        if found:
            enriched_count = int(enriched_count + 1)  # type: ignore
            audiences_found = int(audiences_found + found)  # type: ignore
            print(f"  [{i+1:3d}/{len(suppliers)}] {s.rut:12s} -> {found} audiencias encontradas.")
            
    print("=" * 70)
    print("  ENRICHMENT COMPLETE")
    print(f"  Suppliers with InfoLobby activity: {enriched_count}")
    print(f"  Total meetings downloaded: {audiences_found}")
    print("=" * 70)
    db.close()

if __name__ == "__main__":
    main()
