#!/usr/bin/env python3
"""
Fraud Engine Runner: runs all fraud detectors and saves alerts to the database.
Usage: python scripts/run_fraud_engine.py [--clear]
"""
import sys
import os
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import init_db, SessionLocal
from fraud.engine import run_all_detectors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fraud_engine.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run fraud detection on loaded procurement data")
    parser.add_argument("--clear", action="store_true", help="Clear existing alerts before running")
    args = parser.parse_args()

    logger.info("Initializing database...")
    init_db()

    db = SessionLocal()
    try:
        logger.info("Starting fraud detection engine...")
        stats = run_all_detectors(db, clear_existing=args.clear)

        logger.info("=" * 60)
        logger.info("FRAUD DETECTION COMPLETE")
        logger.info(f"  Total alerts generated: {stats['total_alerts']:,}")
        logger.info(f"  By type:")
        for alert_type, count in stats.get("by_type", {}).items():
            logger.info(f"    {alert_type}: {count:,}")
        logger.info(f"  By severity:")
        for sev, count in stats.get("by_severity", {}).items():
            logger.info(f"    {sev}: {count:,}")
        logger.info(f"  Started:  {stats.get('started_at')}")
        logger.info(f"  Finished: {stats.get('finished_at')}")
        logger.info("=" * 60)
        
        # 3. Disparar notificaciones por correo de fraude critico (Integracion SOC)
        try:
            from notifications.email import send_critical_alerts_email
            send_critical_alerts_email(stats)
        except Exception as email_err:
            logger.error(f"Error al despachar el correo: {email_err}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
