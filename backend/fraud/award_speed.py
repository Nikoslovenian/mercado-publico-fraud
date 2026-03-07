"""
Detector: Velocidad de Adjudicacion (VELO)
Detects suspiciously fast awards after tender close.

Criteria:
  - Award same day as close (0 days) = alta
  - Award within 1 day of close = media
  - Evaluation took 0 days for complex methods (LP, LQ) with many bidders = alta
  - Excludes trato directo (TD) and L1 (simple purchases)
"""
import logging
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Methods to exclude (no competitive evaluation expected)
EXCLUDED_METHODS = {"TD", "AT", "CO", "AM", "L1"}

# Complex methods where fast evaluation is suspicious
COMPLEX_METHODS = {"LP", "LQ", "LR"}

# Minimum bidders for complex method check
MIN_BIDDERS_COMPLEX = 3


def _parse_date(val):
    """Parse date from string or datetime. Returns datetime or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _extract_method_code(method_details: str) -> str:
    """Extract method code from method_details string."""
    if not method_details:
        return ""
    # Try parentheses pattern: "Licitacion Publica (LP)"
    m = re.search(r'\((\w+)\)\s*$', method_details)
    if m:
        return m.group(1).upper()
    # Fall back to first 2 chars
    return method_details.strip()[:2].upper()


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for suspiciously fast award decisions.
    """
    alerts = []

    # Get procurements with tender_end and award_date
    query = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.method,
            p.method_details,
            p.tender_end,
            p.award_date,
            p.total_amount,
            (SELECT COUNT(DISTINCT pp_t.party_rut)
             FROM procurement_parties pp_t
             WHERE pp_t.procurement_ocid = p.ocid
               AND pp_t.role = 'tenderer'
            ) AS bid_count
        FROM procurements p
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE p.tender_end IS NOT NULL
          AND p.award_date IS NOT NULL
          AND pp_b.party_rut IS NOT NULL
    """)

    rows = db.execute(query).fetchall()

    if not rows:
        logger.info("VELO detector: no procurements with both tender_end and award_date found")
        return alerts

    seen = set()

    for row in rows:
        if row.ocid in seen:
            continue

        method_code = _extract_method_code(row.method_details)

        # Skip excluded methods
        if method_code in EXCLUDED_METHODS:
            continue

        tender_end = _parse_date(row.tender_end)
        award_date = _parse_date(row.award_date)

        if not tender_end or not award_date:
            continue

        # Calculate days between tender close and award
        delta_days = (award_date - tender_end).days

        # Skip if award is before tender end (bad data) or too far in the future
        if delta_days < 0:
            continue

        severity = None
        description_detail = ""

        # Check for same-day award
        if delta_days == 0:
            severity = "alta"
            description_detail = (
                f"La adjudicacion se realizo el MISMO DIA del cierre de ofertas "
                f"({award_date.date()}). Es practicamente imposible evaluar "
                f"correctamente las ofertas en 0 dias, lo que sugiere que el "
                f"resultado estaba predeterminado."
            )
        elif delta_days <= 1:
            severity = "media"
            description_detail = (
                f"La adjudicacion se realizo solo {delta_days} dia(s) despues "
                f"del cierre ({tender_end.date()} -> {award_date.date()}). "
                f"Un periodo de evaluacion tan breve puede ser insuficiente "
                f"para una evaluacion objetiva de las ofertas."
            )

        # Additional check: complex methods with many bidders evaluated in 0 days
        if method_code in COMPLEX_METHODS and delta_days == 0:
            bid_count = row.bid_count or 0
            if bid_count >= MIN_BIDDERS_COMPLEX:
                severity = "alta"
                description_detail += (
                    f" Ademas, se trata de un proceso {method_code} con "
                    f"{bid_count} oferentes, lo que hace aun mas improbable "
                    f"una evaluacion legitima en el mismo dia."
                )

        if not severity:
            continue

        seen.add(row.ocid)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "VELO",
            "severity": severity,
            "title": (
                f"Adjudicacion ultra-rapida ({delta_days} dias): "
                f"{row.title[:60] if row.title else row.ocid}"
            ),
            "description": (
                f"En la licitacion '{row.title or row.ocid}' del organismo "
                f"{row.buyer_name or row.buyer_rut}, la adjudicacion se "
                f"realizo en solo {delta_days} dia(s) desde el cierre de ofertas. "
                f"{description_detail}"
            ),
            "evidence": {
                "ocid": row.ocid,
                "tender_end": str(tender_end),
                "award_date": str(award_date),
                "evaluation_days": delta_days,
                "method_code": method_code,
                "method_details": row.method_details,
                "bid_count": row.bid_count,
                "total_amount": row.total_amount,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": None,
            "supplier_name": None,
            "region": row.region,
            "amount_involved": row.total_amount,
        })

    logger.info(f"VELO detector: {len(alerts)} alerts generated")
    return alerts
