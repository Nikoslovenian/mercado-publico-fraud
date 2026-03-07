"""
Detector: Proximidad a Umbrales Legales (UMBR)
Detects procurement amounts suspiciously close to legal thresholds,
suggesting intentional structuring to avoid stricter procurement rules.

Thresholds (UTM 2025 = 67,294 CLP):
  - 100 UTM  = 6,729,400 CLP   (Trato Directo limit)
  - 1000 UTM = 67,294,000 CLP  (LE limit)
  - 2000 UTM = 134,588,000 CLP (LQ limit)

Severity:
  - 95-100% of threshold (exclusive) = alta
  - 90-95% of threshold = media
  - Exact threshold boundary amounts are excluded
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025

THRESHOLDS = [
    {
        "name": "Trato Directo (100 UTM)",
        "amount": 100 * UTM,       # 6,729,400 CLP
        "description": "limite para trato directo",
    },
    {
        "name": "Licitacion Publica LE (1000 UTM)",
        "amount": 1000 * UTM,      # 67,294,000 CLP
        "description": "limite para licitacion electronica",
    },
    {
        "name": "Licitacion Publica LQ (2000 UTM)",
        "amount": 2000 * UTM,      # 134,588,000 CLP
        "description": "limite para licitacion publica mayor",
    },
]

PROXIMITY_ALTA = 0.95   # 95% of threshold = alta
PROXIMITY_MEDIA = 0.90  # 90% of threshold = media


def _check_threshold(amount: float) -> tuple:
    """
    Check if an amount is suspiciously close to any threshold.
    Returns (severity, threshold_info) or (None, None).
    """
    if amount is None or amount <= 0:
        return None, None

    for threshold in THRESHOLDS:
        t_amount = threshold["amount"]

        # Skip if amount is exactly at or above the threshold
        if amount >= t_amount:
            continue

        ratio = amount / t_amount

        # Must be below but close to the threshold (not exactly at boundary)
        if ratio >= PROXIMITY_ALTA:
            # 95-100% of threshold (exclusive of 100%)
            return "alta", threshold
        elif ratio >= PROXIMITY_MEDIA:
            # 90-95% of threshold
            return "media", threshold

    return None, None


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for amounts suspiciously close to legal thresholds.
    Checks both procurement total_amount and individual award amounts.
    """
    alerts = []
    seen = set()  # Deduplicate by (ocid, threshold_name, source)

    # --- Check procurement total amounts ---
    query_proc = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.total_amount,
            p.method,
            p.method_details
        FROM procurements p
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE p.total_amount IS NOT NULL
          AND p.total_amount > 0
          AND pp_b.party_rut IS NOT NULL
    """)

    proc_rows = db.execute(query_proc).fetchall()

    for row in proc_rows:
        severity, threshold_info = _check_threshold(row.total_amount)
        if not severity:
            continue

        key = (row.ocid, threshold_info["name"], "procurement")
        if key in seen:
            continue
        seen.add(key)

        ratio_pct = (row.total_amount / threshold_info["amount"]) * 100

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "UMBR",
            "severity": severity,
            "title": (
                f"Monto cercano al umbral de {threshold_info['name']}: "
                f"{row.title[:60] if row.title else row.ocid}"
            ),
            "description": (
                f"La licitacion '{row.title or row.ocid}' del organismo "
                f"{row.buyer_name or row.buyer_rut} tiene un monto total de "
                f"${row.total_amount:,.0f} CLP, equivalente al {ratio_pct:.1f}% "
                f"del umbral de {threshold_info['name']} "
                f"(${threshold_info['amount']:,.0f} CLP). "
                f"Un monto tan cercano al {threshold_info['description']} "
                f"puede indicar que el valor fue deliberadamente fijado "
                f"justo por debajo del umbral para evitar un proceso "
                f"de contratacion mas riguroso."
            ),
            "evidence": {
                "ocid": row.ocid,
                "amount": row.total_amount,
                "threshold_name": threshold_info["name"],
                "threshold_amount": threshold_info["amount"],
                "proximity_pct": round(ratio_pct, 2),
                "difference_clp": threshold_info["amount"] - row.total_amount,
                "source": "procurement_total",
                "method": row.method,
                "method_details": row.method_details,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": None,
            "supplier_name": None,
            "region": row.region,
            "amount_involved": row.total_amount,
        })

    # --- Check individual award amounts ---
    query_awards = text("""
        SELECT
            a.ocid,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            a.amount,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE a.amount IS NOT NULL
          AND a.amount > 0
          AND pp_b.party_rut IS NOT NULL
    """)

    award_rows = db.execute(query_awards).fetchall()

    for row in award_rows:
        severity, threshold_info = _check_threshold(row.amount)
        if not severity:
            continue

        key = (row.ocid, threshold_info["name"], "award")
        if key in seen:
            continue
        seen.add(key)

        ratio_pct = (row.amount / threshold_info["amount"]) * 100

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "UMBR",
            "severity": severity,
            "title": (
                f"Adjudicacion cercana al umbral de {threshold_info['name']}: "
                f"{row.supplier_name or row.supplier_rut}"
            ),
            "description": (
                f"La adjudicacion al proveedor {row.supplier_name or row.supplier_rut} "
                f"(RUT: {row.supplier_rut}) en la licitacion "
                f"'{row.title or row.ocid}' es de ${row.amount:,.0f} CLP, "
                f"equivalente al {ratio_pct:.1f}% del umbral de "
                f"{threshold_info['name']} (${threshold_info['amount']:,.0f} CLP). "
                f"Monto sospechosamente cercano al {threshold_info['description']}."
            ),
            "evidence": {
                "ocid": row.ocid,
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "amount": row.amount,
                "threshold_name": threshold_info["name"],
                "threshold_amount": threshold_info["amount"],
                "proximity_pct": round(ratio_pct, 2),
                "difference_clp": threshold_info["amount"] - row.amount,
                "source": "award",
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    logger.info(f"UMBR detector: {len(alerts)} alerts generated")
    return alerts
