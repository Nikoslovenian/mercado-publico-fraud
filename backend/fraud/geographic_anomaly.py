"""
Detector: Anomalia Geografica (GEOG)
Detects suppliers winning contracts far from their registered region.

Uses a simple distance matrix based on Chilean regions ordered from north to south.
Compares the supplier's registered region (parties.region) with the procurement
region (procurements.region) through awards.

Thresholds:
  - Distance >= 8 regions apart and award > 200 UTM = alta
  - Distance >= 8 regions apart and award > 50 UTM = media
  - Distance >= 5 regions apart and award > 200 UTM = media
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

UTM = 67294  # CLP per UTM unit in 2025
THRESHOLD_ALTA = 200 * UTM     # ~13.5M CLP
THRESHOLD_MEDIA = 50 * UTM     # ~3.4M CLP
DIST_FAR = 8                   # Regions apart to consider "far"
DIST_MODERATE = 5              # Regions apart for moderate distance

# Chilean regions ordered from north to south
# Index position represents geographic order
REGION_ORDER = {
    "arica y parinacota": 0,
    "arica": 0,
    "tarapaca": 1,
    "antofagasta": 2,
    "atacama": 3,
    "coquimbo": 4,
    "valparaiso": 5,
    "metropolitana": 6,
    "metropolitana de santiago": 6,
    "region metropolitana": 6,
    "santiago": 6,
    "ohiggins": 7,
    "o'higgins": 7,
    "libertador general bernardo o'higgins": 7,
    "maule": 8,
    "nuble": 9,
    "biobio": 10,
    "bio-bio": 10,
    "bio bio": 10,
    "araucania": 11,
    "la araucania": 11,
    "los rios": 12,
    "los lagos": 13,
    "aysen": 14,
    "aisen": 14,
    "aysen del general carlos ibanez del campo": 14,
    "magallanes": 15,
    "magallanes y de la antartica chilena": 15,
}


def _normalize_region(region: str) -> str:
    """Normalize region name for lookup."""
    if not region:
        return ""
    import unicodedata
    # Remove accents
    nfkd = unicodedata.normalize("NFKD", region)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase and strip
    normalized = ascii_name.lower().strip()
    # Remove common prefixes
    for prefix in ("region de ", "region del ", "region ", "de "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return normalized.strip()


def _get_region_index(region: str) -> int:
    """Get the north-to-south index for a region. Returns -1 if not found."""
    normalized = _normalize_region(region)
    if not normalized:
        return -1

    # Direct lookup
    if normalized in REGION_ORDER:
        return REGION_ORDER[normalized]

    # Fuzzy match: check if any key is contained in the region or vice versa
    for key, idx in REGION_ORDER.items():
        if key in normalized or normalized in key:
            return idx

    return -1


def _region_distance(region1: str, region2: str) -> int:
    """
    Calculate the geographic distance between two regions.
    Returns the absolute difference in north-south index.
    Returns -1 if either region cannot be resolved.
    """
    idx1 = _get_region_index(region1)
    idx2 = _get_region_index(region2)
    if idx1 < 0 or idx2 < 0:
        return -1
    return abs(idx1 - idx2)


def detect(db: Session) -> list[dict]:
    """
    Returns list of alert dicts for geographic anomalies.
    Flags suppliers winning contracts in regions far from their registered location.
    """
    alerts = []

    query = text("""
        SELECT
            a.ocid,
            pp_s.party_rut AS supplier_rut,
            pa.name AS supplier_name,
            a.amount,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region AS procurement_region,
            p.title,
            pa.region AS supplier_region
        FROM awards a
        JOIN procurements p ON p.ocid = a.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties pa ON pa.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE a.amount IS NOT NULL
          AND a.amount > 0
          AND p.region IS NOT NULL
          AND p.region != ''
          AND pa.region IS NOT NULL
          AND pa.region != ''
    """)

    rows = db.execute(query).fetchall()

    if not rows:
        logger.info("GEOG detector: no qualifying awards found")
        return alerts

    seen = set()  # Deduplicate by (ocid, supplier_rut)

    for row in rows:
        key = (row.ocid, row.supplier_rut)
        if key in seen:
            continue

        proc_region = row.procurement_region
        supp_region = row.supplier_region

        # Skip if regions are the same (normalized)
        if _normalize_region(proc_region) == _normalize_region(supp_region):
            continue

        distance = _region_distance(proc_region, supp_region)
        if distance < 0:
            continue  # Could not resolve one or both regions

        amount = row.amount or 0

        severity = None
        if distance >= DIST_FAR and amount >= THRESHOLD_ALTA:
            severity = "alta"
        elif distance >= DIST_FAR and amount >= THRESHOLD_MEDIA:
            severity = "media"
        elif distance >= DIST_MODERATE and amount >= THRESHOLD_ALTA:
            severity = "media"
        else:
            continue

        seen.add(key)

        alerts.append({
            "ocid": row.ocid,
            "alert_type": "GEOG",
            "severity": severity,
            "title": (
                f"Anomalia geografica: proveedor de {supp_region} "
                f"gana en {proc_region}"
            ),
            "description": (
                f"El proveedor {row.supplier_name or row.supplier_rut} "
                f"(RUT: {row.supplier_rut}), registrado en la region de "
                f"{supp_region}, gano un contrato en la region de "
                f"{proc_region} por ${amount:,.0f} CLP. "
                f"Las regiones estan separadas por {distance} posiciones "
                f"en el eje norte-sur. "
                f"Licitacion: '{row.title[:80] if row.title else row.ocid}'. "
                f"Contratos adjudicados a proveedores lejanos de la zona de "
                f"ejecucion pueden indicar favoritismo o falta de competencia local."
            ),
            "evidence": {
                "ocid": row.ocid,
                "supplier_rut": row.supplier_rut,
                "supplier_name": row.supplier_name,
                "supplier_region": supp_region,
                "procurement_region": proc_region,
                "region_distance": distance,
                "award_amount": amount,
                "buyer_rut": row.buyer_rut,
                "buyer_name": row.buyer_name,
            },
            "buyer_rut": row.buyer_rut,
            "buyer_name": row.buyer_name,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "region": proc_region,
            "amount_involved": amount,
        })

    logger.info(f"GEOG detector: {len(alerts)} alerts generated")
    return alerts
