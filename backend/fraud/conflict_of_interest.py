"""
Detector: Conflicto de Interes (CONF)
Detecta posibles conflictos de interes entre proveedores y funcionarios
publicos del organismo comprador.

Estrategias:
  1. Cruzar nombre de contacto del proveedor con funcionarios del organismo
  2. Detectar proveedores persona natural que son funcionarios publicos
  3. Coincidencia de apellidos entre contacto del proveedor y personal comprador
"""
import logging
import unicodedata
import re
from collections import defaultdict
from sqlalchemy.orm import Session  # type: ignore
from sqlalchemy import text  # type: ignore

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize name for comparison: remove accents, lowercase, strip."""
    if not name:
        return ""
    # Remove accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase, strip extra whitespace
    return re.sub(r"\s+", " ", ascii_name.lower().strip())


def _extract_surnames(name: str) -> set:
    """Extract likely surnames from a full name."""
    normalized = _normalize_name(name)
    if not normalized:
        return set()
    parts = normalized.split()
    if len(parts) <= 1:
        return set()
    # In Chilean naming: NOMBRE(S) APELLIDO_PATERNO APELLIDO_MATERNO
    # Last two parts are typically surnames
    if len(parts) >= 3:
        return {parts[-2], parts[-1]}
    return {parts[-1]}


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for potential conflicts of interest.
    """
    alerts = []

    # --- Strategy 1: Suppliers flagged as public employees ---
    query_employees = text("""
        SELECT
            pa.rut,
            pa.name,
            pa.contact_name,
            pa.is_public_employee,
            pa.public_employee_org,
            a.ocid,
            a.amount,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title
        FROM parties pa
        JOIN procurement_parties pp_s ON pp_s.party_rut = pa.rut AND pp_s.role = 'supplier'
        JOIN awards a ON a.ocid = pp_s.procurement_ocid
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = a.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pa.is_public_employee = 1
          AND a.amount IS NOT NULL
          AND a.amount > 0
    """)

    rows = db.execute(query_employees).fetchall()
    seen_conflicts = set()

    for row in rows:
        key = (row.rut, row.buyer_rut)
        if key in seen_conflicts:
            continue
        seen_conflicts.add(key)

        # Check if the employee works at the buyer organization
        same_org = False
        if row.public_employee_org and row.buyer_name:
            org_norm = _normalize_name(row.public_employee_org)
            buyer_norm = _normalize_name(row.buyer_name)
            # Fuzzy match: check if significant words overlap
            org_words = set(org_norm.split()) - {"de", "del", "la", "el", "y", "los", "las"}
            buyer_words = set(buyer_norm.split()) - {"de", "del", "la", "el", "y", "los", "las"}
            overlap = org_words & buyer_words
            same_org = len(overlap) >= 2 or (len(overlap) >= 1 and len(org_words) <= 3)

        severity = "alta" if same_org else "media"

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "CONF",
            "severity": severity,
            "title": f"Posible conflicto de interes: {row.name or row.rut}",
            "description": (
                f"El proveedor {row.name or row.rut} (RUT: {row.rut}) esta registrado "
                f"como funcionario publico en {row.public_employee_org or 'organismo desconocido'} "
                f"y recibio contratos del organismo {row.buyer_name or row.buyer_rut} "
                f"por ${row.amount:,.0f} CLP. "
                + (
                    "El proveedor trabaja en el MISMO organismo comprador, lo que constituye "
                    "un conflicto de interes directo."
                    if same_org else
                    "Aunque trabaja en un organismo diferente, un funcionario publico "
                    "que provee servicios al Estado requiere investigacion adicional."
                )
            ),
            "evidence": {
                "supplier_rut": row.rut,
                "supplier_name": row.name,
                "public_employee_org": row.public_employee_org,
                "buyer_name": row.buyer_name,
                "buyer_rut": row.buyer_rut,
                "same_organization": same_org,
                "award_amount": row.amount,
                "ocid": row.ocid,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.rut,
            "supplier_name": row.name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    # --- Strategy 2: Supplier contact name matches buyer contact ---
    # Cross-reference supplier contact_name with buyer's contact person
    query_contacts = text("""
        SELECT
            pp_s.party_rut AS supplier_rut,
            supplier.name AS supplier_name,
            supplier.contact_name AS supplier_contact,
            pp_b.party_rut AS buyer_rut,
            buyer.name AS buyer_name,
            buyer.contact_name AS buyer_contact,
            a.ocid,
            a.amount,
            p.region,
            p.title
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier ON supplier.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = a.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer ON buyer.rut = pp_b.party_rut
        WHERE supplier.contact_name IS NOT NULL
          AND supplier.contact_name != ''
          AND buyer.contact_name IS NOT NULL
          AND buyer.contact_name != ''
          AND a.amount IS NOT NULL
          AND a.amount > 0
    """)

    rows2 = db.execute(query_contacts).fetchall()

    for row in rows2:
        key = (row.supplier_rut, row.buyer_rut)
        if key in seen_conflicts:
            continue

        supplier_surnames = _extract_surnames(row.supplier_contact)
        buyer_surnames = _extract_surnames(row.buyer_contact)

        if not supplier_surnames or not buyer_surnames:
            continue

        shared_surnames = supplier_surnames & buyer_surnames
        if not shared_surnames:
            continue

        # Full name match = alta, surname match = media
        supplier_norm = _normalize_name(row.supplier_contact)
        buyer_norm = _normalize_name(row.buyer_contact)
        full_match = supplier_norm == buyer_norm

        severity = "alta" if full_match else "media"
        seen_conflicts.add(key)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "CONF",
            "severity": severity,
            "title": (
                f"Contacto del proveedor coincide con contacto del organismo: "
                f"{row.supplier_contact}"
            ),
            "description": (
                f"El contacto del proveedor {row.supplier_name or row.supplier_rut} "
                f"({row.supplier_contact}) comparte "
                + ("nombre completo" if full_match else f"apellido(s) ({', '.join(shared_surnames)})")
                + f" con el contacto del organismo comprador {row.buyer_name or row.buyer_rut} "
                f"({row.buyer_contact}). Monto adjudicado: ${row.amount:,.0f} CLP. "
                f"Esto sugiere una posible relacion familiar o personal entre el "
                f"proveedor y un funcionario del organismo comprador."
            ),
            "evidence": {
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "supplier_contact": row.supplier_contact,
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "buyer_contact": row.buyer_contact,
                "shared_surnames": list(shared_surnames),
                "full_name_match": full_match,
                "award_amount": row.amount,
                "ocid": row.ocid,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    # --- Strategy 3: Natural person supplier = same name as buyer party contact ---
    query_natural = text("""
        SELECT
            pp_s.party_rut AS supplier_rut,
            supplier.name AS supplier_name,
            supplier.party_type,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            buyer_party.contact_name AS buyer_contact,
            a.ocid,
            a.amount,
            p.region
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier ON supplier.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = a.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE supplier.party_type = 'natural'
          AND a.amount IS NOT NULL
          AND a.amount > 0
          AND buyer_party.contact_name IS NOT NULL
          AND buyer_party.contact_name != ''
    """)

    rows3 = db.execute(query_natural).fetchall()

    for row in rows3:
        key = (row.supplier_rut, row.buyer_rut)
        if key in seen_conflicts:
            continue

        supplier_surnames = _extract_surnames(row.supplier_name)
        buyer_surnames = _extract_surnames(row.buyer_contact)

        if not supplier_surnames or not buyer_surnames:
            continue

        shared = supplier_surnames & buyer_surnames
        if not shared:
            continue

        seen_conflicts.add(key)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "CONF",
            "severity": "media",
            "title": f"Proveedor persona natural comparte apellido con funcionario: {row.supplier_name}",
            "description": (
                f"El proveedor persona natural {row.supplier_name} "
                f"(RUT: {row.supplier_rut}) comparte apellido(s) "
                f"({', '.join(shared)}) con el contacto {row.buyer_contact} "
                f"del organismo {row.buyer_name or row.buyer_rut}. "
                f"Monto: ${row.amount:,.0f} CLP. "
                f"Proveedores persona natural con relacion familiar con "
                f"funcionarios del organismo comprador constituyen un riesgo "
                f"de conflicto de interes."
            ),
            "evidence": {
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "supplier_type": "natural",
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "buyer_contact": row.buyer_contact,
                "shared_surnames": list(shared),
                "award_amount": row.amount,
                "ocid": row.ocid,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    # --- Strategy 4: Shareholders/Reps (RES) matching Buyer Contact ---
    query_soc = text("SELECT rut, raw_data FROM external_data WHERE source = 'registro_sociedades'")
    soc_rows = db.execute(query_soc).fetchall()
    
    soc_data = {}
    import json
    for r in soc_rows:
        try:
            raw = json.loads(r.raw_data) if isinstance(r.raw_data, str) else r.raw_data
            if raw: soc_data[r.rut] = raw
        except:
            pass

    if soc_data:
        # Cross reference Awards Buyer Contacts with the Real Shareholders
        seen_soc = set()
        for row in rows2:
            key = (row.supplier_rut, row.buyer_rut)
            if key in seen_soc: continue
            
            s_data = soc_data.get(row.supplier_rut)
            if not isinstance(s_data, dict): continue
            
            socios = s_data.get("socios", []) + s_data.get("representantes_legales", [])
            buyer_surnames = _extract_surnames(row.buyer_contact)
            
            if not buyer_surnames or not socios: continue
            
            for socio in socios:
                socio_surnames = _extract_surnames(socio)
                shared_surnames = socio_surnames & buyer_surnames
                
                if shared_surnames:
                    seen_soc.add(key)
                    # We might have caught it in Strategy 2, but if the Contact Name didn't match
                    # but the *Socio's* name matched, we alert it with CRITICA severity.
                    alerts.append({
                        "ocid": row.ocid,
                        "alert_type": "CONF",
                        "severity": "critica",
                        "title": f"Malla Societaria / Socio comparte apellido con Funcionario ({', '.join(shared_surnames)})",
                        "description": (
                            f"Al analizar la Malla Societaria del proveedor {row.supplier_name} "
                            f"(RUT: {row.supplier_rut}) a través del Registro de Empresas, descubrimos "
                            f"que el socio/representante '{socio}' comparte familiaridad/apellidos "
                            f"({', '.join(shared_surnames)}) con el funcionario a cargo del organismo "
                            f"{row.buyer_name}: {row.buyer_contact}. "
                            f"Monto: ${row.amount:,.0f} CLP. Esto es un conflicto de interés indirecto grave."
                        ),
                        "evidence": {
                            "supplier_rut": row.supplier_rut,
                            "supplier_name": row.supplier_name,
                            "socio_name": socio,
                            "buyer_name": row.buyer_name,
                            "buyer_contact": row.buyer_contact,
                            "shared_surnames": list(shared_surnames),
                            "award_amount": row.amount,
                            "ocid": row.ocid,
                        },
                        "buyer_rut": row.buyer_rut,
                        "buyer_name": row.buyer_name,
                        "supplier_rut": row.supplier_rut,
                        "supplier_name": row.supplier_name,
                        "region": row.region,
                        "amount_involved": row.amount,
                    })
                    break

    logger.info(f"CONF detector: {len(alerts)} alerts generated")
    return alerts
