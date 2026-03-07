"""
Enrichment Pipeline: cross-references suppliers with external data sources.
Queries SII, Portal de Transparencia, InfoLobby, and Contraloria
to enrich supplier profiles and detect potential conflicts of interest.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import Party, ExternalData, Alert
from integrations import sii, transparencia, infolobby, contraloria

logger = logging.getLogger(__name__)


def enrich_supplier(rut: str, db: Session) -> dict:
    """
    Enrich a single supplier with data from all external sources.
    Returns dict with results from each source.
    """
    results = {}

    # 1. SII - Tax authority data
    try:
        sii_data = sii.enrich_party_sii(rut, db)
        if sii_data:
            results["sii"] = sii_data
    except Exception as e:
        logger.error(f"SII enrichment failed for {rut}: {e}")

    # 2. Get supplier name for name-based lookups
    party = db.get(Party, rut)
    supplier_name = party.name if party else None
    contact_name = party.contact_name if party else None

    if not supplier_name:
        return results

    # 3. Transparencia - Public employee records
    try:
        # Get buyer organizations this supplier has worked with
        buyers = db.execute(text("""
            SELECT DISTINCT p.buyer_name
            FROM procurements p
            JOIN awards a ON a.ocid = p.ocid
            WHERE a.supplier_rut = :rut AND p.buyer_name IS NOT NULL
            LIMIT 5
        """), {"rut": rut}).fetchall()

        for buyer in buyers:
            conflict = transparencia.check_conflict_of_interest(
                supplier_name, rut, buyer.buyer_name
            )
            if conflict:
                # Store in external_data
                ext = db.get(ExternalData, (rut, "transparencia")) or ExternalData(
                    rut=rut, source="transparencia"
                )
                ext.raw_data = conflict
                ext.last_updated = datetime.utcnow()
                db.merge(ext)
                results["transparencia"] = conflict

                # If same-organization match, flag the party
                if conflict.get("match_type") == "same_organization" and party:
                    party.is_public_employee = True
                    party.public_employee_org = buyer.buyer_name

                break  # One conflict is enough
    except Exception as e:
        logger.error(f"Transparencia enrichment failed for {rut}: {e}")

    # 4. InfoLobby - Lobby meetings
    try:
        search_name = contact_name or supplier_name
        buyers = db.execute(text("""
            SELECT DISTINCT p.buyer_name
            FROM procurements p
            JOIN awards a ON a.ocid = p.ocid
            WHERE a.supplier_rut = :rut AND p.buyer_name IS NOT NULL
            LIMIT 3
        """), {"rut": rut}).fetchall()

        for buyer in buyers:
            lobby = infolobby.check_lobby_activity(
                search_name, rut, buyer.buyer_name
            )
            if lobby and lobby.get("total_meetings_found", 0) > 0:
                ext = db.get(ExternalData, (rut, "infolobby")) or ExternalData(
                    rut=rut, source="infolobby"
                )
                ext.raw_data = lobby
                ext.last_updated = datetime.utcnow()
                db.merge(ext)
                results["infolobby"] = lobby
                break
    except Exception as e:
        logger.error(f"InfoLobby enrichment failed for {rut}: {e}")

    # 5. Contraloria - Audit reports on buyer organizations
    try:
        buyers = db.execute(text("""
            SELECT DISTINCT p.buyer_name
            FROM procurements p
            JOIN awards a ON a.ocid = p.ocid
            WHERE a.supplier_rut = :rut AND p.buyer_name IS NOT NULL
            LIMIT 3
        """), {"rut": rut}).fetchall()

        for buyer in buyers:
            reports = contraloria.search_audit_reports(buyer.buyer_name)
            if reports:
                ext = db.get(ExternalData, (rut, "contraloria")) or ExternalData(
                    rut=rut, source="contraloria"
                )
                ext.raw_data = {"buyer_name": buyer.buyer_name, "reports": reports[:5]}
                ext.last_updated = datetime.utcnow()
                db.merge(ext)
                results["contraloria"] = reports[:5]
                break
    except Exception as e:
        logger.error(f"Contraloria enrichment failed for {rut}: {e}")

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to commit enrichment for {rut}: {e}")
        db.rollback()

    return results


def enrich_top_suppliers(db: Session, limit: int = 50) -> dict:
    """
    Enrich the top N suppliers with the most alerts or highest awarded amounts.
    Returns summary of enrichment results.
    """
    # Get top suppliers by alert count and amount
    top_suppliers = db.execute(text("""
        SELECT
            a.supplier_rut,
            COUNT(*) as alert_count,
            SUM(COALESCE(a.amount_involved, 0)) as total_amount
        FROM alerts a
        WHERE a.supplier_rut IS NOT NULL
        GROUP BY a.supplier_rut
        ORDER BY alert_count DESC, total_amount DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()

    # Also get top suppliers by awarded amount (even without alerts)
    top_awarded = db.execute(text("""
        SELECT
            a.supplier_rut,
            SUM(a.amount) as total_awarded
        FROM awards a
        WHERE a.supplier_rut IS NOT NULL
          AND a.supplier_rut NOT IN (
              SELECT DISTINCT supplier_rut FROM alerts WHERE supplier_rut IS NOT NULL
          )
        GROUP BY a.supplier_rut
        ORDER BY total_awarded DESC
        LIMIT :limit
    """), {"limit": limit // 2}).fetchall()

    ruts_to_enrich = []
    seen = set()
    for row in top_suppliers:
        if row.supplier_rut not in seen:
            ruts_to_enrich.append(row.supplier_rut)
            seen.add(row.supplier_rut)
    for row in top_awarded:
        if row.supplier_rut not in seen:
            ruts_to_enrich.append(row.supplier_rut)
            seen.add(row.supplier_rut)

    summary = {
        "total_suppliers": len(ruts_to_enrich),
        "enriched": 0,
        "sii_found": 0,
        "transparencia_found": 0,
        "infolobby_found": 0,
        "contraloria_found": 0,
        "errors": 0,
    }

    for i, rut in enumerate(ruts_to_enrich):
        logger.info(f"Enriching {i+1}/{len(ruts_to_enrich)}: {rut}")
        try:
            results = enrich_supplier(rut, db)
            if results:
                summary["enriched"] += 1
                if "sii" in results:
                    summary["sii_found"] += 1
                if "transparencia" in results:
                    summary["transparencia_found"] += 1
                if "infolobby" in results:
                    summary["infolobby_found"] += 1
                if "contraloria" in results:
                    summary["contraloria_found"] += 1
        except Exception as e:
            logger.error(f"Enrichment failed for {rut}: {e}")
            summary["errors"] += 1

    logger.info(f"Enrichment complete: {summary}")
    return summary
