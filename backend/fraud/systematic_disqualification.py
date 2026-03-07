"""
Detector: Descalificacion Sistematica (DESC)
Detects buyers who disqualify an abnormally high percentage of bidders,
and specific supplier targeting (same supplier disqualified 3+ times
by the same buyer).

Thresholds:
  - >40% disqualified and >=10 total bids = alta
  - >25% disqualified and >=5 total bids = media
  - Same supplier disqualified 3+ times by same buyer = alta
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

DISQ_RATIO_HIGH = 0.40    # >40% disqualified = alta
DISQ_RATIO_MEDIUM = 0.25  # >25% disqualified = media
MIN_BIDS_HIGH = 10         # Minimum total bids for alta threshold
MIN_BIDS_MEDIUM = 5        # Minimum total bids for media threshold
MIN_TARGETED_DISQ = 3      # Same supplier disqualified N+ times = targeted


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for systematic disqualification patterns.
    Two strategies:
      1. High overall disqualification rate per buyer
      2. Targeted disqualification of specific suppliers
    """
    alerts = []
    seen_buyer_general = set()

    # --- Strategy 1: High disqualification rate by buyer ---
    # Resolve bid supplier OCDS IDs to real Chilean RUTs via procurement_parties
    query = text("""
        SELECT
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            COALESCE(bid_party.rut, b.supplier_rut) AS supplier_rut,
            COALESCE(bid_party.name, b.supplier_name) AS supplier_name,
            b.status AS bid_status,
            b.ocid
        FROM bids b
        JOIN procurements p ON p.ocid = b.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        LEFT JOIN procurement_parties pp_bid ON pp_bid.procurement_ocid = b.ocid AND pp_bid.role = 'tenderer'
        LEFT JOIN parties bid_party ON bid_party.rut = pp_bid.party_rut
            AND bid_party.name = b.supplier_name
        WHERE pp_b.party_rut IS NOT NULL
          AND b.supplier_rut IS NOT NULL
          AND b.status IS NOT NULL
          AND b.status != ''
    """)

    rows = db.execute(query).fetchall()

    if not rows:
        logger.info("DESC detector: no bids with status found")
        return alerts

    # Group by buyer_rut
    buyer_bids = defaultdict(list)
    for row in rows:
        buyer_bids[row.buyer_rut].append(row)

    for buyer_rut, bids in buyer_bids.items():
        total_bids = len(bids)
        disqualified = [b for b in bids if (b.bid_status or "").lower().strip() in (
            "disqualified", "rejected", "invalid", "inadmissible"
        )]
        disq_count = len(disqualified)

        if total_bids < MIN_BIDS_MEDIUM or disq_count == 0:
            continue

        ratio = disq_count / total_bids
        first = bids[0]

        severity = None
        if ratio >= DISQ_RATIO_HIGH and total_bids >= MIN_BIDS_HIGH:
            severity = "alta"
        elif ratio >= DISQ_RATIO_MEDIUM and total_bids >= MIN_BIDS_MEDIUM:
            severity = "media"

        if severity and buyer_rut not in seen_buyer_general:
            seen_buyer_general.add(buyer_rut)

            # Collect sample OCIDs from disqualified bids
            disq_ocids = list({b.ocid for b in disqualified})
            disq_suppliers = list({b.supplier_rut for b in disqualified if b.supplier_rut})

            alerts.append({
                "ocid": disq_ocids[0] if disq_ocids else None,
                "alert_type": "DESC",
                "severity": severity,
                "title": f"Descalificacion sistematica: {first.buyer_name or buyer_rut}",
                "description": (
                    f"El organismo {first.buyer_name or buyer_rut} ha descalificado "
                    f"el {ratio * 100:.1f}% de las ofertas recibidas "
                    f"({disq_count} de {total_bids} ofertas). "
                    f"Un porcentaje tan alto de descalificaciones puede indicar "
                    f"uso de criterios restrictivos para favorecer a un proveedor "
                    f"predeterminado o limitar artificialmente la competencia."
                ),
                "evidence": {
                    "buyer_rut": buyer_rut,
                    "buyer_name": first.buyer_name,
                    "total_bids": total_bids,
                    "disqualified_count": disq_count,
                    "disqualification_rate": round(ratio, 4),
                    "unique_disqualified_suppliers": len(disq_suppliers),
                    "sample_ocids": disq_ocids[:10],
                    "disqualified_supplier_ruts": disq_suppliers[:10],
                },
                "buyer_rut": buyer_rut,
                "buyer_name": first.buyer_name,
                "supplier_rut": None,
                "supplier_name": None,
                "region": first.region,
                "amount_involved": None,
            })

    # --- Strategy 2: Targeted disqualification of specific suppliers ---
    # Group by (buyer_rut, supplier_rut) and count disqualifications
    buyer_supplier_disq = defaultdict(list)
    for row in rows:
        bid_status = (row.bid_status or "").lower().strip()
        if bid_status in ("disqualified", "rejected", "invalid", "inadmissible"):
            key = (row.buyer_rut, row.supplier_rut)
            buyer_supplier_disq[key].append(row)

    seen_targeted = set()

    for (buyer_rut, supplier_rut), disq_bids in buyer_supplier_disq.items():
        if len(disq_bids) < MIN_TARGETED_DISQ:
            continue

        key = (buyer_rut, supplier_rut)
        if key in seen_targeted:
            continue
        seen_targeted.add(key)

        first = disq_bids[0]
        disq_ocids = list({b.ocid for b in disq_bids})

        alerts.append({
            "ocid": disq_ocids[0] if disq_ocids else None,
            "alert_type": "DESC",
            "severity": "alta",
            "title": (
                f"Descalificacion dirigida: {first.supplier_name or supplier_rut} "
                f"por {first.buyer_name or buyer_rut}"
            ),
            "description": (
                f"El proveedor {first.supplier_name or supplier_rut} "
                f"(RUT: {supplier_rut}) ha sido descalificado "
                f"{len(disq_bids)} veces por el organismo "
                f"{first.buyer_name or buyer_rut}. "
                f"La descalificacion repetida del mismo proveedor puede indicar "
                f"un patron de exclusion intencional para eliminar competencia "
                f"legitima y favorecer a otro oferente."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": first.buyer_name,
                "targeted_supplier_rut": supplier_rut,
                "targeted_supplier_name": first.supplier_name,
                "disqualification_count": len(disq_bids),
                "ocids": disq_ocids[:10],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": first.buyer_name,
            "supplier_rut": supplier_rut,
            "supplier_name": first.supplier_name,
            "region": first.region,
            "amount_involved": None,
        })

    logger.info(f"DESC detector: {len(alerts)} alerts generated")
    return alerts
