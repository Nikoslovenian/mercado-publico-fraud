"""
Procurements API routes.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, Procurement, Alert, Bid, Award, Item

router = APIRouter(prefix="/api/procurements", tags=["procurements"])


def procurement_to_dict(p: Procurement) -> dict:
    return {
        "ocid": p.ocid,
        "buyer_rut": p.buyer_rut,
        "buyer_name": p.buyer_name,
        "region": p.region,
        "title": p.title,
        "description": p.description,
        "method": p.method,
        "method_details": p.method_details,
        "tender_start": p.tender_start.isoformat() if p.tender_start else None,
        "tender_end": p.tender_end.isoformat() if p.tender_end else None,
        "award_date": p.award_date.isoformat() if p.award_date else None,
        "status": p.status,
        "total_amount": p.total_amount,
        "currency": p.currency,
        "year": p.year,
        "month": p.month,
    }


@router.get("")
def list_procurements(
    q: str = Query(None),
    region: str = Query(None),
    buyer_rut: str = Query(None),
    method: str = Query(None),
    year: int = Query(None),
    status: str = Query(None),
    has_alerts: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Search and list procurements."""
    query = db.query(Procurement)

    if q:
        query = query.filter(
            Procurement.title.ilike(f"%{q}%") |
            Procurement.description.ilike(f"%{q}%") |
            Procurement.ocid.ilike(f"%{q}%")
        )
    if region:
        query = query.filter(Procurement.region.ilike(f"%{region}%"))
    if buyer_rut:
        query = query.filter(Procurement.buyer_rut == buyer_rut)
    if method:
        query = query.filter(Procurement.method_details.ilike(f"%{method}%"))
    if year:
        query = query.filter(Procurement.year == year)
    if status:
        query = query.filter(Procurement.status == status)
    if has_alerts is True:
        alert_ocids = db.execute(text("SELECT DISTINCT ocid FROM alerts WHERE ocid IS NOT NULL")).scalars().all()
        query = query.filter(Procurement.ocid.in_(alert_ocids))

    total = query.count()
    items = (
        query
        .order_by(Procurement.tender_start.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [procurement_to_dict(p) for p in items],
    }


@router.get("/{ocid}")
def get_procurement(ocid: str, db: Session = Depends(get_db)):
    """Get full procurement detail with bids, awards, items, and alerts."""
    proc = db.get(Procurement, ocid)
    if not proc:
        raise HTTPException(status_code=404, detail="Procurement not found")

    result = procurement_to_dict(proc)

    # Bids
    bids = db.query(Bid).filter(Bid.ocid == ocid).order_by(Bid.amount).all()
    result["bids"] = [
        {
            "id": b.id,
            "supplier_rut": b.supplier_rut,
            "supplier_name": b.supplier_name,
            "amount": b.amount,
            "date": b.date.isoformat() if b.date else None,
            "status": b.status,
        }
        for b in bids
    ]

    # Awards
    awards = db.query(Award).filter(Award.ocid == ocid).all()
    result["awards"] = [
        {
            "id": a.id,
            "supplier_rut": a.supplier_rut,
            "supplier_name": a.supplier_name,
            "amount": a.amount,
            "date": a.date.isoformat() if a.date else None,
            "status": a.status,
        }
        for a in awards
    ]

    # Items
    items = db.query(Item).filter(Item.ocid == ocid).all()
    result["items"] = [
        {
            "id": i.id,
            "unspsc_code": i.unspsc_code,
            "description": i.description,
            "quantity": i.quantity,
            "unit": i.unit,
            "unit_price": i.unit_price,
            "total_price": i.total_price,
        }
        for i in items
    ]

    # Alerts for this procurement
    alerts = db.query(Alert).filter(Alert.ocid == ocid).all()
    result["alerts"] = [
        {
            "id": a.id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "status": a.status,
        }
        for a in alerts
    ]

    # Parties
    parties = db.execute(text("""
        SELECT pa.rut, pa.name, pp.role, pa.region, pa.address, pa.phone, pa.contact_name
        FROM procurement_parties pp
        JOIN parties pa ON pa.rut = pp.party_rut
        WHERE pp.procurement_ocid = :ocid
    """), {"ocid": ocid}).fetchall()

    result["parties"] = [
        {
            "rut": p.rut,
            "name": p.name,
            "role": p.role,
            "region": p.region,
            "address": p.address,
            "phone": p.phone,
            "contact_name": p.contact_name,
        }
        for p in parties
    ]

    return result
