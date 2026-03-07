"""
Detector: Adjudicacion a Oferente No Mas Barato (ADJU)
Detects when the winning supplier is NOT the lowest valid bidder.

If the winner's amount exceeds the lowest valid bid by >20% = alta.
If >5% = media.
Only applies to open/selective methods with >=2 valid bids.
Minimum bid amount must be > 0.
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MARGIN_HIGH = 0.20    # >20% more expensive than lowest bid = alta
MARGIN_MEDIUM = 0.05  # >5% more expensive = media


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for awards not going to the lowest bidder.
    Compares award amounts against all valid bids for the same procurement.
    """
    alerts = []

    # Get all procurements with their bids and awards
    # Only open/selective methods (competitive processes)
    # Resolve bid supplier OCDS IDs to real Chilean RUTs via procurement_parties
    query = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.method,
            p.method_details,
            p.total_amount,
            pp_w.party_rut AS winner_rut,
            winner_party.name AS winner_name,
            a.supplier_rut AS winner_ocds_id,
            a.amount AS award_amount,
            b.supplier_rut AS bid_ocds_id,
            COALESCE(bid_party.rut, b.supplier_rut) AS bid_supplier_rut,
            COALESCE(bid_party.name, b.supplier_name) AS bid_supplier_name,
            b.amount AS bid_amount,
            b.status AS bid_status
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN bids b ON b.ocid = p.ocid
        JOIN procurement_parties pp_w ON pp_w.procurement_ocid = a.ocid AND pp_w.role = 'supplier'
        JOIN parties winner_party ON winner_party.rut = pp_w.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        LEFT JOIN procurement_parties pp_bid ON pp_bid.procurement_ocid = b.ocid AND pp_bid.role = 'tenderer'
        LEFT JOIN parties bid_party ON bid_party.rut = pp_bid.party_rut
            AND bid_party.name = b.supplier_name
        WHERE p.method IN ('open', 'selective')
          AND pp_w.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND b.amount IS NOT NULL
          AND b.amount > 0
        ORDER BY p.ocid, b.amount ASC
    """)

    rows = db.execute(query).fetchall()

    if not rows:
        logger.info("ADJU detector: no qualifying procurements found")
        return alerts

    # Group by ocid
    by_ocid = defaultdict(list)
    for row in rows:
        by_ocid[row.ocid].append(row)

    seen_ocids = set()

    for ocid, proc_rows in by_ocid.items():
        if ocid in seen_ocids:
            continue

        first = proc_rows[0]
        winner_rut = first.winner_rut  # Real RUT for output
        winner_ocds_id = first.winner_ocds_id  # OCDS ID for comparison with bids
        award_amount = first.award_amount

        if not winner_rut or not award_amount:
            continue

        # Collect valid bids (status is valid, submitted, or empty/null = accepted)
        valid_bids = []
        for row in proc_rows:
            bid_status = (row.bid_status or "").lower().strip()
            if bid_status in ("valid", "submitted", "pending", ""):
                # Deduplicate by bid OCDS ID (same supplier may appear multiple times from joins)
                if not any(vb["bid_ocds_id"] == row.bid_ocds_id for vb in valid_bids):
                    valid_bids.append({
                        "bid_ocds_id": row.bid_ocds_id,
                        "supplier_rut": row.bid_supplier_rut,
                        "supplier_name": row.bid_supplier_name,
                        "amount": row.bid_amount,
                    })

        # Need at least 2 valid bids for comparison
        if len(valid_bids) < 2:
            continue

        # Find the lowest valid bid
        valid_bids.sort(key=lambda b: b["amount"])
        lowest_bid = valid_bids[0]
        lowest_amount = lowest_bid["amount"]

        if lowest_amount <= 0:
            continue

        # Check if the winner is NOT the lowest bidder
        # Compare using OCDS IDs (both from original bids/awards tables)
        if winner_ocds_id == lowest_bid["bid_ocds_id"]:
            continue  # Winner IS the lowest bidder, no alert

        # Calculate how much more expensive the award is vs the lowest bid
        excess_ratio = (award_amount - lowest_amount) / lowest_amount

        if excess_ratio <= MARGIN_MEDIUM:
            continue  # Within acceptable range

        seen_ocids.add(ocid)

        if excess_ratio > MARGIN_HIGH:
            severity = "alta"
        else:
            severity = "media"

        excess_pct = excess_ratio * 100
        excess_amount = award_amount - lowest_amount

        alerts.append({
            "ocid": ocid,
            "alert_type": "ADJU",
            "severity": severity,
            "title": f"Adjudicacion a oferente mas caro: {first.title[:80] if first.title else ocid}",
            "description": (
                f"En la licitacion '{first.title or ocid}', el contrato fue adjudicado a "
                f"{first.winner_name or winner_rut} por ${award_amount:,.0f} CLP, siendo "
                f"un {excess_pct:.1f}% mas caro que la oferta mas baja de "
                f"{lowest_bid['supplier_name'] or lowest_bid['supplier_rut']} "
                f"(${lowest_amount:,.0f} CLP). Diferencia: ${excess_amount:,.0f} CLP. "
                f"Hubo {len(valid_bids)} ofertas validas. "
                f"La adjudicacion a un oferente significativamente mas caro puede "
                f"indicar favoritismo o criterios de evaluacion manipulados."
            ),
            "evidence": {
                "ocid": ocid,
                "winner_rut": winner_rut,
                "winner_name": first.winner_name,
                "award_amount": award_amount,
                "lowest_bid_rut": lowest_bid["supplier_rut"],
                "lowest_bid_name": lowest_bid["supplier_name"],
                "lowest_bid_amount": lowest_amount,
                "excess_pct": round(excess_pct, 2),
                "excess_amount": excess_amount,
                "total_valid_bids": len(valid_bids),
                "all_bids": [
                    {
                        "supplier_rut": b["supplier_rut"],
                        "supplier_name": b["supplier_name"],
                        "amount": b["amount"],
                    }
                    for b in valid_bids[:10]
                ],
                "method": first.method,
                "method_details": first.method_details,
            },
            "buyer_rut": first.buyer_rut,
            "buyer_name": first.buyer_name,
            "supplier_rut": winner_rut,
            "supplier_name": first.winner_name,
            "region": first.region,
            "amount_involved": award_amount,
        })

    logger.info(f"ADJU detector: {len(alerts)} alerts generated")
    return alerts
