#!/usr/bin/env python3
"""
Enrich top suppliers with SII data (Start Date, Activity Code/Giro).
Queries the public SII pages to extract basic tax payer information.
"""
import sys
import logging
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal, Party  # type: ignore
from integrations.sii import enrich_party_sii  # type: ignore
from sqlalchemy import text  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_SUPPLIERS = 50

def get_top_suppliers(db, limit=MAX_SUPPLIERS):
    """Get the top suppliers that don't have SII info updated recently."""
    rows = db.execute(text("""
        SELECT p.rut, p.name 
        FROM parties p
        LEFT JOIN (
            SELECT supplier_rut, COUNT(*) AS alert_count
            FROM alerts WHERE supplier_rut IS NOT NULL AND supplier_rut NOT LIKE 'CL-MP-%'
            GROUP BY supplier_rut
        ) alert_stats ON alert_stats.supplier_rut = p.rut
        WHERE p.rut IS NOT NULL AND LENGTH(p.rut) >= 7
          AND (p.sii_activity_code IS NULL OR p.sii_start_date IS NULL)
        ORDER BY COALESCE(alert_stats.alert_count, 0) DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return rows

def main():
    db = SessionLocal()
    print("=" * 70)
    print("  SII ENRICHMENT: Fetching Start Dates and Activity Codes (Giros)")
    print("=" * 70)
    
    suppliers = get_top_suppliers(db, MAX_SUPPLIERS)
    print(f"[*] Found {len(suppliers)} suppliers missing SII data. Starting extraction...")

    enriched_count = 0
    
    for i, s in enumerate(suppliers):
        # Add slight delay so we don't spam the public endpoint
        time.sleep(0.1)
        
        sii_data = enrich_party_sii(s.rut, db)
        
        if sii_data and sii_data.get("valid"):
            actividad = sii_data.get('actividad', 'Desconocido')
            inicio = sii_data.get('inicio_actividades', 'Desconocido')
            
            # Truncate for display
            display_act = (actividad[:40] + '...') if actividad and len(actividad) > 40 else actividad
            
            if i % 10 == 0 or i < 5:
                print(f"  [{i+1:3d}/{len(suppliers)}] {s.rut:12s} -> Inicio: {inicio} | Giro: {display_act}")
            enriched_count += 1
        else:
            if i % 10 == 0 or i < 5:
                print(f"  [{i+1:3d}/{len(suppliers)}] {s.rut:12s} -> [!] No data found or invalid RUT")

    print("=" * 70)
    print(f"[*] ENRICHMENT COMPLETE")
    print(f"[*] Total suppliers enriched from SII: {enriched_count}")
    print("=" * 70)
    db.close()

if __name__ == "__main__":
    main()
