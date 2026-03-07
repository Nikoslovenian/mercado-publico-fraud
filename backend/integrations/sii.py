"""
Integration: SII (Servicio de Impuestos Internos)
Queries public SII data for RUT validation and company information.
Uses the public SII endpoint (no authentication required for public data).
"""
import logging
import requests
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Public SII endpoint (no auth required for basic lookup)
SII_PERSON_URL = "https://zeus.sii.cl/cvc_cgi/stc/getstc"
SII_COMPANY_URL = "https://zeus.sii.cl/cvc_cgi/stc/getstc"

# Alternative: SII contribuyente info
SII_CONTRIB_URL = "https://www4c.sii.cl/bolcoreinternetui/api/v1/pagos/estado/contribuyente"

_last_request = 0.0
RATE_DELAY = 2.0  # Be respectful with public endpoints


def _rate_limited_get(url: str, params: dict = None, headers: dict = None) -> Optional[requests.Response]:
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_DELAY:
        time.sleep(RATE_DELAY - elapsed)

    try:
        resp = requests.get(url, params=params, headers=headers or {
            "User-Agent": "Mozilla/5.0 (compatible; FraudDetector/1.0; research)",
            "Accept": "application/json, text/html",
        }, timeout=15)
        _last_request = time.time()
        return resp
    except Exception as e:
        logger.error(f"SII request failed: {e}")
        return None


def format_rut(rut: str) -> str:
    """Format RUT as XX.XXX.XXX-X for display."""
    rut = rut.replace(".", "").replace("-", "").strip().upper()
    if len(rut) < 2:
        return rut
    body = rut[:-1]
    dv = rut[-1]
    # Add dots
    groups = []
    while body:
        groups.insert(0, body[-3:])
        body = body[:-3]
    return ".".join(groups) + "-" + dv


def validate_rut_checksum(rut: str) -> bool:
    """Validate Chilean RUT using the Módulo 11 algorithm."""
    rut = rut.replace(".", "").replace("-", "").strip().upper()
    if len(rut) < 2:
        return False
    body = rut[:-1]
    dv = rut[-1]

    if not body.isdigit():
        return False

    total = 0
    multiplier = 2
    for digit in reversed(body):
        total += int(digit) * multiplier
        multiplier = multiplier % 7 + 2

    remainder = 11 - (total % 11)
    if remainder == 11:
        expected_dv = "0"
    elif remainder == 10:
        expected_dv = "K"
    else:
        expected_dv = str(remainder)

    return dv == expected_dv


def get_sii_info(rut: str) -> Optional[dict]:
    """
    Get basic public info for a RUT from SII.
    Returns dict with: rut, nombre, actividad, inicio_actividades, estado
    Only returns publicly available data (no sensitive tax info).
    """
    if not validate_rut_checksum(rut):
        logger.debug(f"Invalid RUT checksum: {rut}")
        return {"rut": rut, "valid": False, "error": "RUT inválido (dígito verificador incorrecto)"}

    # Try SII public lookup
    rut_clean = rut.replace(".", "").replace("-", "").upper()
    body = rut_clean[:-1]
    dv = rut_clean[-1]

    try:
        # SII public info endpoint (HTML response - parse it)
        url = f"https://zeus.sii.cl/cvc_cgi/stc/getstc"
        resp = _rate_limited_get(url, params={"RUT": body, "DV": dv})

        if resp and resp.status_code == 200:
            return _parse_sii_html(resp.text, rut)
    except Exception as e:
        logger.error(f"SII lookup failed for {rut}: {e}")

    # Return minimal info if lookup fails
    return {
        "rut": rut,
        "valid": True,
        "nombre": None,
        "actividad": None,
        "inicio_actividades": None,
        "estado": "desconocido",
        "source": "SII (consulta no disponible)",
    }


def _parse_sii_html(html: str, rut: str) -> dict:
    """Parse SII HTML response to extract company info."""
    from bs4 import BeautifulSoup
    result = {
        "rut": rut,
        "valid": True,
        "nombre": None,
        "actividad": None,
        "inicio_actividades": None,
        "estado": "activo",
        "source": "SII (zeus.sii.cl)",
    }

    try:
        soup = BeautifulSoup(html, "lxml")
        # SII returns different structures - try to find key fields
        text_content = soup.get_text(separator="\n")
        lines = [l.strip() for l in text_content.split("\n") if l.strip()]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "nombre" in line_lower or "razón social" in line_lower or "razon social" in line_lower:
                if i + 1 < len(lines):
                    result["nombre"] = lines[i + 1]
            elif "actividad" in line_lower or "giro" in line_lower:
                if i + 1 < len(lines):
                    result["actividad"] = lines[i + 1]
            elif "inicio" in line_lower and "actividad" in line_lower:
                if i + 1 < len(lines):
                    result["inicio_actividades"] = lines[i + 1]
            elif "no ha sido encontrado" in line_lower or "no encontrado" in line_lower:
                result["estado"] = "no encontrado"
            elif "contribuyente no tiene inicio de actividades" in line_lower:
                result["estado"] = "sin_inicio_actividades"

        # Also try parsing tables (SII sometimes returns data in tables)
        tables = soup.find_all("table")
        for table in tables:
            cells = table.find_all("td")
            for j, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True).lower()
                if ("nombre" in cell_text or "razón" in cell_text) and j + 1 < len(cells):
                    val = cells[j + 1].get_text(strip=True)
                    if val and not result["nombre"]:
                        result["nombre"] = val
                elif ("actividad" in cell_text or "giro" in cell_text) and j + 1 < len(cells):
                    val = cells[j + 1].get_text(strip=True)
                    if val and not result["actividad"]:
                        result["actividad"] = val
                elif "inicio" in cell_text and j + 1 < len(cells):
                    val = cells[j + 1].get_text(strip=True)
                    if val and not result["inicio_actividades"]:
                        result["inicio_actividades"] = val

    except Exception as e:
        logger.debug(f"Failed to parse SII HTML: {e}")

    return result


def enrich_party_sii(rut: str, db) -> Optional[dict]:
    """
    Fetch SII data and update the Party record in the database.
    Returns the SII data dict, or None on failure.
    """
    from datetime import datetime as dt

    sii_data = get_sii_info(rut)
    if not sii_data or not sii_data.get("valid", False):
        return sii_data

    try:
        from database import Party, ExternalData
        party = db.get(Party, rut)
        if party:
            # Update SII fields on party
            if sii_data.get("actividad"):
                party.sii_activity_code = sii_data["actividad"]
            if sii_data.get("estado"):
                party.sii_status = sii_data["estado"]
            if sii_data.get("inicio_actividades"):
                # Try to parse the date
                for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        party.sii_start_date = dt.strptime(
                            sii_data["inicio_actividades"], fmt
                        )
                        break
                    except (ValueError, TypeError):
                        continue
            party.external_data_updated = dt.utcnow()

        # Also store in external_data cache
        ext = db.get(ExternalData, (rut, "sii")) or ExternalData(rut=rut, source="sii")
        ext.raw_data = sii_data
        ext.last_updated = dt.utcnow()
        db.merge(ext)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to enrich party {rut} with SII data: {e}")
        db.rollback()

    return sii_data
