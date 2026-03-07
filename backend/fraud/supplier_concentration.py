"""
Detector: Concentración de Proveedores (CONC)
Uses Herfindahl-Hirschman Index (HHI) to detect market concentration
by region + UNSPSC category and by buyer + supplier dominance.
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

HHI_MEDIUM = 0.25   # 1 supplier controls 25%+ of a market segment
HHI_HIGH = 0.40     # 1 supplier controls 40%+ of a market segment
MIN_CONTRACTS = 5   # Minimum contracts in segment to be meaningful
DOMINANCE_HIGH = 0.70  # Supplier wins 70%+ of buyer's contracts in a category


def detect(db: Session) -> list[dict]:
    alerts = []

    # --- HHI by region + UNSPSC prefix ---
    query = text("""
        SELECT
            p.region,
            i.unspsc_prefix,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            COUNT(DISTINCT p.ocid) AS contract_count,
            SUM(a.amount) AS total_amount
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN items i ON i.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        WHERE pp_s.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND p.region != ''
          AND i.unspsc_prefix != ''
        GROUP BY p.region, i.unspsc_prefix, pp_s.party_rut, supplier_party.name
    """)

    rows = db.execute(query).fetchall()

    # Group by (region, unspsc_prefix)
    segments = defaultdict(list)
    for row in rows:
        key = (row.region, row.unspsc_prefix)
        segments[key].append(row)

    for (region, unspsc_prefix), suppliers in segments.items():
        total_segment = sum(r.total_amount for r in suppliers if r.total_amount)
        total_contracts = sum(r.contract_count for r in suppliers)

        if total_contracts < MIN_CONTRACTS or total_segment == 0:
            continue

        # Calculate HHI
        hhi = sum((r.total_amount / total_segment) ** 2 for r in suppliers if r.total_amount)

        # Find top supplier
        top = max(suppliers, key=lambda r: r.total_amount or 0)
        top_share = (top.total_amount or 0) / total_segment

        if hhi >= HHI_HIGH or top_share >= DOMINANCE_HIGH:
            severity = "alta"
        elif hhi >= HHI_MEDIUM:
            severity = "media"
        else:
            continue

        alerts.append({
            "ocid": None,
            "alert_type": "CONC",
            "severity": severity,
            "title": f"Alta concentración de proveedor: {top.supplier_name or top.supplier_rut} en {region}",
            "description": (
                f"En la región {region}, categoría UNSPSC {unspsc_prefix}, "
                f"el proveedor {top.supplier_name or top.supplier_rut} concentra el "
                f"{top_share * 100:.1f}% del mercado ({top.contract_count} contratos, "
                f"${top.total_amount:,.0f} CLP). Índice HHI del segmento: {hhi:.3f}. "
                f"Un valor HHI > 0.25 indica concentración significativa de mercado."
            ),
            "evidence": {
                "region": region,
                "unspsc_prefix": unspsc_prefix,
                "hhi": round(hhi, 4),
                "top_supplier_rut": top.supplier_rut,
                "top_supplier_name": top.supplier_name,
                "top_supplier_share": round(top_share, 4),
                "top_supplier_contracts": top.contract_count,
                "top_supplier_amount": top.total_amount,
                "total_segment_contracts": total_contracts,
                "total_segment_amount": total_segment,
                "all_suppliers": [
                    {
                        "rut": r.supplier_rut,
                        "name": r.supplier_name,
                        "contracts": r.contract_count,
                        "amount": r.total_amount,
                        "share": round((r.total_amount or 0) / total_segment, 4),
                    }
                    for r in sorted(suppliers, key=lambda x: x.total_amount or 0, reverse=True)[:10]
                ],
            },
            "buyer_rut": None,
            "buyer_name": None,
            "supplier_rut": top.supplier_rut,
            "supplier_name": top.supplier_name,
            "region": region,
            "amount_involved": top.total_amount,
        })

    # --- Buyer-level concentration: one supplier wins majority of buyer's contracts ---
    query2 = text("""
        SELECT
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            COUNT(DISTINCT p.ocid) AS contract_count,
            SUM(a.amount) AS total_amount
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pp_s.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND pp_b.party_rut IS NOT NULL
        GROUP BY pp_b.party_rut, buyer_party.name, p.region, pp_s.party_rut, supplier_party.name
    """)

    rows2 = db.execute(query2).fetchall()

    buyer_segments = defaultdict(list)
    for row in rows2:
        buyer_segments[row.buyer_rut].append(row)

    for buyer_rut, buyer_suppliers in buyer_segments.items():
        total_amount = sum(r.total_amount for r in buyer_suppliers if r.total_amount)
        total_contracts = sum(r.contract_count for r in buyer_suppliers)

        if total_contracts < MIN_CONTRACTS or total_amount == 0:
            continue

        top = max(buyer_suppliers, key=lambda r: r.total_amount or 0)
        top_share = (top.total_amount or 0) / total_amount

        if top_share >= 0.80 and total_contracts >= 10:
            severity = "alta"
        elif top_share >= DOMINANCE_HIGH and total_contracts >= 5:
            severity = "media"
        else:
            continue

        alerts.append({
            "ocid": None,
            "alert_type": "CONC",
            "severity": severity,
            "title": f"Organismo {top.buyer_name or buyer_rut} concentra {top_share*100:.0f}% en un proveedor",
            "description": (
                f"El organismo {top.buyer_name or buyer_rut} adjudicó el "
                f"{top_share * 100:.1f}% de su gasto total ({top.contract_count} de "
                f"{total_contracts} contratos, ${top.total_amount:,.0f} CLP) "
                f"al proveedor {top.supplier_name or top.supplier_rut}. "
                f"Esta dependencia extrema en un único proveedor puede indicar "
                f"direccionamiento de licitaciones o falta de competencia real."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": top.buyer_name,
                "top_supplier_rut": top.supplier_rut,
                "top_supplier_name": top.supplier_name,
                "top_share": round(top_share, 4),
                "top_contracts": top.contract_count,
                "top_amount": top.total_amount,
                "total_contracts": total_contracts,
                "total_amount": total_amount,
            },
            "buyer_rut": buyer_rut,
            "buyer_name": top.buyer_name,
            "supplier_rut": top.supplier_rut,
            "supplier_name": top.supplier_name,
            "region": top.region,
            "amount_involved": top.total_amount,
        })

    logger.info(f"CONC detector: {len(alerts)} alerts generated")
    return alerts
