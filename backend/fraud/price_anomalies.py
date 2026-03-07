"""
Detector: Precios Anómalos (PREC)
Compares unit prices for the same UNSPSC code + unit combination
using statistical outlier detection (z-score / IQR).
"""
import logging
import math
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_SAMPLES = 5     # Need at least 5 data points to compute meaningful stats
Z_SCORE_MEDIUM = 2.0   # Alert if price > mean + 2σ
Z_SCORE_HIGH = 3.0     # High severity if > mean + 3σ
MIN_UNIT_PRICE = 10    # Skip items with prices < $10 CLP (likely free/sample)


def _mean_std(values: list) -> tuple:
    n = len(values)
    if n < 2:
        return None, None
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(variance)
    return mean, std


def detect(db: Session) -> list[dict]:
    alerts = []

    query = text("""
        SELECT
            i.id AS item_id,
            i.ocid,
            i.unspsc_code,
            i.unspsc_prefix,
            i.description,
            i.unit,
            i.unit_price,
            i.quantity,
            i.total_price,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.tender_start
        FROM items i
        JOIN procurements p ON p.ocid = i.ocid
        LEFT JOIN awards a ON a.id = i.award_id
        LEFT JOIN procurement_parties pp_s ON pp_s.procurement_ocid = i.ocid AND pp_s.role = 'supplier'
        LEFT JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE i.unit_price IS NOT NULL
          AND i.unit_price >= :min_price
          AND i.unspsc_prefix != ''
    """)

    rows = db.execute(query, {"min_price": MIN_UNIT_PRICE}).fetchall()

    # Group by (unspsc_prefix, unit) — normalized unit
    groups = defaultdict(list)
    for row in rows:
        unit_norm = (row.unit or "").lower().strip()
        key = (row.unspsc_prefix, unit_norm)
        groups[key].append(row)

    for (unspsc_prefix, unit), group_rows in groups.items():
        if len(group_rows) < MIN_SAMPLES:
            continue

        prices = [r.unit_price for r in group_rows if r.unit_price]
        mean, std = _mean_std(prices)

        if mean is None or std is None or std == 0:
            continue

        for row in group_rows:
            if not row.unit_price:
                continue
            z = (row.unit_price - mean) / std

            if z >= Z_SCORE_HIGH:
                severity = "alta"
            elif z >= Z_SCORE_MEDIUM:
                severity = "media"
            else:
                continue

            alerts.append({
                "ocid": row.ocid,
                "alert_type": "PREC",
                "severity": severity,
                "title": f"Precio anómalo detectado: {row.description[:60] if row.description else unspsc_prefix}",
                "description": (
                    f"El ítem '{row.description or unspsc_prefix}' (UNSPSC: {row.unspsc_code}) "
                    f"adjudicado al proveedor {row.supplier_name or row.supplier_rut} "
                    f"tiene un precio unitario de ${row.unit_price:,.0f} CLP/{row.unit}, "
                    f"que es {z:.1f} desviaciones estándar sobre la media "
                    f"(media: ${mean:,.0f}, σ: ${std:,.0f}). "
                    f"Este precio se compara contra {len(group_rows)} registros similares "
                    f"en el mismo código de producto."
                ),
                "evidence": {
                    "item_id": row.item_id,
                    "ocid": row.ocid,
                    "unspsc_code": row.unspsc_code,
                    "unspsc_prefix": unspsc_prefix,
                    "description": row.description,
                    "unit": row.unit,
                    "unit_price": row.unit_price,
                    "quantity": row.quantity,
                    "total_price": row.total_price,
                    "z_score": round(z, 2),
                    "mean_price": round(mean, 2),
                    "std_price": round(std, 2),
                    "sample_count": len(group_rows),
                    "percentile": round(sum(1 for p in prices if p <= row.unit_price) / len(prices) * 100, 1),
                },
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "region": row.region,
                "amount_involved": row.total_price,
            })

    logger.info(f"PREC detector: {len(alerts)} alerts generated")
    return alerts
