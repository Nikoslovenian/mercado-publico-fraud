"""
Detector: Coincidencia de Apellidos (PARE)
Detects shared surnames between buyer contacts and supplier contacts/legal names.

Chilean naming convention: NOMBRE(S) APELLIDO_PATERNO APELLIDO_MATERNO
Extract last 2 words as surnames.

Severity:
  - Both surnames match = alta
  - 1 surname matches = media
  - Only for awards > 50 UTM

Excludes very common Chilean surnames to reduce false positives.
Uses unidecode-style normalization for accent handling.
"""
import logging
import unicodedata
import re
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025
MIN_AWARD_AMOUNT = 50 * UTM  # ~3.4M CLP

# Very common Chilean surnames excluded to avoid false positives
COMMON_SURNAMES = {
    "gonzalez", "rodriguez", "munoz", "munoz", "rojas", "diaz",
    "perez", "soto", "contreras", "silva", "martinez", "lopez",
    "hernandez", "garcia", "reyes", "torres", "morales", "sepulveda",
    "araya", "espinoza", "castillo", "tapia", "ramirez", "sanchez",
    "fernandez", "flores", "bravo", "valenzuela", "nunez", "nunez",
    "figueroa", "fuentes", "gutierrez", "alarcon", "vergara",
}


def _normalize_name(name: str) -> str:
    """Remove accents, lowercase, and clean up whitespace."""
    if not name:
        return ""
    # Remove accents using NFKD normalization
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase, collapse whitespace
    return re.sub(r"\s+", " ", ascii_name.lower().strip())


def _extract_surnames(name: str) -> list:
    """
    Extract likely surnames from a Chilean full name.
    Returns list of normalized surnames (last 2 words),
    excluding very short words and common particles.
    """
    normalized = _normalize_name(name)
    if not normalized:
        return []

    # Remove common particles/prefixes
    particles = {"de", "del", "la", "las", "los", "el", "y", "e", "van", "von"}
    parts = [p for p in normalized.split() if p not in particles and len(p) > 1]

    if len(parts) <= 1:
        return []

    # Last 2 parts are typically surnames in Chilean naming
    if len(parts) >= 3:
        return [parts[-2], parts[-1]]
    # 2-part name: last part is likely surname
    return [parts[-1]]


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for surname matches between buyers and suppliers.
    """
    alerts = []

    # Get awards with buyer contact and supplier contact info
    # Join through procurement_parties because awards.supplier_rut uses OCDS IDs
    # while parties.rut uses raw Chilean RUTs
    query = text("""
        SELECT
            a.ocid,
            pp_s.party_rut AS supplier_rut,
            supplier_party.name AS supplier_name,
            a.amount,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            p.title,
            buyer_party.contact_name AS buyer_contact,
            supplier_party.contact_name AS supplier_contact,
            supplier_party.name AS supplier_party_name,
            supplier_party.legal_name AS supplier_legal_name
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = a.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        WHERE a.amount IS NOT NULL
          AND a.amount > :min_amount
          AND buyer_party.contact_name IS NOT NULL
          AND buyer_party.contact_name != ''
    """)

    rows = db.execute(query, {"min_amount": MIN_AWARD_AMOUNT}).fetchall()

    if not rows:
        logger.info("PARE detector: no qualifying awards with buyer contacts found")
        return alerts

    seen = set()  # Deduplicate by (buyer_rut, supplier_rut)

    for row in rows:
        key = (row.buyer_rut, row.supplier_rut)
        if key in seen:
            continue

        buyer_surnames = _extract_surnames(row.buyer_contact)
        if not buyer_surnames:
            continue

        # Check supplier contact name, party name, and legal name
        supplier_names_to_check = []
        if row.supplier_contact:
            supplier_names_to_check.append(("contacto", row.supplier_contact))
        if row.supplier_party_name:
            supplier_names_to_check.append(("nombre", row.supplier_party_name))
        if row.supplier_legal_name:
            supplier_names_to_check.append(("razon social", row.supplier_legal_name))

        best_match = None
        best_shared = []
        best_source = ""

        for source_label, supplier_name in supplier_names_to_check:
            supplier_surnames = _extract_surnames(supplier_name)
            if not supplier_surnames:
                continue

            # Find shared surnames (excluding common ones)
            shared = []
            for bs in buyer_surnames:
                for ss in supplier_surnames:
                    if bs == ss and bs not in COMMON_SURNAMES:
                        shared.append(bs)

            if len(shared) > len(best_shared):
                best_shared = shared
                best_match = supplier_name
                best_source = source_label

        if not best_shared:
            continue

        seen.add(key)

        # Determine severity
        if len(best_shared) >= 2:
            severity = "alta"
            match_desc = "AMBOS apellidos"
        else:
            severity = "media"
            match_desc = "un apellido"

        shared_str = ", ".join(best_shared)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "PARE",
            "severity": severity,
            "title": (
                f"Apellido compartido entre comprador y proveedor: "
                f"{shared_str.upper()}"
            ),
            "description": (
                f"El contacto del organismo comprador {row.buyer_name or row.buyer_rut} "
                f"({row.buyer_contact}) comparte {match_desc} ({shared_str}) con "
                f"el {best_source} del proveedor {row.supplier_name or row.supplier_rut} "
                f"({best_match}). Monto adjudicado: ${row.amount:,.0f} CLP. "
                f"La coincidencia de apellidos puede indicar relacion familiar "
                f"entre funcionarios del organismo comprador y el proveedor, "
                f"lo que constituye un potencial conflicto de interes."
            ),
            "evidence": {
                "ocid": row.ocid,
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
                "buyer_contact": row.buyer_contact,
                "buyer_surnames": buyer_surnames,
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "supplier_match_source": best_source,
                "supplier_match_name": best_match,
                "supplier_surnames": _extract_surnames(best_match),
                "shared_surnames": best_shared,
                "both_surnames_match": len(best_shared) >= 2,
                "award_amount": row.amount,
                "common_surnames_excluded": list(COMMON_SURNAMES),
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": row.region,
            "amount_involved": row.amount,
        })

    logger.info(f"PARE detector: {len(alerts)} alerts generated")
    return alerts
