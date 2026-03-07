"""
Detector: Empresas Nuevas Ganadoras (NUEV)
Detecta empresas recien constituidas que ganan contratos de alto valor.
Una empresa con pocos meses de vida que gana licitaciones grandes es un
indicador de posible empresa de fachada o creada ad-hoc para un contrato.

Criterios:
  - Empresa con < 6 meses de inicio de actividades gana > 100 UTM → alta
  - Empresa con < 12 meses gana > 50 UTM → media
  - Empresa sin historial previo (primera aparicion en el sistema) gana > 200 UTM → media
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025
THRESHOLD_HIGH = 100 * UTM       # ~6.7M CLP
THRESHOLD_MEDIUM = 50 * UTM      # ~3.4M CLP
THRESHOLD_NO_HISTORY = 200 * UTM # ~13.5M CLP
MAX_AGE_HIGH_MONTHS = 6
MAX_AGE_MEDIUM_MONTHS = 12


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


def _months_between(d1: datetime, d2: datetime) -> float:
    """Calculate approximate months between two dates."""
    return (d2 - d1).days / 30.44


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for new supplier winners.
    """
    alerts = []

    # Strategy 1: Suppliers with known SII start date
    query_sii = text("""
        SELECT
            pa.rut,
            pa.name,
            pa.sii_start_date,
            pa.sii_activity_code,
            a.ocid,
            a.amount,
            a.date AS award_date,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.method_details
        FROM parties pa
        JOIN procurement_parties pp_s ON pp_s.party_rut = pa.rut AND pp_s.role = 'supplier'
        JOIN awards a ON a.ocid = pp_s.procurement_ocid
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pa.sii_start_date IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND a.date IS NOT NULL
    """)

    rows = db.execute(query_sii).fetchall()

    seen_ruts = set()
    for row in rows:
        sii_start = _parse_date(row.sii_start_date)
        award_date = _parse_date(row.award_date)

        if not sii_start or not award_date:
            continue

        if award_date < sii_start:
            continue  # Bad data

        age_months = _months_between(sii_start, award_date)
        amount = row.amount or 0

        severity = None
        if age_months < MAX_AGE_HIGH_MONTHS and amount >= THRESHOLD_HIGH:
            severity = "alta"
        elif age_months < MAX_AGE_MEDIUM_MONTHS and amount >= THRESHOLD_MEDIUM:
            severity = "media"

        if not severity:
            continue

        # Deduplicate: one alert per supplier (pick highest amount)
        if row.rut in seen_ruts:
            continue
        seen_ruts.add(row.rut)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "NUEV",
            "severity": severity,
            "title": f"Empresa nueva gana contrato: {row.name or row.rut}",
            "description": (
                f"El proveedor {row.name or row.rut} (RUT: {row.rut}) inicio "
                f"actividades en SII hace solo {age_months:.0f} meses "
                f"(fecha inicio: {sii_start.date()}) y gano un contrato por "
                f"${amount:,.0f} CLP con el organismo {row.buyer_name or row.buyer_rut}. "
                f"Giro: {row.sii_activity_code or 'no registrado'}. "
                f"Empresas recien constituidas que ganan contratos de alto valor "
                f"pueden ser fachadas creadas para un contrato especifico."
            ),
            "evidence": {
                "supplier_rut": row.rut,
                "supplier_name": row.name,
                "sii_start_date": str(sii_start.date()),
                "award_date": str(award_date.date()),
                "age_months": round(age_months, 1),
                "award_amount": amount,
                "sii_activity": row.sii_activity_code,
                "method_details": row.method_details,
                "ocid": row.ocid,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.rut,
            "supplier_name": row.name,
            "region": row.region,
            "amount_involved": amount,
        })

    # Strategy 2: Suppliers with no prior history in the system
    # (first appearance, and they win a large contract)
    query_first = text("""
        SELECT
            pp_s2.party_rut AS supplier_rut,
            supplier_party2.name AS supplier_name,
            a.ocid,
            a.amount,
            a.date AS award_date,
            pp_b2.party_rut AS buyer_rut,
            buyer_party2.name AS buyer_name,
            p.region,
            p.title,
            p.method_details,
            MIN(p.tender_start) AS first_appearance
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s2 ON pp_s2.procurement_ocid = a.ocid AND pp_s2.role = 'supplier'
        JOIN parties supplier_party2 ON supplier_party2.rut = pp_s2.party_rut
        JOIN procurement_parties pp_b2 ON pp_b2.procurement_ocid = p.ocid AND pp_b2.role = 'buyer'
        JOIN parties buyer_party2 ON buyer_party2.rut = pp_b2.party_rut
        WHERE pp_s2.party_rut IS NOT NULL
          AND a.amount IS NOT NULL
          AND a.amount >= :threshold
          AND pp_s2.party_rut NOT IN (
              SELECT DISTINCT rut FROM parties WHERE sii_start_date IS NOT NULL
          )
        GROUP BY pp_s2.party_rut
        HAVING COUNT(DISTINCT a.ocid) = 1
        ORDER BY a.amount DESC
    """)

    rows2 = db.execute(query_first, {"threshold": THRESHOLD_NO_HISTORY}).fetchall()

    for row in rows2:
        if row.supplier_rut in seen_ruts:
            continue
        seen_ruts.add(row.supplier_rut)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "NUEV",
            "severity": "media",
            "title": f"Proveedor sin historial gana contrato alto: {row.supplier_name or row.supplier_rut}",
            "description": (
                f"El proveedor {row.supplier_name or row.supplier_rut} "
                f"(RUT: {row.supplier_rut}) aparece por primera vez en el sistema "
                f"y gana un contrato por ${row.amount:,.0f} CLP con el organismo "
                f"{row.buyer_name or row.buyer_rut}. No tiene historial previo "
                f"de participacion en compras publicas ni datos de inicio de "
                f"actividades en SII."
            ),
            "evidence": {
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "first_appearance": str(row.first_appearance) if row.first_appearance else None,
                "award_amount": row.amount,
                "total_contracts": 1,
                "no_sii_data": True,
                "ocid": row.ocid,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    logger.info(f"NUEV detector: {len(alerts)} alerts generated")
    return alerts
