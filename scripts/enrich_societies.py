"""
Run the Registro de Sociedades Enrichment over Top Suppliers (Corporate Structure).
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal, Party, ExternalData  # type: ignore
from integrations.registro_sociedades import parse_res_data  # type: ignore
from sqlalchemy import text  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_SUPPLIERS = 300

def get_top_suppliers(db, limit=MAX_SUPPLIERS):
    return db.execute(text("""
        SELECT p.rut, p.name, 
               COALESCE(alert_stats.alert_count, 0) AS alert_count
        FROM parties p
        LEFT JOIN (
            SELECT supplier_rut, COUNT(*) AS alert_count
            FROM alerts WHERE supplier_rut IS NOT NULL AND supplier_rut NOT LIKE 'CL-MP-%'
            GROUP BY supplier_rut
        ) alert_stats ON alert_stats.supplier_rut = p.rut
        WHERE p.rut IS NOT NULL AND LENGTH(p.rut) >= 7 AND p.party_type != 'natural'
        ORDER BY COALESCE(alert_stats.alert_count, 0) DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()

def enrich_supplier(db, rut: str, name: str):
    societal_data = parse_res_data(rut, name)
    if not societal_data: return False

    try:
        ext = db.get(ExternalData, (rut, "registro_sociedades"))
        if not ext: ext = ExternalData(rut=rut, source="registro_sociedades")
        ext.raw_data = societal_data
        ext.last_updated = datetime.utcnow()
        db.merge(ext)
        db.commit()
    except Exception as e:
        logger.error(f"DB error {rut}: {e}")
        db.rollback()
        
    return True

def main():
    db = SessionLocal()
    print("=" * 70)
    print("  CORP. STRUCTURE Enrichment: Fetching Socios / Representantes (RES)")
    suppliers = get_top_suppliers(db, MAX_SUPPLIERS)
    
    enriched_count: int = 0
    for i, s in enumerate(suppliers):
        if enrich_supplier(db, s.rut, s.name):
            enriched_count = int(enriched_count + 1)  # type: ignore
            if i % 10 == 0 or i < 5:
                print(f"  [{i+1:3d}/{len(suppliers)}] {s.rut:12s} -> Identidad Legal Levantada")
                
    print("=" * 70)
    print(f"  Total enriched: {enriched_count}")
    print("=" * 70)
    db.close()

if __name__ == "__main__":
    main()
