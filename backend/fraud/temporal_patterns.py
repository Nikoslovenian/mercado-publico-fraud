"""
Detector: Patrones Temporales Sospechosos (TEMP)
Detecta anomalias en los patrones de tiempo de las licitaciones:

  1. Licitaciones publicadas en horarios no laborales (madrugada, fines de semana)
  2. Concentracion excesiva de licitaciones al final del ano fiscal
  3. Multiples licitaciones del mismo organismo en el mismo dia
  4. Uso de "urgencia" sin justificacion aparente
"""
import logging
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Horarios no laborales en Chile
OFF_HOURS_START = 22  # 10 PM
OFF_HOURS_END = 6     # 6 AM
# Fin de ano fiscal (Chile: diciembre)
FISCAL_YEAR_END_MONTH = 12
# Umbral de concentracion en fin de ano
YEAR_END_RATIO_MEDIUM = 0.25  # > 25% de licitaciones en diciembre
YEAR_END_RATIO_HIGH = 0.40    # > 40%
# Umbral de licitaciones el mismo dia
SAME_DAY_THRESHOLD = 5  # 5+ licitaciones el mismo dia
MIN_TENDERS_TEMPORAL = 10  # Minimo de licitaciones para analisis temporal

URGENCY_KEYWORDS = [
    "urgente", "urgencia", "emergencia", "impostergable",
    "critico", "critica", "inmediato", "inmediata",
    "perentorio", "perentoria", "apremiante",
]


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
    Returns list of alert dicts for suspicious temporal patterns.
    """
    alerts = []

    query = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.description,
            p.method,
            p.method_details,
            p.tender_start,
            p.tender_end,
            p.total_amount,
            p.year,
            p.month
        FROM procurements p
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE p.tender_start IS NOT NULL
          AND pp_b.party_rut IS NOT NULL
    """)

    rows = db.execute(query).fetchall()

    # --- Strategy 1: Off-hours publications ---
    off_hours_by_buyer = defaultdict(list)

    for row in rows:
        ts = _parse_date(row.tender_start)
        if not ts:
            continue

        hour = ts.hour
        weekday = ts.weekday()  # 0=Monday, 6=Sunday

        is_off_hours = hour >= OFF_HOURS_START or hour < OFF_HOURS_END
        is_weekend = weekday >= 5  # Saturday or Sunday

        if is_off_hours or is_weekend:
            off_hours_by_buyer[row.buyer_rut].append({
                "ocid": row.ocid,
                "title": row.title,
                "datetime": ts,
                "hour": hour,
                "weekday": weekday,
                "is_weekend": is_weekend,
                "is_off_hours": is_off_hours,
                "amount": row.total_amount,
                "buyer_name": row.buyer_name,
                "region": row.region,
                "method": row.method_details,
            })

    for buyer_rut, off_hours_list in off_hours_by_buyer.items():
        if len(off_hours_list) < 3:
            continue

        first = off_hours_list[0]
        total_amount = sum(o["amount"] or 0 for o in off_hours_list)

        weekends = sum(1 for o in off_hours_list if o["is_weekend"])
        nights = sum(1 for o in off_hours_list if o["is_off_hours"])

        alerts.append({
            "ocid": first["ocid"],
            "alert_type": "TEMP",
            "severity": "media",
            "title": f"Publicaciones en horarios inusuales: {first['buyer_name'] or buyer_rut}",
            "description": (
                f"El organismo {first['buyer_name'] or buyer_rut} publico "
                f"{len(off_hours_list)} licitaciones en horarios no laborales: "
                f"{nights} en horario nocturno (22:00-06:00) y {weekends} en fines de semana. "
                f"Monto total: ${total_amount:,.0f} CLP. "
                f"La publicacion en horarios inusuales puede buscar reducir "
                f"la visibilidad de la licitacion y limitar la competencia."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": first["buyer_name"],
                "off_hours_count": len(off_hours_list),
                "weekend_count": weekends,
                "night_count": nights,
                "total_amount_clp": total_amount,
                "sample_publications": [
                    {
                        "ocid": o["ocid"],
                        "datetime": str(o["datetime"]),
                        "hour": o["hour"],
                        "day": ["lun", "mar", "mie", "jue", "vie", "sab", "dom"][o["weekday"]],
                    }
                    for o in off_hours_list[:10]
                ],
            },
            "buyer_rut": buyer_rut,
            "buyer_name": first["buyer_name"],
            "supplier_rut": None,
            "supplier_name": None,
            "region": first["region"],
            "amount_involved": total_amount,
        })

    # --- Strategy 2: Year-end concentration ---
    buyer_monthly = defaultdict(lambda: defaultdict(int))
    buyer_info = {}

    for row in rows:
        if not row.month or not row.year:
            continue
        buyer_monthly[row.buyer_rut][row.month] += 1
        buyer_info[row.buyer_rut] = {
            "name": row.buyer_name or "",
            "region": row.region or "",
        }

    for buyer_rut, monthly in buyer_monthly.items():
        total = sum(monthly.values())
        if total < MIN_TENDERS_TEMPORAL:
            continue

        dec_count = monthly.get(FISCAL_YEAR_END_MONTH, 0)
        dec_ratio = dec_count / total

        if dec_ratio >= YEAR_END_RATIO_HIGH:
            severity = "alta"
        elif dec_ratio >= YEAR_END_RATIO_MEDIUM:
            severity = "media"
        else:
            continue

        info = buyer_info.get(buyer_rut, {"name": "", "region": ""})

        alerts.append({
            "ocid": None,
            "alert_type": "TEMP",
            "severity": severity,
            "title": f"Concentracion de compras en fin de ano: {info['name'] or buyer_rut}",
            "description": (
                f"El organismo {info['name'] or buyer_rut} concentra el "
                f"{dec_ratio * 100:.1f}% de sus licitaciones ({dec_count} de {total}) "
                f"en diciembre (fin del ano fiscal). "
                f"La concentracion excesiva de compras al final del periodo puede "
                f"indicar ejecucion apresurada de presupuesto remanente, con menor "
                f"rigor en la evaluacion y control de los procesos."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": info["name"],
                "december_count": dec_count,
                "total_tenders": total,
                "december_ratio": round(dec_ratio, 4),
                "monthly_distribution": dict(monthly),
            },
            "buyer_rut": buyer_rut,
            "buyer_name": info["name"],
            "supplier_rut": None,
            "supplier_name": None,
            "region": info["region"],
            "amount_involved": None,
        })

    # --- Strategy 3: Multiple tenders same day ---
    buyer_daily = defaultdict(lambda: defaultdict(list))

    for row in rows:
        ts = _parse_date(row.tender_start)
        if not ts:
            continue
        day_key = ts.strftime("%Y-%m-%d")
        buyer_daily[row.buyer_rut][day_key].append({
            "ocid": row.ocid,
            "title": row.title,
            "amount": row.total_amount,
            "method": row.method_details,
            "buyer_name": row.buyer_name,
            "region": row.region,
        })

    for buyer_rut, days in buyer_daily.items():
        for day, tenders in days.items():
            if len(tenders) < SAME_DAY_THRESHOLD:
                continue

            first = tenders[0]
            total_amount = sum(t["amount"] or 0 for t in tenders)

            alerts.append({
                "ocid": first["ocid"],
                "alert_type": "TEMP",
                "severity": "media",
                "title": (
                    f"Multiples licitaciones en un dia: {first['buyer_name'] or buyer_rut} "
                    f"({day})"
                ),
                "description": (
                    f"El organismo {first['buyer_name'] or buyer_rut} publico "
                    f"{len(tenders)} licitaciones el dia {day}. "
                    f"Monto total: ${total_amount:,.0f} CLP. "
                    f"La publicacion masiva de licitaciones en un mismo dia puede "
                    f"dificultar la revision adecuada de las bases y reducir la "
                    f"competencia efectiva por saturacion de procesos."
                ),
                "evidence": {
                    "buyer_rut": buyer_rut,
                    "buyer_name": first["buyer_name"],
                    "date": day,
                    "tender_count": len(tenders),
                    "total_amount_clp": total_amount,
                    "tenders": [
                        {
                            "ocid": t["ocid"],
                            "title": t["title"],
                            "amount": t["amount"],
                            "method": t["method"],
                        }
                        for t in tenders[:10]
                    ],
                },
                "buyer_rut": buyer_rut,
                "buyer_name": first["buyer_name"],
                "supplier_rut": None,
                "supplier_name": None,
                "region": first["region"],
                "amount_involved": total_amount,
            })

    # --- Strategy 4: Urgency keywords in non-urgent methods ---
    urgency_pattern = re.compile(
        "|".join(URGENCY_KEYWORDS), re.IGNORECASE
    )

    for row in rows:
        # Only flag urgency in competitive methods (not trato directo)
        if row.method not in ("open", "selective"):
            continue

        text_to_check = f"{row.title or ''} {row.description or ''}"
        match = urgency_pattern.search(text_to_check)
        if not match:
            continue

        ts = _parse_date(row.tender_start)
        te = _parse_date(row.tender_end)
        tender_days = None
        if ts and te:
            tender_days = (te - ts).days

        # Only alert if tender period is also short (< 7 days)
        if tender_days is not None and tender_days >= 7:
            continue

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "TEMP",
            "severity": "media",
            "title": f"Urgencia en licitacion competitiva: {row.title[:80] if row.title else row.ocid}",
            "description": (
                f"La licitacion '{row.title or row.ocid}' del organismo "
                f"{row.buyer_name or row.buyer_rut} usa lenguaje de urgencia "
                f"('{match.group()}') en un proceso competitivo "
                + (f"con plazo de solo {tender_days} dias. " if tender_days is not None else ". ")
                + f"Modalidad: {row.method_details or row.method}. "
                f"Monto: ${(row.total_amount or 0):,.0f} CLP. "
                f"El uso de urgencia injustificada en procesos competitivos puede "
                f"buscar acortar plazos y limitar la participacion."
            ),
            "evidence": {
                "ocid": row.ocid,
                "urgency_keyword": match.group(),
                "title": row.title,
                "tender_days": tender_days,
                "method": row.method_details,
                "amount": row.total_amount,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": None,
            "supplier_name": None,
            "region": row.region,
            "amount_involved": row.total_amount,
        })

    logger.info(f"TEMP detector: {len(alerts)} alerts generated")
    return alerts
