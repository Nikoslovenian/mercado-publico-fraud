"""
Loader: inserts parsed OCDS records into the SQLite database.
Uses bulk inserts and upserts for efficiency.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import Procurement, Party, ProcurementParty, Bid, Award, Item

logger = logging.getLogger(__name__)


def upsert_procurement(db: Session, data: dict) -> bool:
    """Insert or update a procurement record. Returns True if new."""
    existing = db.get(Procurement, data["ocid"])
    if existing:
        return False
    proc = Procurement(**{k: v for k, v in data.items()})
    db.add(proc)
    return True


def upsert_party(db: Session, data: dict) -> None:
    """Insert party if not exists, update contact info if it has more detail."""
    rut = data["rut"]
    roles = data.pop("roles", [])

    existing = db.get(Party, rut)
    if not existing:
        party = Party(**{k: v for k, v in data.items()})
        db.add(party)
    else:
        # Update if we have more info
        if data.get("name") and not existing.name:
            existing.name = data["name"]
        if data.get("address") and not existing.address:
            existing.address = data["address"]
        if data.get("phone") and not existing.phone:
            existing.phone = data["phone"]
        if data.get("email") and not existing.email:
            existing.email = data["email"]
        if data.get("contact_name") and not existing.contact_name:
            existing.contact_name = data["contact_name"]
    return roles


def load_parsed_records(db: Session, records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Load a batch of parsed OCDS records into the database."""
    stats = {"procurements": 0, "parties": 0, "bids": 0, "awards": 0, "items": 0}

    for record in records:
        if not record:
            continue

        # --- Procurement ---
        proc_data = record.get("procurement", {})
        if not proc_data or not proc_data.get("ocid"):
            continue

        ocid = proc_data["ocid"]
        is_new = upsert_procurement(db, proc_data.copy())
        if is_new:
            stats["procurements"] += 1

        # --- Parties ---
        party_roles_map = {}  # rut → roles
        for party_data in record.get("parties", []):
            rut = party_data.get("rut")
            if not rut:
                continue
            data_copy = party_data.copy()
            roles = upsert_party(db, data_copy)
            party_roles_map[rut] = roles
            stats["parties"] += 1

        # Flush parties before creating relationships
        try:
            db.flush()
        except Exception:
            db.rollback()
            continue

        # --- ProcurementParty relationships ---
        for rut, roles in party_roles_map.items():
            for role in roles:
                existing_rel = db.query(ProcurementParty).filter_by(
                    procurement_ocid=ocid, party_rut=rut, role=role
                ).first()
                if not existing_rel:
                    rel = ProcurementParty(procurement_ocid=ocid, party_rut=rut, role=role)
                    db.add(rel)

        # --- Bids ---
        for bid_data in record.get("bids", []):
            if not bid_data.get("id"):
                continue
            if not db.get(Bid, bid_data["id"]):
                db.add(Bid(**bid_data))
                stats["bids"] += 1

        # --- Awards ---
        for award_data in record.get("awards", []):
            if not award_data.get("id"):
                continue
            if not db.get(Award, award_data["id"]):
                db.add(Award(**award_data))
                stats["awards"] += 1

        # --- Items ---
        for item_data in record.get("items", []):
            if not item_data.get("id"):
                continue
            if not db.get(Item, item_data["id"]):
                db.add(Item(**item_data))
                stats["items"] += 1

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        db.rollback()

    return stats
