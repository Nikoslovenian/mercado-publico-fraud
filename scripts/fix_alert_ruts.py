#!/usr/bin/env python3
"""
Migration script: Fix alert RUTs that store OCDS identifiers (CL-MP-XXXXX)
instead of real Chilean RUTs.

Uses the procurement_parties table to map (ocid, role) -> real party_rut,
then updates alerts.supplier_rut, supplier_name, buyer_rut, buyer_name.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal
from sqlalchemy import text


def main():
    db = SessionLocal()
    start = time.time()

    print("=" * 70)
    print("  Fix Alert RUTs: CL-MP-XXXXX -> Real Chilean RUTs")
    print("=" * 70)

    # ── Step 0: Diagnostics ──────────────────────────────────────────────
    total_alerts = db.execute(text("SELECT COUNT(*) FROM alerts")).scalar()
    bad_supplier = db.execute(text(
        "SELECT COUNT(*) FROM alerts WHERE supplier_rut LIKE 'CL-MP-%'"
    )).scalar()
    bad_buyer = db.execute(text(
        "SELECT COUNT(*) FROM alerts WHERE buyer_rut LIKE 'CL-MP-%'"
    )).scalar()
    total_parties = db.execute(text(
        "SELECT COUNT(DISTINCT party_rut) FROM procurement_parties"
    )).scalar()
    total_mappings = db.execute(text(
        "SELECT COUNT(*) FROM procurement_parties"
    )).scalar()

    print(f"\n  Total alerts:                    {total_alerts:,}")
    print(f"  Alerts with CL-MP supplier_rut:  {bad_supplier:,}")
    print(f"  Alerts with CL-MP buyer_rut:     {bad_buyer:,}")
    print(f"  Procurement-party mappings:      {total_mappings:,}")
    print(f"  Distinct party RUTs:             {total_parties:,}")

    if bad_supplier == 0 and bad_buyer == 0:
        print("\n  Nothing to fix -- all RUTs already use real format.")
        db.close()
        return

    # ── Step 1: Fix supplier_rut + supplier_name ─────────────────────────
    print(f"\n--- Step 1: Fixing supplier_rut ({bad_supplier:,} alerts) ---")

    result_supplier = db.execute(text("""
        UPDATE alerts SET
            supplier_rut = (
                SELECT pp.party_rut
                FROM procurement_parties pp
                WHERE pp.procurement_ocid = alerts.ocid
                  AND pp.role = 'supplier'
                LIMIT 1
            ),
            supplier_name = (
                SELECT p.name
                FROM procurement_parties pp
                JOIN parties p ON p.rut = pp.party_rut
                WHERE pp.procurement_ocid = alerts.ocid
                  AND pp.role = 'supplier'
                LIMIT 1
            )
        WHERE supplier_rut LIKE 'CL-MP-%'
          AND ocid IS NOT NULL
    """))
    fixed_supplier = result_supplier.rowcount
    print(f"  Updated: {fixed_supplier:,} alerts")

    # Check how many still have CL-MP after update (no matching party found)
    still_bad_supplier = db.execute(text(
        "SELECT COUNT(*) FROM alerts WHERE supplier_rut LIKE 'CL-MP-%'"
    )).scalar()
    if still_bad_supplier > 0:
        print(f"  WARNING: {still_bad_supplier:,} alerts still have CL-MP supplier_rut"
              " (no matching procurement_parties entry)")

    # ── Step 2: Fix buyer_rut + buyer_name ───────────────────────────────
    print(f"\n--- Step 2: Fixing buyer_rut ({bad_buyer:,} alerts) ---")

    result_buyer = db.execute(text("""
        UPDATE alerts SET
            buyer_rut = (
                SELECT pp.party_rut
                FROM procurement_parties pp
                WHERE pp.procurement_ocid = alerts.ocid
                  AND pp.role = 'buyer'
                LIMIT 1
            ),
            buyer_name = (
                SELECT p.name
                FROM procurement_parties pp
                JOIN parties p ON p.rut = pp.party_rut
                WHERE pp.procurement_ocid = alerts.ocid
                  AND pp.role = 'buyer'
                LIMIT 1
            )
        WHERE buyer_rut LIKE 'CL-MP-%'
          AND ocid IS NOT NULL
    """))
    fixed_buyer = result_buyer.rowcount
    print(f"  Updated: {fixed_buyer:,} alerts")

    still_bad_buyer = db.execute(text(
        "SELECT COUNT(*) FROM alerts WHERE buyer_rut LIKE 'CL-MP-%'"
    )).scalar()
    if still_bad_buyer > 0:
        print(f"  WARNING: {still_bad_buyer:,} alerts still have CL-MP buyer_rut"
              " (no matching procurement_parties entry)")

    # ── Step 3: Commit ───────────────────────────────────────────────────
    db.commit()
    elapsed = time.time() - start

    # ── Step 4: Post-fix verification ────────────────────────────────────
    print("\n--- Verification ---")
    sample_suppliers = db.execute(text(
        "SELECT DISTINCT supplier_rut FROM alerts "
        "WHERE supplier_rut IS NOT NULL LIMIT 10"
    )).fetchall()
    print("  Sample supplier_rut values after fix:")
    for row in sample_suppliers:
        print(f"    {row[0]}")

    sample_buyers = db.execute(text(
        "SELECT DISTINCT buyer_rut FROM alerts "
        "WHERE buyer_rut IS NOT NULL LIMIT 10"
    )).fetchall()
    print("  Sample buyer_rut values after fix:")
    for row in sample_buyers:
        print(f"    {row[0]}")

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  MIGRATION COMPLETE")
    print(f"  Supplier RUTs fixed:  {fixed_supplier:,}")
    print(f"  Buyer RUTs fixed:     {fixed_buyer:,}")
    print(f"  Still CL-MP supplier: {still_bad_supplier:,}")
    print(f"  Still CL-MP buyer:    {still_bad_buyer:,}")
    print(f"  Time elapsed:         {elapsed:.1f}s")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
