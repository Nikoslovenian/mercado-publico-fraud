"""
Detector: Division Artificial de Contratos (DIVI)
Detects artificial splitting of contracts to stay below legal thresholds.

Groups awards by (buyer_rut, supplier_rut) within 30-day sliding windows.
If individual awards are each below a threshold but the combined total
exceeds it, this suggests deliberate splitting.

Severity:
  - Combined > 100 UTM but each individual < 100 UTM = alta
  - Combined > 50 UTM but each individual < 50 UTM = media
  - Minimum 2 transactions in window
"""
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025
THRESHOLD_HIGH = 100 * UTM     # 6,729,400 CLP (trato directo limit)
THRESHOLD_MEDIUM = 50 * UTM   # 3,364,700 CLP
WINDOW_DAYS = 30
MIN_TRANSACTIONS = 2


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


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for artificial contract splitting.
    """
    alerts = []

    # Get all awards with dates, grouped by buyer and supplier
    query = text("""
        SELECT
            a.ocid,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            a.amount,
            a.date AS award_date,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.tender_start
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pp_s.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND pp_b.party_rut IS NOT NULL
          AND (a.date IS NOT NULL OR p.tender_start IS NOT NULL)
        ORDER BY pp_b.party_rut, pp_s.party_rut, COALESCE(a.date, p.tender_start)
    """)

    rows = db.execute(query).fetchall()

    if not rows:
        logger.info("DIVI detector: no qualifying awards found")
        return alerts

    # Group by (buyer_rut, supplier_rut)
    groups = defaultdict(list)
    for row in rows:
        # Use award date if available, otherwise tender_start
        dt = _parse_date(row.award_date) or _parse_date(row.tender_start)
        if not dt:
            continue
        key = (row.buyer_rut, row.supplier_rut)
        groups[key].append({
            "ocid": row.ocid,
            "amount": row.amount,
            "date": dt,
            "supplier_name": row.supplier_name,
            "buyer_name": row.buyer_name,
            "region": row.region,
            "title": row.title,
        })

    seen_groups = set()

    for (buyer_rut, supplier_rut), award_list in groups.items():
        if len(award_list) < MIN_TRANSACTIONS:
            continue

        # Sort by date
        award_list.sort(key=lambda x: x["date"])

        # Sliding window: find best window per group
        best_window = None
        best_total = 0
        best_severity = None
        best_threshold_name = ""

        i = 0
        while i < len(award_list):
            window_start = award_list[i]["date"]
            window_end = window_start + timedelta(days=WINDOW_DAYS)

            # Collect all awards in this window
            window = []
            for j in range(i, len(award_list)):
                if award_list[j]["date"] <= window_end:
                    window.append(award_list[j])
                else:
                    break

            if len(window) >= MIN_TRANSACTIONS:
                total = sum(a["amount"] for a in window)

                # Check alta: combined > 100 UTM, each < 100 UTM
                all_below_high = all(a["amount"] < THRESHOLD_HIGH for a in window)
                # Check media: combined > 50 UTM, each < 50 UTM
                all_below_medium = all(a["amount"] < THRESHOLD_MEDIUM for a in window)

                severity = None
                threshold_name = ""

                if all_below_high and total >= THRESHOLD_HIGH:
                    severity = "alta"
                    threshold_name = "100 UTM (Trato Directo)"
                elif all_below_medium and total >= THRESHOLD_MEDIUM:
                    severity = "media"
                    threshold_name = "50 UTM"

                if severity and total > best_total:
                    best_window = window
                    best_total = total
                    best_severity = severity
                    best_threshold_name = threshold_name

            i += 1

        if not best_window or not best_severity:
            continue

        group_key = (buyer_rut, supplier_rut)
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)

        window = best_window
        total = best_total
        severity = best_severity
        threshold_name = best_threshold_name
        first = window[0]
        ocids = list({a["ocid"] for a in window})

        date_range_start = min(a["date"] for a in window)
        date_range_end = max(a["date"] for a in window)
        span_days = (date_range_end - date_range_start).days

        alerts.append({
            "ocid": ocids[0],
            "alert_type": "DIVI",
            "severity": severity,
            "title": (
                f"Division artificial de contratos: "
                f"{first['supplier_name'] or supplier_rut}"
            ),
            "description": (
                f"El organismo {first['buyer_name'] or buyer_rut} realizo "
                f"{len(window)} adjudicaciones al proveedor "
                f"{first['supplier_name'] or supplier_rut} "
                f"(RUT: {supplier_rut}) en un periodo de {span_days} dias "
                f"(del {date_range_start.date()} al {date_range_end.date()}). "
                f"Cada adjudicacion individual es menor al umbral de "
                f"{threshold_name}, pero el monto combinado es de "
                f"${total:,.0f} CLP, superando dicho umbral. "
                f"Este patron sugiere una posible division artificial de "
                f"contratos para evitar el proceso de licitacion requerido "
                f"por ley sobre el umbral."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": first["buyer_name"],
                "supplier_rut": supplier_rut,
                "supplier_name": first["supplier_name"],
                "transaction_count": len(window),
                "window_days": span_days,
                "combined_amount": total,
                "threshold_evaded": threshold_name,
                "individual_amounts": [a["amount"] for a in window[:15]],
                "dates": [str(a["date"].date()) for a in window[:15]],
                "ocids": ocids[:15],
                "titles": [a["title"] for a in window[:15] if a["title"]],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": first["buyer_name"],
            "supplier_rut": supplier_rut,
            "supplier_name": first["supplier_name"],
            "region": first["region"],
            "amount_involved": total,
        })

    logger.info(f"DIVI detector: {len(alerts)} alerts generated")
    return alerts
