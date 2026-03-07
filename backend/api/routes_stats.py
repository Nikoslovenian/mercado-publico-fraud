"""
Stats API routes: summary statistics for the dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    """Return dashboard summary statistics."""

    total_procurements = db.execute(text("SELECT COUNT(*) FROM procurements")).scalar()
    total_alerts = db.execute(text("SELECT COUNT(*) FROM alerts")).scalar()
    total_suppliers = db.execute(text("SELECT COUNT(DISTINCT rut) FROM parties WHERE rut IN (SELECT DISTINCT party_rut FROM procurement_parties WHERE role IN ('supplier','tenderer'))")).scalar()
    total_amount = db.execute(text("SELECT COALESCE(SUM(total_amount), 0) FROM procurements WHERE total_amount > 0")).scalar()

    alerts_by_severity = db.execute(text("""
        SELECT severity, COUNT(*) as count
        FROM alerts
        GROUP BY severity
        ORDER BY CASE severity WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END
    """)).fetchall()

    alerts_by_type = db.execute(text("""
        SELECT alert_type, COUNT(*) as count, severity
        FROM alerts
        GROUP BY alert_type, severity
        ORDER BY count DESC
    """)).fetchall()

    top_suppliers = db.execute(text("""
        SELECT
            a.supplier_rut,
            a.supplier_name,
            COUNT(*) as alert_count,
            MAX(a.severity) as max_severity,
            SUM(a.amount_involved) as total_amount
        FROM alerts a
        WHERE a.supplier_rut IS NOT NULL
        GROUP BY a.supplier_rut, a.supplier_name
        ORDER BY alert_count DESC
        LIMIT 10
    """)).fetchall()

    top_buyers = db.execute(text("""
        SELECT
            a.buyer_rut,
            a.buyer_name,
            COUNT(*) as alert_count,
            SUM(a.amount_involved) as total_amount
        FROM alerts a
        WHERE a.buyer_rut IS NOT NULL
        GROUP BY a.buyer_rut, a.buyer_name
        ORDER BY alert_count DESC
        LIMIT 10
    """)).fetchall()

    alerts_by_region = db.execute(text("""
        SELECT region, COUNT(*) as count
        FROM alerts
        WHERE region IS NOT NULL AND region != ''
        GROUP BY region
        ORDER BY count DESC
    """)).fetchall()

    alerts_by_month = db.execute(text("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as count
        FROM alerts
        GROUP BY month
        ORDER BY month
    """)).fetchall()

    procurements_by_method = db.execute(text("""
        SELECT method_details, COUNT(*) as count, SUM(total_amount) as total
        FROM procurements
        GROUP BY method_details
        ORDER BY count DESC
        LIMIT 15
    """)).fetchall()

    # Monthly breakdown by fraud type (for stacked chart)
    alerts_monthly_by_type = db.execute(text("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            alert_type,
            COUNT(*) as count
        FROM alerts
        GROUP BY month, alert_type
        ORDER BY month, alert_type
    """)).fetchall()

    # Cumulative totals per fraud type
    fraud_type_totals = db.execute(text("""
        SELECT
            alert_type,
            COUNT(*) as total,
            SUM(CASE WHEN severity='alta' THEN 1 ELSE 0 END) as count_alta,
            SUM(CASE WHEN severity='media' THEN 1 ELSE 0 END) as count_media,
            SUM(CASE WHEN severity='baja' THEN 1 ELSE 0 END) as count_baja,
            SUM(COALESCE(amount_involved, 0)) as total_amount
        FROM alerts
        GROUP BY alert_type
        ORDER BY total DESC
    """)).fetchall()

    return {
        "summary": {
            "total_procurements": total_procurements,
            "total_alerts": total_alerts,
            "total_suppliers": total_suppliers,
            "total_amount_clp": float(total_amount or 0),
        },
        "alerts_by_severity": [
            {"severity": r.severity, "count": r.count}
            for r in alerts_by_severity
        ],
        "alerts_by_type": [
            {"type": r.alert_type, "count": r.count, "severity": r.severity}
            for r in alerts_by_type
        ],
        "top_suppliers_with_alerts": [
            {
                "rut": r.supplier_rut,
                "name": r.supplier_name,
                "alert_count": r.alert_count,
                "max_severity": r.max_severity,
                "total_amount": float(r.total_amount or 0),
            }
            for r in top_suppliers
        ],
        "top_buyers_with_alerts": [
            {
                "rut": r.buyer_rut,
                "name": r.buyer_name,
                "alert_count": r.alert_count,
                "total_amount": float(r.total_amount or 0),
            }
            for r in top_buyers
        ],
        "alerts_by_region": [
            {"region": r.region, "count": r.count}
            for r in alerts_by_region
        ],
        "alerts_by_month": [
            {"month": r.month, "count": r.count}
            for r in alerts_by_month
        ],
        "procurements_by_method": [
            {
                "method": r.method_details,
                "count": r.count,
                "total_clp": float(r.total or 0),
            }
            for r in procurements_by_method
        ],
        "alerts_monthly_by_type": [
            {"month": r.month, "type": r.alert_type, "count": r.count}
            for r in alerts_monthly_by_type
        ],
        "fraud_type_totals": [
            {
                "type": r.alert_type,
                "total": r.total,
                "alta": r.count_alta,
                "media": r.count_media,
                "baja": r.count_baja,
                "total_amount": float(r.total_amount or 0),
            }
            for r in fraud_type_totals
        ],
    }
