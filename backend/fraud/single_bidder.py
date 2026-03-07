"""
Detector: Oferente Unico Recurrente (UNIC)
Detecta licitaciones que sistematicamente reciben un solo oferente,
lo cual puede indicar:
  - Bases dirigidas (especificaciones a medida para un proveedor)
  - Falta de difusion real de la licitacion
  - Acuerdo previo para desalentar competencia

Criterios:
  - Organismo con > 60% de licitaciones con oferente unico → alta
  - Organismo con > 40% de licitaciones con oferente unico → media
  - Combinacion buyer+supplier donde el mismo proveedor es unico oferente 3+ veces → alta
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

RATIO_HIGH = 0.60         # > 60% single-bidder tenders
RATIO_MEDIUM = 0.40       # > 40% single-bidder tenders
MIN_TENDERS = 5           # Minimum competitive tenders to analyze
MIN_REPEAT_SINGLE = 3     # Minimum times same supplier is sole bidder


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for recurring single-bidder tenders.
    """
    alerts = []

    # Count bids per tender (only competitive methods, exclude trato directo)
    # Use procurement_parties for real buyer RUT; for bidder identification,
    # use procurement_parties tenderer role to get real RUTs
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
            COUNT(DISTINCT pp_t.party_rut) AS bidder_count,
            GROUP_CONCAT(DISTINCT pp_t.party_rut) AS bidder_ruts,
            GROUP_CONCAT(DISTINCT t_party.name) AS bidder_names
        FROM procurements p
        JOIN bids b ON b.ocid = p.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        JOIN procurement_parties pp_t ON pp_t.procurement_ocid = p.ocid AND pp_t.role = 'tenderer'
        JOIN parties t_party ON t_party.rut = pp_t.party_rut
        WHERE p.method IN ('open', 'selective')
          AND b.status IN ('valid', 'submitted', '')
          AND b.supplier_rut IS NOT NULL
          AND pp_b.party_rut IS NOT NULL
        GROUP BY p.ocid, pp_b.party_rut, buyer_party.name, p.region, p.title,
                 p.method, p.method_details, p.total_amount
    """)

    rows = db.execute(query).fetchall()

    # --- Strategy 1: Buyer-level single-bidder ratio ---
    buyer_stats = defaultdict(lambda: {
        "total": 0, "single": 0, "name": "", "region": "",
        "single_ocids": [], "single_amounts": []
    })

    # --- Strategy 2: Same buyer+supplier single bidder ---
    buyer_supplier_singles = defaultdict(list)

    for row in rows:
        buyer_rut = row.buyer_rut
        stats = buyer_stats[buyer_rut]
        stats["name"] = row.buyer_name or ""
        stats["region"] = row.region or ""
        stats["total"] += 1

        if row.bidder_count == 1:
            stats["single"] += 1
            stats["single_ocids"].append(row.ocid)
            stats["single_amounts"].append(row.total_amount or 0)

            # Track buyer+supplier combination
            sole_bidder_rut = (row.bidder_ruts or "").split(",")[0]
            sole_bidder_name = (row.bidder_names or "").split(",")[0]
            if sole_bidder_rut:
                key = (buyer_rut, sole_bidder_rut)
                buyer_supplier_singles[key].append({
                    "ocid": row.ocid,
                    "title": row.title,
                    "amount": row.total_amount,
                    "method": row.method_details,
                    "buyer_name": row.buyer_name,
                    "region": row.region,
                    "supplier_name": sole_bidder_name,
                })

    # Generate buyer-level alerts
    for buyer_rut, stats in buyer_stats.items():
        if stats["total"] < MIN_TENDERS:
            continue

        ratio = stats["single"] / stats["total"]

        if ratio >= RATIO_HIGH:
            severity = "alta"
        elif ratio >= RATIO_MEDIUM:
            severity = "media"
        else:
            continue

        total_single_amount = sum(stats["single_amounts"])
        sample_ocid = stats["single_ocids"][0] if stats["single_ocids"] else None

        alerts.append({
            "ocid": sample_ocid,
            "alert_type": "UNIC",
            "severity": severity,
            "title": f"Oferente unico recurrente: {stats['name'] or buyer_rut}",
            "description": (
                f"El organismo {stats['name'] or buyer_rut} recibio un solo "
                f"oferente en {stats['single']} de {stats['total']} licitaciones "
                f"competitivas ({ratio * 100:.1f}%). "
                f"Monto total en licitaciones con oferente unico: "
                f"${total_single_amount:,.0f} CLP. "
                f"Un alto porcentaje de licitaciones sin competencia real puede "
                f"indicar bases dirigidas, falta de publicidad efectiva, o "
                f"acuerdos previos para inhibir la participacion."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": stats["name"],
                "single_bidder_count": stats["single"],
                "total_competitive_tenders": stats["total"],
                "single_bidder_ratio": round(ratio, 4),
                "total_single_amount_clp": total_single_amount,
                "sample_ocids": stats["single_ocids"][:10],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": stats["name"],
            "supplier_rut": None,
            "supplier_name": None,
            "region": stats["region"],
            "amount_involved": total_single_amount,
        })

    # Generate buyer+supplier pair alerts
    for (buyer_rut, supplier_rut), occurrences in buyer_supplier_singles.items():
        if len(occurrences) < MIN_REPEAT_SINGLE:
            continue

        first = occurrences[0]
        total_amount = sum(o["amount"] or 0 for o in occurrences)

        alerts.append({
            "ocid": first["ocid"],
            "alert_type": "UNIC",
            "severity": "alta",
            "title": (
                f"Proveedor unico reiterado: {first['supplier_name'] or supplier_rut} "
                f"en {first['buyer_name'] or buyer_rut}"
            ),
            "description": (
                f"El proveedor {first['supplier_name'] or supplier_rut} "
                f"(RUT: {supplier_rut}) fue el UNICO oferente en "
                f"{len(occurrences)} licitaciones del organismo "
                f"{first['buyer_name'] or buyer_rut}. "
                f"Monto total: ${total_amount:,.0f} CLP. "
                f"La ausencia sistematica de otros oferentes cuando este "
                f"proveedor participa sugiere posibles bases dirigidas o "
                f"conocimiento previo que inhibe la competencia."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": first["buyer_name"],
                "supplier_rut": supplier_rut,
                "supplier_name": first["supplier_name"],
                "occurrence_count": len(occurrences),
                "total_amount_clp": total_amount,
                "occurrences": [
                    {
                        "ocid": o["ocid"],
                        "title": o["title"],
                        "amount": o["amount"],
                        "method": o["method"],
                    }
                    for o in occurrences[:15]
                ],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": first["buyer_name"],
            "supplier_rut": supplier_rut,
            "supplier_name": first["supplier_name"],
            "region": first["region"],
            "amount_involved": total_amount,
        })

    logger.info(f"UNIC detector: {len(alerts)} alerts generated")
    return alerts
