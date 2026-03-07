"""
Parser: reads OCDS JSON files and extracts normalized records.
Handles malformed files gracefully.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

UTM_VALUE_CLP = 67294  # Approximate UTM value in CLP for 2025


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _get_rut(identifier: dict) -> Optional[str]:
    """Extract RUT from an identifier dict, normalizing format."""
    if not identifier:
        return None
    rut = identifier.get("id") or identifier.get("legalId")
    if rut:
        return str(rut).strip().replace(".", "").replace("-", "").upper()
    return None


def _get_party_rut(party: dict) -> Optional[str]:
    """Extract RUT from a party dict."""
    ident = party.get("identifier") or {}
    rut = _get_rut(ident)
    if not rut:
        # Try additionalIdentifiers
        for add_ident in party.get("additionalIdentifiers", []):
            rut = _get_rut(add_ident)
            if rut:
                break
    if not rut:
        rut = party.get("id", "").strip()
    return rut if rut else None


def parse_ocds_file(json_path: Path) -> Optional[dict]:
    """
    Parse a single OCDS JSON file and return a normalized dict with keys:
    procurement, parties, bids, awards, items
    Returns None if the file is invalid or empty.
    """
    try:
        with open(json_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as e:
        logger.debug(f"Cannot read {json_path.name}: {e}")
        return None

    records = data.get("records", [])
    if not records:
        return None

    results = []
    for record in records:
        release = record.get("compiledRelease", {})
        if not release:
            continue

        parsed = _parse_release(release, json_path.name)
        if parsed:
            results.append(parsed)

    return results if results else None


def _parse_release(release: dict, filename: str) -> Optional[dict]:
    ocid = release.get("ocid", "").strip()
    if not ocid:
        return None

    tender = release.get("tender", {}) or {}
    buyer = release.get("buyer", {}) or {}
    parties_raw = release.get("parties", []) or []
    bids_raw = (release.get("bids") or {}).get("details", []) or []
    awards_raw = release.get("awards", []) or []

    # --- Buyer ---
    buyer_rut = _get_party_rut(buyer)
    buyer_name = buyer.get("name", "")

    # --- Procurement ---
    tender_period = tender.get("tenderPeriod") or {}
    award_period = tender.get("awardPeriod") or {}

    # Get region from buyer or procuring entity party
    region = ""
    for p in parties_raw:
        if "buyer" in p.get("roles", []) or "procuringEntity" in p.get("roles", []):
            region = (p.get("address") or {}).get("region", "")
            if region:
                break

    # Determine award date and total amount from awards
    award_date = None
    total_amount = None
    for award in awards_raw:
        d = _parse_date(award.get("date"))
        if d and (award_date is None or d < award_date):
            award_date = d
        v = (award.get("value") or {}).get("amount")
        if v:
            total_amount = (total_amount or 0) + _safe_float(v)

    procurement = {
        "ocid": ocid,
        "buyer_rut": buyer_rut,
        "buyer_name": buyer_name,
        "region": region,
        "title": tender.get("title", ""),
        "description": tender.get("description", ""),
        "method": tender.get("procurementMethod", ""),
        "method_details": tender.get("procurementMethodDetails", ""),
        "tender_start": _parse_date(tender_period.get("startDate")),
        "tender_end": _parse_date(tender_period.get("endDate")),
        "award_date": award_date,
        "status": tender.get("status", ""),
        "total_amount": total_amount,
        "currency": "CLP",
        "year": None,
        "month": None,
        "raw_file": filename,
    }

    # Set year/month from tender_start or award_date
    ref_date = procurement["tender_start"] or procurement["award_date"]
    if ref_date:
        procurement["year"] = ref_date.year
        procurement["month"] = ref_date.month

    # --- Parties ---
    parties = []
    for p in parties_raw:
        rut = _get_party_rut(p)
        if not rut:
            continue
        ident = p.get("identifier") or {}
        address = p.get("address") or {}
        contact = p.get("contactPoint") or {}
        parties.append({
            "rut": rut,
            "name": p.get("name", ""),
            "legal_name": ident.get("legalName", ""),
            "address": address.get("streetAddress", ""),
            "region": address.get("region", ""),
            "phone": contact.get("telephone", ""),
            "email": contact.get("email", ""),
            "contact_name": contact.get("name", ""),
            "roles": p.get("roles", []),
        })

    # --- Bids ---
    bids = []
    for i, bid in enumerate(bids_raw):
        bid_id = bid.get("id") or f"{ocid}-bid-{i}"
        tenderers = bid.get("tenderers", []) or []
        supplier_rut = None
        supplier_name = ""
        if tenderers:
            t = tenderers[0]
            supplier_rut = _get_party_rut(t)
            supplier_name = t.get("name", "")
        value = bid.get("value") or {}
        bids.append({
            "id": f"{ocid}-{bid_id}",
            "ocid": ocid,
            "supplier_rut": supplier_rut,
            "supplier_name": supplier_name,
            "amount": _safe_float(value.get("amount")),
            "currency": value.get("currency", "CLP"),
            "date": _parse_date(bid.get("date")),
            "status": bid.get("status", ""),
        })

    # --- Awards ---
    awards = []
    for award in awards_raw:
        award_id = award.get("id") or f"{ocid}-award"
        suppliers = award.get("suppliers", []) or []
        supplier_rut = None
        supplier_name = ""
        if suppliers:
            s = suppliers[0]
            supplier_rut = _get_party_rut(s)
            supplier_name = s.get("name", "")
        value = award.get("value") or {}
        awards.append({
            "id": f"{ocid}-{award_id}",
            "ocid": ocid,
            "supplier_rut": supplier_rut,
            "supplier_name": supplier_name,
            "amount": _safe_float(value.get("amount")),
            "currency": value.get("currency", "CLP"),
            "date": _parse_date(award.get("date")),
            "status": award.get("status", ""),
            "items_raw": award.get("items", []),
        })

    # --- Items (from awards, prefer award items which have unit prices) ---
    items = []
    item_counter = 0
    for award in awards:
        award_id = award["id"]
        for item in award.get("items_raw", []):
            item_counter += 1
            classification = item.get("classification") or {}
            unit = item.get("unit") or {}
            # Unit price is in unit.value.amount (ChileCompra OCDS format)
            unit_price_val = (unit.get("value") or {}).get("amount")
            quantity = _safe_float(item.get("quantity"))
            unit_price = _safe_float(unit_price_val)
            total = None
            if unit_price and quantity:
                total = unit_price * quantity
            unspsc = classification.get("id", "")
            items.append({
                "id": f"{ocid}-item-{item_counter}",
                "ocid": ocid,
                "award_id": award_id,
                "unspsc_code": unspsc,
                "unspsc_prefix": unspsc[:4] if len(unspsc) >= 4 else unspsc,
                "description": item.get("description", ""),
                "quantity": quantity,
                "unit": unit.get("name", ""),
                "unit_price": unit_price,
                "total_price": total,
            })

    # Also add items from tender if not present in awards
    if not items:
        for item in tender.get("items", []):
            item_counter += 1
            classification = item.get("classification") or {}
            unit = item.get("unit") or {}
            quantity = _safe_float(item.get("quantity"))
            unspsc = classification.get("id", "")
            items.append({
                "id": f"{ocid}-item-{item_counter}",
                "ocid": ocid,
                "award_id": None,
                "unspsc_code": unspsc,
                "unspsc_prefix": unspsc[:4] if len(unspsc) >= 4 else unspsc,
                "description": item.get("description", ""),
                "quantity": quantity,
                "unit": unit.get("name", ""),
                "unit_price": None,
                "total_price": None,
            })

    # Clean up awards (remove items_raw)
    for award in awards:
        award.pop("items_raw", None)

    return {
        "procurement": procurement,
        "parties": parties,
        "bids": bids,
        "awards": awards,
        "items": items,
    }
