"""
Detector: Trato Directo Excesivo (TRAT) y Licitaciones Desiertas + Trato Directo (DTDR)
"""
import logging
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text


def _parse_date(val):
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

DIRECT_RATIO_MEDIUM = 0.30   # > 30% trato directo → alert
DIRECT_RATIO_HIGH = 0.50     # > 50% → high severity
MIN_TOTAL_CONTRACTS = 5      # Min contracts to be relevant
DESERT_WINDOW_DAYS = 90      # Days after a desierta to look for related trato directo


def detect(db: Session) -> list[dict]:
    alerts = []

    # --- TRAT: Excessive direct purchases by buyer ---
    query = text("""
        SELECT
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.method,
            p.method_details,
            COUNT(p.ocid) AS contract_count,
            SUM(p.total_amount) AS total_amount
        FROM procurements p
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pp_b.party_rut IS NOT NULL
          AND p.status NOT IN ('cancelled', 'unsuccessful')
        GROUP BY pp_b.party_rut, buyer_party.name, p.region, p.method, p.method_details
    """)

    rows = db.execute(query).fetchall()

    buyer_stats = defaultdict(lambda: {"total": 0, "direct": 0, "direct_amount": 0, "total_amount": 0, "name": "", "region": ""})

    for row in rows:
        buyer_rut = row.buyer_rut
        buyer_stats[buyer_rut]["name"] = row.buyer_name or ""
        buyer_stats[buyer_rut]["region"] = row.region or ""
        buyer_stats[buyer_rut]["total"] += row.contract_count
        buyer_stats[buyer_rut]["total_amount"] += row.total_amount or 0
        method = (row.method_details or "").upper()
        if row.method == "limited" or "TD" in method or "AT" in method or method.startswith("AT"):
            buyer_stats[buyer_rut]["direct"] += row.contract_count
            buyer_stats[buyer_rut]["direct_amount"] += row.total_amount or 0

    for buyer_rut, stats in buyer_stats.items():
        if stats["total"] < MIN_TOTAL_CONTRACTS:
            continue
        ratio = stats["direct"] / stats["total"]

        if ratio >= DIRECT_RATIO_HIGH:
            severity = "alta"
        elif ratio >= DIRECT_RATIO_MEDIUM:
            severity = "media"
        else:
            continue

        alerts.append({
            "ocid": None,
            "alert_type": "TRAT",
            "severity": severity,
            "title": f"Trato directo excesivo: {stats['name'] or buyer_rut}",
            "description": (
                f"El organismo {stats['name'] or buyer_rut} realizó el "
                f"{ratio * 100:.1f}% de sus contratos ({stats['direct']} de "
                f"{stats['total']}) mediante trato directo. "
                f"Monto en trato directo: ${stats['direct_amount']:,.0f} CLP. "
                f"Un uso excesivo de trato directo puede indicar elusión "
                f"sistemática de procesos competitivos de licitación."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": stats["name"],
                "direct_contracts": stats["direct"],
                "total_contracts": stats["total"],
                "direct_ratio": round(ratio, 4),
                "direct_amount_clp": stats["direct_amount"],
                "total_amount_clp": stats["total_amount"],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": stats["name"],
            "supplier_rut": None,
            "supplier_name": None,
            "region": stats["region"],
            "amount_involved": stats["direct_amount"],
        })

    # --- DTDR: Desierta + subsequent direct purchase to same bidder ---
    # Find deserted tenders
    desert_query = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.tender_end,
            GROUP_CONCAT(DISTINCT pp_t.party_rut) AS bidder_ruts
        FROM procurements p
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        LEFT JOIN procurement_parties pp_t ON pp_t.procurement_ocid = p.ocid AND pp_t.role = 'tenderer'
        WHERE p.status IN ('unsuccessful', 'cancelled')
           OR p.method_details LIKE '%Desierta%'
        GROUP BY p.ocid, pp_b.party_rut, buyer_party.name, p.region, p.title, p.tender_end
    """)

    desert_rows = db.execute(desert_query).fetchall()

    # Find direct purchases after deserted tenders
    direct_query = text("""
        SELECT
            p.ocid,
            pp_b2.party_rut AS buyer_rut,
            p.tender_start,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            a.amount
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b2 ON pp_b2.procurement_ocid = p.ocid AND pp_b2.role = 'buyer'
        WHERE (p.method = 'limited' OR p.method_details LIKE '%TD%' OR p.method_details LIKE '%Trato%')
          AND p.tender_start IS NOT NULL
          AND pp_s.party_rut IS NOT NULL
    """)

    direct_rows = db.execute(direct_query).fetchall()

    # Index direct purchases by buyer_rut
    direct_by_buyer = defaultdict(list)
    for row in direct_rows:
        direct_by_buyer[row.buyer_rut].append(row)

    for desert in desert_rows:
        if not desert.buyer_rut or not desert.tender_end:
            continue

        bidder_ruts = set((desert.bidder_ruts or "").split(","))
        bidder_ruts.discard("")

        desert_end = _parse_date(desert.tender_end)
        for direct in direct_by_buyer.get(desert.buyer_rut, []):
            if not direct.tender_start:
                continue
            direct_start = _parse_date(direct.tender_start)
            if not direct_start or not desert_end:
                continue
            days_after = (direct_start - desert_end).days
            if 0 <= days_after <= DESERT_WINDOW_DAYS:
                if direct.supplier_rut in bidder_ruts:
                    alerts.append({
                        "ocid": direct.ocid,
                        "alert_type": "DTDR",
                        "severity": "alta",
                        "title": f"Licitación desierta seguida de trato directo al mismo oferente",
                        "description": (
                            f"El organismo {desert.buyer_name or desert.buyer_rut} declaró desierta "
                            f"la licitación '{desert.title or desert.ocid}' y {days_after} días después "
                            f"contrató directamente a {direct.supplier_name or direct.supplier_rut} "
                            f"(RUT: {direct.supplier_rut}), quien había participado en el proceso "
                            f"desierto. Monto del trato directo: ${direct.amount:,.0f} CLP. "
                            f"Este patrón puede indicar que la licitación se declaró desierta "
                            f"intencionalmente para adjudicar sin competencia."
                        ),
                        "evidence": {
                            "deserted_ocid": desert.ocid,
                            "deserted_title": desert.title,
                            "desert_end_date": str(desert.tender_end),
                            "direct_ocid": direct.ocid,
                            "direct_start_date": str(direct.tender_start),
                            "days_between": days_after,
                            "supplier_rut": direct.supplier_rut,
                            "supplier_name": direct.supplier_name,
                            "direct_amount": direct.amount,
                            "original_bidders": list(bidder_ruts),
                        },
                        "buyer_rut": desert.buyer_rut,
                        "buyer_name": desert.buyer_name,
                        "supplier_rut": direct.supplier_rut,
                        "supplier_name": direct.supplier_name,
                        "region": desert.region,
                        "amount_involved": direct.amount,
                    })

    logger.info(f"TRAT/DTDR detector: {len(alerts)} alerts generated")
    return alerts
