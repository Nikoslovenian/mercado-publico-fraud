"""
Detector: Empresa Fantasma / Contrabando de Giros (FANT)
Detecta esquemas avanzados de "Proveedores Express" limitados a Tratos Directos
y discrepancias extremas entre el rubro de la empresa (SII) y lo contratado.

Estrategias:
  1. Proveedor Express de Trato Directo: Empresa gana un trato directo con < 3 o 6 meses de vida.
  2. Contrabando de Giros (Mismatch): El código de actividad de la empresa carece de relación con 
     el título y descripción de la licitación.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session  # type: ignore
from sqlalchemy import text  # type: ignore

logger = logging.getLogger(__name__)

def _parse_date(val):
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

def _months_between(d1: datetime, d2: datetime) -> float:
    return (d2 - d1).days / 30.44

def detect(db: Session) -> list[dict]:
    alerts = []
    
    # --- Estrategia 1: Proveedor Express en Tratos Directos ---
    query_express = text("""
        SELECT
            pa.rut,
            pa.name as supplier_name,
            pa.sii_start_date,
            pa.sii_activity_code,
            a.ocid,
            a.amount,
            p.tender_start,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.method,
            p.method_details,
            p.title
        FROM parties pa
        JOIN procurement_parties pp_s ON pp_s.party_rut = pa.rut AND pp_s.role = 'supplier'
        JOIN awards a ON a.ocid = pp_s.procurement_ocid
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pa.sii_start_date IS NOT NULL
          AND a.amount IS NOT NULL AND a.amount > 0
          AND (p.method = 'limited' OR p.method_details LIKE '%TD%' OR p.method_details LIKE '%Trato%')
    """)
    
    rows_express = db.execute(query_express).fetchall()
    seen_express = set()
    
    for row in rows_express:
        sii_start = _parse_date(row.sii_start_date) # type: ignore
        tender_start = _parse_date(row.tender_start) # type: ignore
        
        if not sii_start or not tender_start: continue
        if tender_start < sii_start: continue # type: ignore
        
        age_months = _months_between(sii_start, tender_start) # type: ignore
        
        # Express rules: < 3 meses -> Critica | < 6 meses -> Alta
        if age_months < 6:
            key = (row.rut, row.ocid)
            if key in seen_express: continue
            seen_express.add(key)
            
            severity = "critica" if age_months < 3 else "alta"
            
            alerts.append({
                "ocid": row.ocid, # type: ignore
                "alert_type": "FANT",
                "severity": severity,
                "title": f"Proveedor Express: Trato Directo a los {age_months:.1f} meses", # type: ignore
                "description": (
                    f"El organismo '{row.buyer_name}' entregó un trato directo por " # type: ignore
                    f"${row.amount:,.0f} CLP al proveedor '{row.supplier_name}' " # type: ignore
                    f"(RUT: {row.rut}) tan solo {age_months:.1f} meses después de haber " # type: ignore
                    f"iniciado actividades en el SII ({sii_start.date()}). Esto levanta "
                    f"altas sospechas de ser una empresa 'de fachada' creada específicamente "
                    f"para adsorber fondos públicos evadiendo libre competencia."
                ),
                "evidence": {
                    "supplier_rut": row.rut, # type: ignore
                    "supplier_name": row.supplier_name, # type: ignore
                    "buyer_name": row.buyer_name, # type: ignore
                    "sii_start_date": str(sii_start.date()),
                    "tender_start": str(tender_start.date()),
                    "age_at_tender_months": round(age_months, 1), # type: ignore
                    "amount": row.amount, # type: ignore
                },
                "buyer_rut": row.buyer_rut, # type: ignore
                "buyer_name": row.buyer_name, # type: ignore
                "supplier_rut": row.rut, # type: ignore
                "supplier_name": row.supplier_name, # type: ignore
                "amount_involved": row.amount, # type: ignore
            })
            
    # --- Estrategia 2: Contrabando de Giros (Mismatch Categoría) ---
    query_mismatch = text("""
        SELECT
            pa.rut,
            pa.name as supplier_name,
            pa.sii_activity_code,
            a.ocid,
            a.amount,
            p.title,
            p.description,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name
        FROM parties pa
        JOIN procurement_parties pp_s ON pp_s.party_rut = pa.rut AND pp_s.role = 'supplier'
        JOIN awards a ON a.ocid = pp_s.procurement_ocid
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pa.sii_activity_code IS NOT NULL
          AND p.title IS NOT NULL
          AND a.amount IS NOT NULL AND a.amount > 0
    """)
    
    rows_mismatch = db.execute(query_mismatch).fetchall()
    seen_mismatch = set()
    
    # Diccionario inverso primitivo para mapear giros ilógicos
    # Ej: Empresa de Eventos ganando construcción, Consultoria ganando Insumos
    mismatch_rules = [
        {"sii": ["evento", "publicidad", "asesorias", "consultoria", "contabilidad", "legal"], 
         "tender": ["tecnologico", "servidor", "construccion", "obra", "medico", "quirurgico", "maquinaria", "camion", "vehiculo"]},
        {"sii": ["construccion", "movimiento de tierra", "ingenieria", "arquitectura"], 
         "tender": ["evento", "catering", "alimentacion", "pasaje", "hotel", "consultoria", "capacitacion"]},
        {"sii": ["limpieza", "aseo", "seguridad", "guardiap"], 
         "tender": ["software", "licencia", "medico", "construccion", "ingenieria"]},
    ]
    
    for row in rows_mismatch:
        sii_giro = str(row.sii_activity_code).lower()
        title_desc = str(row.title + " " + (row.description or "")).lower()
        
        flagged = False
        mismatch_pair: tuple = ("", "")
        
        for rule in mismatch_rules:
            # Si el giro cae en el grupo X
            sii_matches = [kw for kw in rule["sii"] if kw in sii_giro]
            if sii_matches:
                # Y la licitación cae en el opuesto Y
                tender_matches = [kw for kw in rule["tender"] if kw in title_desc]
                if tender_matches:
                    flagged = True
                    mismatch_pair = (sii_matches[0], tender_matches[0])
                    break
        
        if flagged:
            key = (row.rut, row.ocid)
            if key in seen_mismatch: continue
            seen_mismatch.add(key)
            
            alerts.append({
                "ocid": row.ocid, # type: ignore
                "alert_type": "FANT",
                "severity": "media",
                "title": f"Contrabando de Giro: {row.supplier_name}", # type: ignore
                "description": (
                    f"El giro oficial en el SII de la empresa '{row.supplier_name}' es " # type: ignore
                    f"'{row.sii_activity_code}', lo cual sugiere un rubro de '{mismatch_pair[0]}'. " # type: ignore
                    f"Sin embargo, ganó la licitación '{row.title}' por ${row.amount:,.0f} CLP " # type: ignore
                    f"que trata de '{mismatch_pair[1]}'. Esta profunda discrepancia de " # type: ignore
                    f"rubros puede indicar facturas de favor o adjudicaciones arregladas a amigos."
                ),
                "evidence": {
                    "supplier_rut": row.rut, # type: ignore
                    "sii_activity": row.sii_activity_code, # type: ignore
                    "tender_title": row.title, # type: ignore
                    "tender_desc": row.description, # type: ignore
                    "mismatch_detected": f"Giro [{mismatch_pair[0]}] vs Licitación [{mismatch_pair[1]}]",
                    "amount": row.amount, # type: ignore
                },
                "buyer_rut": row.buyer_rut, # type: ignore
                "buyer_name": row.buyer_name, # type: ignore
                "supplier_rut": row.rut, # type: ignore
                "supplier_name": row.supplier_name, # type: ignore
                "amount_involved": row.amount, # type: ignore
            })
            
    logger.info(f"FANT detector: {len(alerts)} alerts generated")
    return alerts
