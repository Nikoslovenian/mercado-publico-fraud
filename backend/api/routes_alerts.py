"""
Alerts API routes.
"""
import csv
import io
import json
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

ALERT_TYPE_LABELS = {
    "FRAC": "Compra Fraccionada",
    "CONC": "Concentración de Proveedor",
    "COLU": "Colusión / Shadow Bidding",
    "COLU2": "Rotación de Ganadores",
    "PLAZ": "Plazo Anómalo",
    "RELA": "Proveedores Relacionados",
    "PREC": "Precio Anómalo",
    "NUEV": "Empresa Nueva Ganadora",
    "TRAT": "Trato Directo Excesivo",
    "DTDR": "Desierta + Trato Directo",
    "CONF": "Conflicto de Interés",
    "UNIC": "Oferente Único Recurrente",
    "TEMP": "Patrón Temporal Sospechoso",
}


def alert_to_dict(a: Alert) -> dict:
    return {
        "id": a.id,
        "ocid": a.ocid,
        "alert_type": a.alert_type,
        "alert_type_label": ALERT_TYPE_LABELS.get(a.alert_type, a.alert_type),
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "evidence": a.evidence,
        "buyer_rut": a.buyer_rut,
        "buyer_name": a.buyer_name,
        "supplier_rut": a.supplier_rut,
        "supplier_name": a.supplier_name,
        "region": a.region,
        "amount_involved": a.amount_involved,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "status": a.status,
    }


@router.get("")
def list_alerts(
    alert_type: str = Query(None),
    severity: str = Query(None),
    region: str = Query(None),
    buyer_rut: str = Query(None),
    supplier_rut: str = Query(None),
    status: str = Query(None),
    q: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List alerts with filtering and pagination."""
    query = db.query(Alert)

    if alert_type:
        query = query.filter(Alert.alert_type == alert_type.upper())
    if severity:
        query = query.filter(Alert.severity == severity.lower())
    if region:
        query = query.filter(Alert.region.ilike(f"%{region}%"))
    if buyer_rut:
        query = query.filter(Alert.buyer_rut == buyer_rut)
    if supplier_rut:
        query = query.filter(Alert.supplier_rut == supplier_rut)
    if status:
        query = query.filter(Alert.status == status)
    if q:
        query = query.filter(
            Alert.title.ilike(f"%{q}%") |
            Alert.description.ilike(f"%{q}%") |
            Alert.buyer_name.ilike(f"%{q}%") |
            Alert.supplier_name.ilike(f"%{q}%")
        )

    total = query.count()
    alerts = (
        query
        .order_by(
            Alert.severity.desc(),  # alta first
            Alert.created_at.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [alert_to_dict(a) for a in alerts],
    }


@router.get("/export")
def export_alerts(
    alert_type: str = Query(None),
    severity: str = Query(None),
    region: str = Query(None),
    db: Session = Depends(get_db),
):
    """Export alerts as CSV."""
    query = db.query(Alert)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type.upper())
    if severity:
        query = query.filter(Alert.severity == severity.lower())
    if region:
        query = query.filter(Alert.region.ilike(f"%{region}%"))

    alerts = query.order_by(Alert.severity.desc(), Alert.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "OCID", "Tipo", "Tipo (Etiqueta)", "Severidad", "Título",
        "Descripción", "RUT Comprador", "Organismo", "RUT Proveedor",
        "Proveedor", "Región", "Monto Involucrado CLP", "Estado", "Fecha"
    ])

    for a in alerts:
        writer.writerow([
            a.id, a.ocid, a.alert_type,
            ALERT_TYPE_LABELS.get(a.alert_type, a.alert_type),
            a.severity, a.title, a.description,
            a.buyer_rut, a.buyer_name, a.supplier_rut, a.supplier_name,
            a.region, a.amount_involved, a.status,
            a.created_at.isoformat() if a.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alertas_fraude.csv"},
    )


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Get full alert detail including evidence."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert_to_dict(alert)


@router.patch("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    status: str = Query(..., pattern="^(open|reviewed|dismissed|confirmed)$"),
    db: Session = Depends(get_db),
):
    """Update alert status (open/reviewed/dismissed/confirmed)."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = status
    db.commit()
    return {"id": alert_id, "status": status}
