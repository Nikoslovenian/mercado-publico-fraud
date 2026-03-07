"""
Detector: Compras Fraccionadas (FRAC)
Detects when the same buyer repeatedly purchases from the same supplier
in the same UNSPSC category within a rolling 90-day window, with the
sum exceeding the relevant procurement threshold.

Thresholds (UTM 2025 ≈ 67,294 CLP):
  - Trato Directo: < 100 UTM  (~6,729,400 CLP)
  - LE (100-1000 UTM):        (~67,294,000 CLP)
  - LP (> 1000 UTM):          no upper limit
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text


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

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025
THRESHOLD_DIRECT = 100 * UTM      # ~6.7M CLP
THRESHOLD_LE = 1000 * UTM         # ~67.3M CLP
WINDOW_DAYS = 90
MIN_TRANSACTIONS = 2              # Minimum purchases to flag


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for fractioned purchases.
    Uses raw SQL for performance on large datasets.
    """
    alerts = []

    query = text("""
        SELECT
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            i.unspsc_prefix,
            p.ocid,
            p.tender_start,
            a.amount,
            p.method_details,
            p.title
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN items i ON i.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pp_s.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND p.tender_start IS NOT NULL
          AND pp_b.party_rut IS NOT NULL
        ORDER BY pp_b.party_rut, pp_s.party_rut, i.unspsc_prefix, p.tender_start
    """)

    rows = db.execute(query).fetchall()

    # Group by (buyer_rut, supplier_rut, unspsc_prefix)
    from collections import defaultdict
    groups = defaultdict(list)
    for row in rows:
        key = (row.buyer_rut, row.supplier_rut, row.unspsc_prefix or "")
        groups[key].append(row)

    for (buyer_rut, supplier_rut, unspsc_prefix), group_rows in groups.items():
        if len(group_rows) < MIN_TRANSACTIONS:
            continue

        # Sort by date (parse strings to datetime for comparison)
        group_rows = sorted(group_rows, key=lambda r: _parse_date(r.tender_start) or datetime.min)

        # Find the BEST window (highest total) to deduplicate per group
        best_window = None
        best_total = 0
        best_severity = None
        best_threshold = ""

        i = 0
        while i < len(group_rows):
            window = [group_rows[i]]
            base_date = _parse_date(group_rows[i].tender_start)

            for j in range(i + 1, len(group_rows)):
                row_j = group_rows[j]
                row_j_date = _parse_date(row_j.tender_start)
                if row_j_date and base_date:
                    delta = (row_j_date - base_date).days
                    if delta <= WINDOW_DAYS:
                        window.append(row_j)
                    else:
                        break

            if len(window) >= MIN_TRANSACTIONS:
                total = sum(r.amount for r in window if r.amount)
                all_below_direct = all((r.amount or 0) < THRESHOLD_DIRECT for r in window)
                all_below_le = all((r.amount or 0) < THRESHOLD_LE for r in window)
                severity = None
                threshold_name = ""
                if all_below_direct and total >= THRESHOLD_DIRECT:
                    severity = "alta"
                    threshold_name = "100 UTM (Trato Directo)"
                elif all_below_le and total >= THRESHOLD_LE:
                    severity = "alta" if total >= THRESHOLD_LE * 2 else "media"
                    threshold_name = "1000 UTM (Licitacion Publica)"
                if severity and total > best_total:
                    best_window = window
                    best_total = total
                    best_severity = severity
                    best_threshold = threshold_name
            # Advance past consumed window to avoid overlap
            i += max(1, len(window))

        if not best_window:
            continue

        window = best_window
        total = best_total
        severity = best_severity
        threshold_name = best_threshold
        ocids = list({r.ocid for r in window})

        if severity:
            first_row = window[0]
            alerts.append({
                "ocid": ocids[0],
                "alert_type": "FRAC",
                "severity": severity,
                "title": f"Compra fraccionada: {first_row.supplier_name or supplier_rut}",
                "description": (
                    f"El organismo {first_row.buyer_name or buyer_rut} realizo {len(window)} "
                    f"compras al proveedor {first_row.supplier_name or supplier_rut} "
                    f"en categoria UNSPSC {unspsc_prefix} dentro de {WINDOW_DAYS} dias, "
                    f"sumando ${total:,.0f} CLP. Individualmente cada compra es menor al "
                    f"umbral de {threshold_name}, pero la suma total supera dicho umbral. "
                    f"Esto sugiere posible fraccionamiento para evitar licitacion obligatoria."
                ),
                "evidence": {
                    "buyer_rut": buyer_rut,
                    "supplier_rut": supplier_rut,
                    "unspsc_prefix": unspsc_prefix,
                    "window_days": WINDOW_DAYS,
                    "transaction_count": len(window),
                    "total_amount_clp": total,
                    "threshold_evaded": threshold_name,
                    "individual_amounts": [r.amount for r in window[:10]],
                    "ocids": ocids[:10],
                    "dates": [str(r.tender_start) for r in window[:10]],
                },
                "buyer_rut": buyer_rut,
                "buyer_name": first_row.buyer_name,
                "supplier_rut": supplier_rut,
                "supplier_name": first_row.supplier_name,
                "region": first_row.region,
                "amount_involved": total,
            })

    logger.info(f"FRAC detector: {len(alerts)} alerts generated")
    return alerts
