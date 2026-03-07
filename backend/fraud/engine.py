"""
Fraud Detection Engine: orchestrates all detectors and saves alerts to DB.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import Alert, SessionLocal  # type: ignore

from fraud import (  # type: ignore
    fractioned_purchases,
    supplier_concentration,
    bid_rigging,
    anomalous_timelines,
    related_suppliers,
    price_anomalies,
    direct_purchase_excess,
    new_suppliers,
    conflict_of_interest,
    single_bidder,
    temporal_patterns,
    non_lowest_bidder,
    systematic_disqualification,
    geographic_anomaly,
    threshold_proximity,
    award_speed,
    lobby_correlation,
    surname_matching,
    contract_splitting,
    shell_company_detector,
)

logger = logging.getLogger(__name__)

DETECTORS = [
    ("FRAC", fractioned_purchases),
    ("CONC", supplier_concentration),
    ("COLU", bid_rigging),
    ("PLAZ", anomalous_timelines),
    ("RELA", related_suppliers),
    ("PREC", price_anomalies),
    ("TRAT", direct_purchase_excess),
    ("NUEV", new_suppliers),
    ("CONF", conflict_of_interest),
    ("UNIC", single_bidder),
    ("TEMP", temporal_patterns),
    ("ADJU", non_lowest_bidder),
    ("DESC", systematic_disqualification),
    ("GEOG", geographic_anomaly),
    ("UMBR", threshold_proximity),
    ("VELO", award_speed),
    ("LOBB", lobby_correlation),
    ("PARE", surname_matching),
    ("DIVI", contract_splitting),
    ("FANT", shell_company_detector),
]


def run_all_detectors(db: Session, clear_existing: bool = False) -> dict:
    """
    Run all fraud detectors and save results to the alerts table.
    Returns summary statistics.
    """
    if clear_existing:
        logger.info("Clearing existing alerts...")
        db.query(Alert).delete()
        db.commit()

    stats = {
        "total_alerts": 0,
        "by_type": {},
        "by_severity": {"alta": 0, "media": 0, "baja": 0},
        "started_at": datetime.utcnow().isoformat(),
    }

    for detector_name, detector_module in DETECTORS:
        logger.info(f"Running detector: {detector_name}...")
        try:
            alerts = detector_module.detect(db)
            saved = 0
            for alert_data in alerts:
                alert = Alert(
                    ocid=alert_data.get("ocid"),
                    alert_type=alert_data.get("alert_type"),
                    severity=alert_data.get("severity"),
                    title=alert_data.get("title"),
                    description=alert_data.get("description"),
                    evidence=alert_data.get("evidence"),
                    buyer_rut=alert_data.get("buyer_rut"),
                    buyer_name=alert_data.get("buyer_name"),
                    supplier_rut=alert_data.get("supplier_rut"),
                    supplier_name=alert_data.get("supplier_name"),
                    region=alert_data.get("region"),
                    amount_involved=alert_data.get("amount_involved"),
                    created_at=datetime.utcnow(),
                    status="open",
                )
                db.add(alert)
                saved += 1

                sev = alert_data.get("severity", "baja")
                stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1  # type: ignore

            db.commit()
            stats["by_type"][detector_name] = saved  # type: ignore
            stats["total_alerts"] = int(stats["total_alerts"]) + saved  # type: ignore
            logger.info(f"  → {saved} alerts saved for {detector_name}")

        except Exception as e:
            logger.error(f"Detector {detector_name} failed: {e}", exc_info=True)
            db.rollback()
            stats["by_type"][detector_name] = 0  # type: ignore

    stats["finished_at"] = datetime.utcnow().isoformat()
    logger.info(f"Fraud detection complete. Total alerts: {stats['total_alerts']}")
    return stats
