#!/usr/bin/env python3
"""Check current enrichment status of parties."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

total = db.execute(text('SELECT COUNT(*) FROM parties')).scalar()
no_sii = db.execute(text('SELECT COUNT(*) FROM parties WHERE sii_start_date IS NULL')).scalar()
with_sii = db.execute(text('SELECT COUNT(*) FROM parties WHERE sii_start_date IS NOT NULL')).scalar()
natural = db.execute(text("SELECT COUNT(*) FROM parties WHERE party_type = 'natural'")).scalar()
juridica = db.execute(text("SELECT COUNT(*) FROM parties WHERE party_type = 'juridica'")).scalar()

print(f"Total parties: {total}")
print(f"With SII data: {with_sii}")
print(f"Without SII data: {no_sii}")
print(f"Natural persons: {natural}")
print(f"Juridica: {juridica}")

print("\n--- Top 20 suppliers by alert count ---")
rows = db.execute(text("""
    SELECT a.supplier_rut, p.name, p.party_type, p.sii_start_date,
           COUNT(*) as alert_count, SUM(a.amount_involved) as total_amount
    FROM alerts a
    LEFT JOIN parties p ON p.rut = a.supplier_rut
    WHERE a.supplier_rut IS NOT NULL AND a.supplier_rut != ''
    GROUP BY a.supplier_rut
    ORDER BY alert_count DESC
    LIMIT 20
""")).fetchall()
for r in rows:
    name = (r.name or "?")[:35]
    ptype = r.party_type or "?"
    sii = str(r.sii_start_date or "none")[:10]
    amt = r.total_amount or 0
    print(f"  {r.supplier_rut:15s} | {name:35s} | type={ptype:10s} | sii={sii:10s} | alerts={r.alert_count:4d} | ${amt:>15,.0f}")

print("\n--- Alert distribution by type ---")
rows2 = db.execute(text("""
    SELECT alert_type, severity, COUNT(*) as cnt
    FROM alerts
    GROUP BY alert_type, severity
    ORDER BY alert_type, severity
""")).fetchall()
current_type = None
for r in rows2:
    if r.alert_type != current_type:
        current_type = r.alert_type
        print(f"  {r.alert_type}:")
    print(f"    {r.severity}: {r.cnt}")

db.close()
