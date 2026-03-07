#!/usr/bin/env python3
"""Check which alert types store OCDS IDs vs real RUTs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check which alert_types have CL-MP- format supplier_rut
print("=== Alerts with OCDS-format supplier_rut (CL-MP-) ===")
rows = db.execute(text("""
    SELECT alert_type, COUNT(*) as cnt,
           COUNT(CASE WHEN supplier_rut LIKE 'CL-MP-%' THEN 1 END) as ocds_format,
           COUNT(CASE WHEN supplier_rut NOT LIKE 'CL-MP-%' AND supplier_rut IS NOT NULL AND supplier_rut != '' THEN 1 END) as rut_format,
           COUNT(CASE WHEN supplier_rut IS NULL OR supplier_rut = '' THEN 1 END) as null_rut
    FROM alerts
    GROUP BY alert_type
    ORDER BY alert_type
""")).fetchall()

for r in rows:
    print(f"  {r.alert_type:6s}: total={r.cnt:5d} | OCDS={r.ocds_format:5d} | RUT={r.rut_format:5d} | null={r.null_rut:5d}")

# Same check for buyer_rut
print("\n=== Alerts with OCDS-format buyer_rut (CL-MP-) ===")
rows2 = db.execute(text("""
    SELECT alert_type,
           COUNT(CASE WHEN buyer_rut LIKE 'CL-MP-%' THEN 1 END) as ocds_format,
           COUNT(CASE WHEN buyer_rut NOT LIKE 'CL-MP-%' AND buyer_rut IS NOT NULL AND buyer_rut != '' THEN 1 END) as rut_format,
           COUNT(CASE WHEN buyer_rut IS NULL OR buyer_rut = '' THEN 1 END) as null_rut
    FROM alerts
    GROUP BY alert_type
    ORDER BY alert_type
""")).fetchall()

for r in rows2:
    print(f"  {r.alert_type:6s}: OCDS={r.ocds_format:5d} | RUT={r.rut_format:5d} | null={r.null_rut:5d}")

db.close()
