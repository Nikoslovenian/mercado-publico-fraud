"""
Detector: Plazos Anómalos (PLAZ)
Flags tenders with unreasonably short periods that prevent fair competition.

Legal minimums by method (Reglamento de la Ley 19.886):
  - LP (>1000 UTM): 20+ calendar days for bidding
  - LE (100-1000 UTM): 10+ calendar days
  - L1 (<100 UTM): 5+ calendar days
  - Trato Directo: not applicable (no competition)
"""
import logging
import re
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

# Minimum days by method_details prefix
MIN_DAYS = {
    "LP": 20,   # Licitación Pública > 1000 UTM
    "LE": 10,   # Licitación Pública 100-1000 UTM
    "LQ": 10,   # Licitación Privada
    "LR": 10,
    "L1": 5,    # Licitación < 100 UTM
    "CO": None, # Convenio marco
    "AM": None, # Acuerdo marco
    "TD": None, # Trato directo (skip)
    "AT": None, # Ato Administrativo
}

VERY_SHORT_DAYS = 3   # Award issued within 3 days of closing → very suspicious
MAX_AWARD_DAYS = 1    # Award less than 1 day after closing → impossible / pre-arranged


def detect(db: Session) -> list[dict]:
    alerts = []

    query = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.method,
            p.method_details,
            p.tender_start,
            p.tender_end,
            p.award_date,
            p.total_amount
        FROM procurements p
        LEFT JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        LEFT JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE p.tender_start IS NOT NULL
          AND p.tender_end IS NOT NULL
    """)

    rows = db.execute(query).fetchall()

    for row in rows:
        ts = _parse_date(row.tender_start)
        te = _parse_date(row.tender_end)
        if not ts or not te:
            continue

        tender_days = (te - ts).days
        # Extract code from parentheses: "Licitación Pública Entre 100 y 1000 UTM (LE)" → "LE"
        m = re.search(r'\((\w+)\)\s*$', (row.method_details or ""))
        method_prefix = m.group(1).upper() if m else (row.method_details or "")[:2].upper()

        min_days = MIN_DAYS.get(method_prefix)
        if min_days is None:
            continue  # Skip trato directo and framework agreements

        if tender_days < 0:
            continue  # Bad data: end before start

        severity = None
        description = ""

        if tender_days < VERY_SHORT_DAYS:
            severity = "alta"
            description = (
                f"El período de licitación fue de solo {tender_days} días "
                f"(del {ts.date()} al {te.date()}). "
                f"El mínimo legal para modalidad {method_prefix} es {min_days} días. "
                f"Un plazo tan corto impide la participación real de competidores."
            )
        elif tender_days < min_days:
            severity = "media"
            description = (
                f"El período de licitación ({tender_days} días) es inferior al mínimo "
                f"legal de {min_days} días para modalidad {method_prefix}. "
                f"Esto puede limitar artificialmente la competencia."
            )

        # Check award date anomaly
        ad = _parse_date(row.award_date)
        if ad and te:
            award_lag = (ad - te).days
            if award_lag < MAX_AWARD_DAYS and award_lag >= 0:
                severity = "alta"
                description += (
                    f" Además, la adjudicación se realizó {award_lag} días después del cierre "
                    f"({ad.date()}), lo que sugiere que el ganador estaba "
                    f"predeterminado antes de la apertura de ofertas."
                )

        if severity:
            alerts.append({
                "ocid": row.ocid,
                "alert_type": "PLAZ",
                "severity": severity,
                "title": f"Plazo de licitación irregular: {row.title[:80] if row.title else row.ocid}",
                "description": description.strip(),
                "evidence": {
                    "ocid": row.ocid,
                    "tender_start": str(ts),
                    "tender_end": str(te),
                    "award_date": str(ad) if ad else None,
                    "tender_days": tender_days,
                    "min_legal_days": min_days,
                    "method_details": row.method_details,
                    "award_lag_days": (ad - te).days if ad and te else None,
                },
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "supplier_rut": None,
                "supplier_name": None,
                "region": row.region,
                "amount_involved": row.total_amount,
            })

    logger.info(f"PLAZ detector: {len(alerts)} alerts generated")
    return alerts
