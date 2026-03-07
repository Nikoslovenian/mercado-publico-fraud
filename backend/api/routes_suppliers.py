"""
Suppliers API routes.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, Party, Alert, ExternalData
from integrations import mercado_publico, sii, transparencia, contraloria

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(
    q: str = Query(None),
    region: str = Query(None),
    has_alerts: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List suppliers with optional filtering."""
    query = db.query(Party).filter(
        Party.rut.in_(
            db.execute(text("SELECT DISTINCT party_rut FROM procurement_parties WHERE role IN ('supplier','tenderer')")).scalars().all()
        )
    )

    if q:
        query = query.filter(
            Party.name.ilike(f"%{q}%") |
            Party.rut.ilike(f"%{q}%") |
            Party.legal_name.ilike(f"%{q}%")
        )
    if region:
        query = query.filter(Party.region.ilike(f"%{region}%"))

    if has_alerts is True:
        alert_ruts = db.execute(
            text("SELECT DISTINCT supplier_rut FROM alerts WHERE supplier_rut IS NOT NULL")
        ).scalars().all()
        query = query.filter(Party.rut.in_(alert_ruts))

    total = query.count()
    suppliers = query.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for s in suppliers:
        alert_count = db.query(Alert).filter(Alert.supplier_rut == s.rut).count()
        awards_count = db.execute(
            text("SELECT COUNT(*) FROM awards WHERE supplier_rut = :rut"), {"rut": s.rut}
        ).scalar()
        total_awarded = db.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM awards WHERE supplier_rut = :rut"), {"rut": s.rut}
        ).scalar()

        result.append({
            "rut": s.rut,
            "name": s.name,
            "legal_name": s.legal_name,
            "region": s.region,
            "address": s.address,
            "alert_count": alert_count,
            "awards_count": awards_count,
            "total_awarded_clp": float(total_awarded or 0),
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": result,
    }


@router.get("/{rut}")
def get_supplier(rut: str, db: Session = Depends(get_db)):
    """Get full supplier profile with procurement history, alerts, and external data."""
    party = db.get(Party, rut)
    if not party:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Procurement history
    procs = db.execute(text("""
        SELECT
            p.ocid, p.title, p.buyer_name, p.buyer_rut, p.region,
            p.tender_start, p.method_details, a.amount, a.status as award_status
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        WHERE a.supplier_rut = :rut
        ORDER BY p.tender_start DESC
        LIMIT 100
    """), {"rut": rut}).fetchall()

    # Tender participations (bids)
    bids = db.execute(text("""
        SELECT
            b.ocid, b.amount, b.status, b.date,
            p.title, p.buyer_name
        FROM bids b
        JOIN procurements p ON p.ocid = b.ocid
        WHERE b.supplier_rut = :rut
        ORDER BY b.date DESC
        LIMIT 100
    """), {"rut": rut}).fetchall()

    # Alerts
    alerts = db.query(Alert).filter(Alert.supplier_rut == rut).order_by(Alert.severity.desc()).all()

    # Related suppliers (shared address/phone/contact)
    related = db.execute(text("""
        SELECT a.id, a.supplier_rut, a.supplier_name, a.alert_type, a.severity, a.evidence
        FROM alerts a
        WHERE a.alert_type = 'RELA'
          AND (
            JSON_EXTRACT(a.evidence, '$.rut1') = :rut
            OR JSON_EXTRACT(a.evidence, '$.rut2') = :rut
          )
    """), {"rut": rut}).fetchall()

    # External data cache
    ext_data = db.execute(
        text("SELECT source, raw_data, last_updated FROM external_data WHERE rut = :rut"),
        {"rut": rut}
    ).fetchall()

    return {
        "rut": party.rut,
        "name": party.name,
        "legal_name": party.legal_name,
        "address": party.address,
        "region": party.region,
        "phone": party.phone,
        "email": party.email,
        "contact_name": party.contact_name,
        "sii_start_date": party.sii_start_date.isoformat() if party.sii_start_date else None,
        "sii_activity_code": party.sii_activity_code,
        "sii_status": party.sii_status,
        "is_public_employee": party.is_public_employee,
        "public_employee_org": party.public_employee_org,
        "procurement_history": [
            {
                "ocid": p.ocid,
                "title": p.title,
                "buyer_name": p.buyer_name,
                "buyer_rut": p.buyer_rut,
                "region": p.region,
                "date": str(p.tender_start) if p.tender_start else None,
                "method": p.method_details,
                "amount": p.amount,
                "status": p.award_status,
            }
            for p in procs
        ],
        "bid_history": [
            {
                "ocid": b.ocid,
                "title": b.title,
                "buyer_name": b.buyer_name,
                "amount": b.amount,
                "status": b.status,
                "date": str(b.date) if b.date else None,
            }
            for b in bids
        ],
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
        "related_suppliers": [
            {
                "alert_id": r.id,
                "supplier_rut": r.supplier_rut,
                "supplier_name": r.supplier_name,
                "evidence": r.evidence,
            }
            for r in related
        ],
        "external_data": [
            {
                "source": e.source,
                "data": e.raw_data,
                "last_updated": str(e.last_updated) if e.last_updated else None,
            }
            for e in ext_data
        ],
    }


@router.get("/{rut}/network")
def get_supplier_network(rut: str, db: Session = Depends(get_db)):
    """Get network graph data for supplier relationships."""
    # Get all RELA alerts involving this supplier
    alerts = db.execute(text("""
        SELECT evidence FROM alerts
        WHERE alert_type = 'RELA'
          AND (
            JSON_EXTRACT(evidence, '$.rut1') = :rut
            OR JSON_EXTRACT(evidence, '$.rut2') = :rut
          )
    """), {"rut": rut}).fetchall()

    nodes = {}
    edges = []

    def add_node(rut_val, name, level=0):
        if rut_val not in nodes:
            alert_count = db.query(Alert).filter(Alert.supplier_rut == rut_val).count()
            nodes[rut_val] = {
                "id": rut_val,
                "name": name or rut_val,
                "alert_count": alert_count,
                "level": level,
            }

    add_node(rut, db.execute(text("SELECT name FROM parties WHERE rut = :r"), {"r": rut}).scalar(), 0)

    for alert in alerts:
        evidence = alert.evidence
        if not evidence:
            continue
        r1 = evidence.get("rut1")
        r2 = evidence.get("rut2")
        n1 = evidence.get("name1", r1)
        n2 = evidence.get("name2", r2)
        relations = evidence.get("shared_attributes", [])

        if r1:
            add_node(r1, n1, 1)
        if r2:
            add_node(r2, n2, 1)

        if r1 and r2:
            edges.append({
                "source": r1,
                "target": r2,
                "relations": relations,
                "shared_procurements": evidence.get("shared_procurement_count", 0),
            })

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }


@router.post("/{rut}/refresh-external")
def refresh_external_data(rut: str, db: Session = Depends(get_db)):
    """Fetch and cache fresh external data from all sources for a supplier."""
    from enrichment import enrich_supplier

    results = enrich_supplier(rut, db)

    # Also fetch Mercado Publico API data
    from datetime import datetime
    mp_data = mercado_publico.buscar_proveedor(rut)
    if mp_data:
        ext = db.get(ExternalData, (rut, "mercadopublico")) or ExternalData(rut=rut, source="mercadopublico")
        ext.raw_data = mp_data
        ext.last_updated = datetime.utcnow()
        db.merge(ext)
        db.commit()
        results["mercadopublico"] = mp_data

    return {"rut": rut, "fetched_sources": list(results.keys()), "data": results}
