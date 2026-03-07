#!/usr/bin/env python3
"""Check RUT format differences between tables."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check awards.supplier_rut format
print("=== awards.supplier_rut samples ===")
rows = db.execute(text("SELECT DISTINCT supplier_rut FROM awards LIMIT 10")).fetchall()
for r in rows:
    print(f"  {r[0]}")

# Check parties.rut format
print("\n=== parties.rut samples ===")
rows = db.execute(text("SELECT rut, name FROM parties LIMIT 10")).fetchall()
for r in rows:
    print(f"  {r[0]:20s} -> {r[1]}")

# Check procurement_parties mapping
print("\n=== procurement_parties samples (supplier) ===")
rows = db.execute(text("""
    SELECT pp.party_rut, p.name, a.supplier_rut, a.ocid
    FROM procurement_parties pp
    JOIN parties p ON p.rut = pp.party_rut
    JOIN awards a ON a.ocid = pp.procurement_ocid
    WHERE pp.role = 'supplier'
    LIMIT 10
""")).fetchall()
for r in rows:
    print(f"  party_rut={r[0]:15s} | name={r[1][:30]:30s} | award.supplier_rut={r[2]:20s}")

# Check alerts.supplier_rut format
print("\n=== alerts.supplier_rut samples ===")
rows = db.execute(text("SELECT DISTINCT supplier_rut FROM alerts WHERE supplier_rut IS NOT NULL LIMIT 15")).fetchall()
for r in rows:
    print(f"  {r[0]}")

# How many alerts have a matching party?
print("\n=== Alert-Party join stats ===")
total_alerts = db.execute(text("SELECT COUNT(*) FROM alerts WHERE supplier_rut IS NOT NULL")).scalar()
matching = db.execute(text("""
    SELECT COUNT(*) FROM alerts a
    JOIN parties p ON p.rut = a.supplier_rut
    WHERE a.supplier_rut IS NOT NULL
""")).scalar()
print(f"  Total alerts with supplier_rut: {total_alerts}")
print(f"  Alerts matching parties.rut: {matching}")
print(f"  Alerts NOT matching: {total_alerts - matching}")

db.close()
