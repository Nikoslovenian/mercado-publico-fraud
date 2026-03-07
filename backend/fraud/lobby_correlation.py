"""
Detector: Correlacion de Lobby / Pre-arreglo (LOBB)
Detects patterns suggesting pre-arrangement between buyers and suppliers,
without requiring external InfoLobby data.

Strategies:
  (a) Direct purchase (trato directo) to suppliers who won multiple previous
      contracts from the same buyer in last 12 months - suggests relationship.
  (b) Buyers with a pattern of urgency/emergency trato directo followed by
      awards to the same supplier repeatedly.
"""
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session  # type: ignore
from sqlalchemy import text  # type: ignore

logger = logging.getLogger(__name__)

# Strategy A thresholds
MIN_PREVIOUS_AWARDS = 3      # Supplier must have 3+ prior awards from same buyer
LOOKBACK_MONTHS = 12         # Look back 12 months for prior history
MIN_DIRECT_AMOUNT = 0        # Any amount (we care about pattern, not size)

# Strategy B thresholds
MIN_URGENCY_PATTERNS = 2     # At least 2 urgency-based TDs to same supplier
URGENCY_KEYWORDS = [
    "urgencia", "urgente", "emergencia", "imprevisto",
    "imprevist", "catastrofe", "fuerza mayor",
    "excepcion", "excepcional", "causal",
]


def _parse_date(val):
    """Parse date from string or datetime. Returns datetime or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)[:19]  # type: ignore
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for patterns suggesting pre-arrangement.
    Uses existing procurement data only (no external InfoLobby data).
    """
    alerts = []

    # --- Strategy A: Trato directo to repeat winners ---
    # Get all trato directo awards
    query_td = text("""
        SELECT
            p.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            p.method,
            p.method_details,
            p.tender_start,
            p.total_amount,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            a.amount AS award_amount
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE (p.method = 'limited' OR p.method_details LIKE '%TD%'
               OR p.method_details LIKE '%Trato%' OR p.method_details LIKE '%AT%')
          AND pp_s.party_rut IS NOT NULL
          AND pp_b.party_rut IS NOT NULL
          AND p.tender_start IS NOT NULL
        ORDER BY pp_b.party_rut, p.tender_start
    """)

    td_rows = db.execute(query_td).fetchall()

    # Get all awards (for checking prior history)
    query_all_awards = text("""
        SELECT
            p.ocid,
            pp_b2.party_rut AS buyer_rut,
            buyer_party2.name AS buyer_name,
            pp_s2.party_rut AS supplier_rut,
            supplier_party2.name AS supplier_name,
            a.amount,
            p.tender_start,
            p.method,
            p.method_details
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN procurement_parties pp_s2 ON pp_s2.procurement_ocid = a.ocid AND pp_s2.role = 'supplier'
        JOIN parties supplier_party2 ON supplier_party2.rut = pp_s2.party_rut
        JOIN procurement_parties pp_b2 ON pp_b2.procurement_ocid = p.ocid AND pp_b2.role = 'buyer'
        JOIN parties buyer_party2 ON buyer_party2.rut = pp_b2.party_rut
        WHERE pp_s2.party_rut IS NOT NULL
          AND pp_b2.party_rut IS NOT NULL
          AND p.tender_start IS NOT NULL
        ORDER BY p.tender_start
    """)

    all_awards = db.execute(query_all_awards).fetchall()

    # Index all awards by (buyer_rut, supplier_rut) with dates
    buyer_supplier_history = {}
    for row in all_awards:
        dt = _parse_date(row.tender_start)
        if dt:
            key = (row.buyer_rut, row.supplier_rut)
            if key not in buyer_supplier_history:
                buyer_supplier_history[key] = []
            key = (row.buyer_rut, row.supplier_rut)
            buyer_supplier_history[key].append({
                "ocid": row.ocid,
                "date": dt,
                "amount": row.amount,
                "method": row.method,
                "method_details": row.method_details,
            })

    seen_strategy_a = set()

    for row in td_rows:
        td_date = _parse_date(row.tender_start)
        if not td_date:
            continue

        key = (row.buyer_rut, row.supplier_rut)
        if key in seen_strategy_a:
            continue

        # Look for prior awards from same buyer to same supplier
        history = buyer_supplier_history.get(key, [])
        lookback_start = td_date - timedelta(days=LOOKBACK_MONTHS * 30)

        prior_awards = [
            h for h in history
            if lookback_start <= h["date"] < td_date
        ]

        if len(prior_awards) < MIN_PREVIOUS_AWARDS:
            continue

        seen_strategy_a.add(key)

        total_prior_amount = sum(h["amount"] for h in prior_awards if h["amount"])
        td_amount = row.award_amount or row.total_amount or 0

        # Count how many prior awards were also trato directo
        prior_td = [
            h for h in prior_awards
            if h["method"] == "limited"
            or "TD" in str(h["method_details"] or "").upper()
            or "TRATO" in str(h["method_details"] or "").upper()
        ]

        severity = "alta" if len(prior_awards) >= 5 or len(prior_td) >= 3 else "media"

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "LOBB",
            "severity": severity,
            "title": (
                f"Trato directo a proveedor recurrente: "
                f"{row.supplier_name or row.supplier_rut}"
            ),
            "description": (
                f"El organismo {row.buyer_name or row.buyer_rut} adjudico un "
                f"trato directo a {row.supplier_name or row.supplier_rut} "
                f"(RUT: {row.supplier_rut}) por ${td_amount:,.0f} CLP. "
                f"Este proveedor ya habia recibido {len(prior_awards)} "
                f"contratos previos del mismo organismo en los ultimos "
                f"{LOOKBACK_MONTHS} meses (monto total previo: "
                f"${total_prior_amount:,.0f} CLP"
                + (f", incluyendo {len(prior_td)} tratos directos previos"
                   if prior_td else "")
                + f"). El patron de compras directas repetidas al mismo "
                f"proveedor sugiere una relacion comercial que podria "
                f"estar eludiendo la competencia."
            ),
            "evidence": {
                "ocid": row.ocid,
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "td_amount": td_amount,
                "prior_award_count": len(prior_awards),
                "prior_td_count": len(prior_td),
                "prior_total_amount": total_prior_amount,
                "lookback_months": LOOKBACK_MONTHS,
                "prior_ocids": [h["ocid"] for h in prior_awards[:10]],  # type: ignore
                "prior_dates": [str(h["date"].date()) for h in prior_awards[:10]],  # type: ignore
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": td_amount,
        })

    # --- Strategy B: Urgency/emergency trato directo patterns ---
    # Find TDs with urgency keywords in title/description
    query_urgency = text("""
        SELECT
            p.ocid,
            pp_b3.party_rut AS buyer_rut,
            buyer_party3.name AS buyer_name,
            p.region,
            p.title,
            p.description,
            p.method_details,
            p.tender_start,
            pp_s3.party_rut AS supplier_rut,
            supplier_party3.name AS supplier_name,
            a.amount
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN procurement_parties pp_s3 ON pp_s3.procurement_ocid = a.ocid AND pp_s3.role = 'supplier'
        JOIN parties supplier_party3 ON supplier_party3.rut = pp_s3.party_rut
        JOIN procurement_parties pp_b3 ON pp_b3.procurement_ocid = p.ocid AND pp_b3.role = 'buyer'
        JOIN parties buyer_party3 ON buyer_party3.rut = pp_b3.party_rut
        WHERE (p.method = 'limited' OR p.method_details LIKE '%TD%'
               OR p.method_details LIKE '%Trato%')
          AND pp_s3.party_rut IS NOT NULL
          AND pp_b3.party_rut IS NOT NULL
    """)

    urgency_rows = db.execute(query_urgency).fetchall()

    # Filter for urgency keywords
    urgency_tds = {}  # (buyer_rut, supplier_rut) -> list of urgency TDs

    for row in urgency_rows:
        text_to_search = (
            ((row.title or "") + " " + (row.description or "") + " "
             + (row.method_details or "")).lower()
        )

        is_urgency = any(kw in text_to_search for kw in URGENCY_KEYWORDS)
        if not is_urgency:
            continue

        key = (row.buyer_rut, row.supplier_rut)
        if key not in urgency_tds:
            urgency_tds[key] = []
        urgency_tds[key].append(row)

    seen_strategy_b = set()

    for (buyer_rut, supplier_rut), urgency_list in urgency_tds.items():
        if len(urgency_list) < MIN_URGENCY_PATTERNS:
            continue

        key = (buyer_rut, supplier_rut)
        if key in seen_strategy_b or key in seen_strategy_a:
            continue
        seen_strategy_b.add(key)

        first = urgency_list[0]
        total_amount = sum(r.amount for r in urgency_list if r.amount)

        alerts.append({
            "ocid": first.ocid,
            "alert_type": "LOBB",
            "severity": "alta",
            "title": (
                f"Patron de urgencia repetida: {first.buyer_name or buyer_rut} "
                f"a {first.supplier_name or supplier_rut}"
            ),
            "description": (
                f"El organismo {first.buyer_name or buyer_rut} ha realizado "
                f"{len(urgency_list)} tratos directos invocando urgencia o "
                f"emergencia al proveedor {first.supplier_name or supplier_rut} "
                f"(RUT: {supplier_rut}). Monto total: ${total_amount:,.0f} CLP. "
                f"El uso repetido de causales de urgencia para contratar al "
                f"mismo proveedor sugiere un posible abuso de la excepcion "
                f"de urgencia para evadir procesos competitivos."
            ),
            "evidence": {
                "buyer_rut": buyer_rut,
                "buyer_name": first.buyer_name,
                "supplier_rut": supplier_rut,
                "supplier_name": first.supplier_name,
                "urgency_td_count": len(urgency_list),
                "total_amount": total_amount,
                "ocids": [r.ocid for r in urgency_list[:10]],  # type: ignore
                "titles": [r.title for r in urgency_list[:10] if r.title],  # type: ignore
                "urgency_keywords_found": list(set(
                    kw for r in urgency_list
                    for kw in URGENCY_KEYWORDS
                    if kw in ((r.title or "") + " " + (r.description or "")).lower()
                )),
            },
            "buyer_rut": buyer_rut,
            "buyer_name": first.buyer_name,
            "supplier_rut": supplier_rut,
            "supplier_name": first.supplier_name,
            "region": first.region,
            "amount_involved": total_amount,
        })

    # --- Strategy C: External InfoLobby Meetings ---
    # Query all external lobby data
    query_lobby = text("SELECT rut, raw_data FROM external_data WHERE source = 'infolobby'")
    lobby_rows = db.execute(query_lobby).fetchall()
    
    lobby_data_by_rut = {}
    from json import loads
    
    for row in lobby_rows:
        try:
            raw = loads(row.raw_data) if isinstance(row.raw_data, str) else row.raw_data
            if raw and "audiencias" in raw:
                lobby_data_by_rut[row.rut] = raw["audiencias"]
        except Exception as e:
            continue

    if lobby_data_by_rut:
        # Check awards directly against lobby dates
        seen_strategy_c = set()
        
        for award in all_awards:
            sup_rut = award.supplier_rut
            if not sup_rut or sup_rut not in lobby_data_by_rut:
                continue
                
            tender_dt = _parse_date(award.tender_start)
            if not tender_dt: continue
            
            audiencias = lobby_data_by_rut[sup_rut]
            
            # Look for audiences within 150 days BEFORE tender start
            for aud in audiencias:
                aud_dt = _parse_date(aud.get("fecha"))
                if not aud_dt: continue
                
                days_diff = (tender_dt - aud_dt).days
                if 0 < days_diff <= 150:
                    # Very simple matching: is there any overlap in buyer name and institucion name?
                    buyer_n = (award.buyer_name or "").lower() # type: ignore
                    inst = (aud.get("institucion", "")).lower()
                    
                    # Fuzzy match: significant words overlap
                    ignore_words = {"de", "del", "la", "el", "y", "los", "las", "para", "ministerio", "municipalidad", "subsecretaria", "direccion"}
                    buyer_words = set(buyer_n.split()) - ignore_words
                    inst_words = set(inst.split()) - ignore_words
                    
                    overlap = buyer_words & inst_words
                    if not overlap and buyer_n != inst:
                        continue # Skip if they don't seem like the same institution
                    
                    
                    key = (award.ocid, sup_rut) # type: ignore
                    if key in seen_strategy_c:
                        continue
                        
                    seen_strategy_c.add(key)
                    
                    alerts.append({
                        "ocid": award.ocid, # type: ignore
                        "alert_type": "LOBB",
                        "severity": "critica" if days_diff < 30 else "alta",
                        "title": f"Reunión de Lobby (InfoLobby) previa a Adjudicación: {award.supplier_name or sup_rut}", # type: ignore
                        "description": (
                            f"Se detectó, a través de la API Abierta de InfoLobby, que representantes de la empresa "
                            f"{award.supplier_name or sup_rut} sostuvieron una audiencia con " # type: ignore
                            f"{aud.get('sujeto_pasivo', 'una autoridad')} ({aud.get('cargo', '')}) el {aud.get('fecha')}, "
                            f"solo {days_diff} días antes de que iniciara el proceso de licitación que "
                            f"finalmente ganaron por ${award.amount:,.0f} CLP." # type: ignore
                        ),
                        "evidence": {
                            "buyer_rut": award.buyer_rut, # type: ignore
                            "supplier_rut": sup_rut,
                            "supplier_name": award.supplier_name, # type: ignore
                            "meeting_date": aud.get("fecha"),
                            "tender_start": str(tender_dt.date()),
                            "days_difference": days_diff,
                            "authority": aud.get("sujeto_pasivo"),
                            "cargo": aud.get("cargo"),
                            "materia": aud.get("materia"),
                            "amount": award.amount # type: ignore
                        },
                        "buyer_rut": award.buyer_rut, # type: ignore
                        "buyer_name": award.buyer_name, # type: ignore
                        "supplier_rut": sup_rut,
                        "supplier_name": award.supplier_name, # type: ignore
                        "amount_involved": award.amount, # type: ignore
                    })

    logger.info(f"LOBB detector: {len(alerts)} alerts generated")
    return alerts
