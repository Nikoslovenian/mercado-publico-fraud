"""
Detector: Proveedores Relacionados (RELA)
Flags suppliers that share addresses, phone numbers, or contact persons,
especially when they appear in the same tender as competitors.
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_SHARED_RELATIONS = 1   # Just 1 shared procurement is enough if data quality confirms it


def _normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, and country code for comparison."""
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit())[-9:]  # Last 9 digits


def _normalize_address(addr: str) -> str:
    """Normalize address for fuzzy comparison."""
    if not addr:
        return ""
    return " ".join(addr.lower().split())


def detect(db: Session) -> list[dict]:
    alerts = []

    # Get all parties with contact info (suppliers only)
    query = text("""
        SELECT DISTINCT
            pa.rut,
            pa.name,
            pa.address,
            pa.phone,
            pa.contact_name,
            pa.region
        FROM parties pa
        JOIN procurement_parties pp ON pp.party_rut = pa.rut
        WHERE pp.role IN ('supplier', 'tenderer')
          AND pa.rut IS NOT NULL
    """)

    suppliers = db.execute(query).fetchall()

    # Index by normalized fields
    by_address = defaultdict(list)   # normalized_address → list of suppliers
    by_phone = defaultdict(list)     # normalized_phone → list of suppliers
    by_contact = defaultdict(list)   # contact_name → list of suppliers

    for s in suppliers:
        addr = _normalize_address(s.address)
        phone = _normalize_phone(s.phone)
        contact = (s.contact_name or "").strip().lower()

        if addr and len(addr) > 10:  # Avoid matching very short addresses
            by_address[addr].append(s)
        if phone and len(phone) >= 8:
            by_phone[phone].append(s)
        if contact and len(contact) > 5:  # Avoid matching very short names
            by_contact[contact].append(s)

    # Find groups of related suppliers
    related_groups = {}  # (rut1, rut2) → relationship type + data

    def add_relation(rut1, rut2, name1, name2, rel_type, shared_value):
        key = (min(rut1, rut2), max(rut1, rut2))
        if key not in related_groups:
            related_groups[key] = {
                "rut1": rut1, "name1": name1,
                "rut2": rut2, "name2": name2,
                "relations": [],
            }
        related_groups[key]["relations"].append({
            "type": rel_type,
            "value": shared_value,
        })

    for addr, group in by_address.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                s1, s2 = group[i], group[j]
                if s1.rut == s2.rut:
                    continue
                add_relation(s1.rut, s2.rut, s1.name, s2.name, "dirección", addr)

    for phone, group in by_phone.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                s1, s2 = group[i], group[j]
                if s1.rut == s2.rut:
                    continue
                add_relation(s1.rut, s2.rut, s1.name, s2.name, "teléfono", phone)

    for contact, group in by_contact.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                s1, s2 = group[i], group[j]
                if s1.rut == s2.rut:
                    continue
                add_relation(s1.rut, s2.rut, s1.name, s2.name, "contacto", contact)

    if not related_groups:
        return alerts

    # For each related pair, check if they competed in the same tenders
    # Build map of rut → set of ocids they participated in
    ocid_query = text("""
        SELECT party_rut, procurement_ocid
        FROM procurement_parties
        WHERE role IN ('supplier', 'tenderer')
    """)
    ocid_rows = db.execute(ocid_query).fetchall()

    rut_to_ocids = defaultdict(set)
    for row in ocid_rows:
        rut_to_ocids[row.party_rut].add(row.procurement_ocid)

    for (rut1, rut2), rel_data in related_groups.items():
        ocids1 = rut_to_ocids.get(rut1, set())
        ocids2 = rut_to_ocids.get(rut2, set())
        shared_ocids = ocids1 & ocids2

        relation_types = [r["type"] for r in rel_data["relations"]]
        rel_summary = ", ".join(set(relation_types))

        # Severity: higher if they competed in same tenders
        if shared_ocids:
            severity = "alta"
            description = (
                f"Los proveedores {rel_data['name1'] or rut1} (RUT: {rut1}) y "
                f"{rel_data['name2'] or rut2} (RUT: {rut2}) comparten {rel_summary} "
                f"y participaron juntos en {len(shared_ocids)} licitación(es). "
                f"Proveedores relacionados que compiten en el mismo proceso constituyen "
                f"un serio riesgo de colusión o competencia ficticia."
            )
        else:
            severity = "media"
            description = (
                f"Los proveedores {rel_data['name1'] or rut1} (RUT: {rut1}) y "
                f"{rel_data['name2'] or rut2} (RUT: {rut2}) comparten {rel_summary}. "
                f"Esta relación podría indicar empresas relacionadas o personas vinculadas "
                f"que participan en distintos procesos de compra pública."
            )

        sample_ocid = next(iter(shared_ocids), None)

        alerts.append({
            "ocid": sample_ocid,
            "alert_type": "RELA",
            "severity": severity,
            "title": f"Proveedores relacionados: {rel_data['name1'] or rut1} y {rel_data['name2'] or rut2}",
            "description": description,
            "evidence": {
                "rut1": rut1,
                "name1": rel_data["name1"],
                "rut2": rut2,
                "name2": rel_data["name2"],
                "shared_attributes": rel_data["relations"],
                "shared_procurement_count": len(shared_ocids),
                "shared_ocids": list(shared_ocids)[:10],
            },
            "buyer_rut": None,
            "buyer_name": None,
            "supplier_rut": rut1,
            "supplier_name": rel_data["name1"],
            "region": None,
            "amount_involved": None,
        })

    logger.info(f"RELA detector: {len(alerts)} alerts generated")
    return alerts
