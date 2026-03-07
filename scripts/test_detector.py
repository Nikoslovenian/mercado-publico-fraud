#!/usr/bin/env python3
"""Quick test of one detector to check for hangs."""
import sys
import os
from pathlib import Path

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

print("Starting test...", flush=True)

try:
    from database import init_db, SessionLocal, Alert
    from sqlalchemy import text
    print("Imports OK", flush=True)

    init_db()
    print("DB init OK", flush=True)

    db = SessionLocal()
    print("Session OK", flush=True)

    # Check if DB is locked
    count = db.execute(text("SELECT COUNT(*) FROM alerts")).scalar()
    print(f"Current alerts: {count}", flush=True)

    # Try to clear
    print("Clearing alerts...", flush=True)
    db.execute(text("DELETE FROM alerts"))
    db.commit()
    print("Cleared!", flush=True)

    # Test one simple detector
    print("Importing VELO (award_speed)...", flush=True)
    from fraud import award_speed
    print("Running VELO...", flush=True)
    alerts = award_speed.detect(db)
    print(f"VELO: {len(alerts)} alerts", flush=True)

    # Save them
    for a in alerts:
        alert = Alert(
            ocid=a.get("ocid"),
            alert_type=a.get("alert_type"),
            severity=a.get("severity"),
            title=a.get("title"),
            description=a.get("description"),
            evidence=a.get("evidence"),
            buyer_rut=a.get("buyer_rut"),
            buyer_name=a.get("buyer_name"),
            supplier_rut=a.get("supplier_rut"),
            supplier_name=a.get("supplier_name"),
            region=a.get("region"),
            amount_involved=a.get("amount_involved"),
            status="open",
        )
        db.add(alert)
    db.commit()
    print(f"Saved {len(alerts)} VELO alerts", flush=True)

    db.close()
    print("Done!", flush=True)

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
