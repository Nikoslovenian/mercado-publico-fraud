"""
Integration: Mercado Público API (api.mercadopublico.cl)
Requires a ticket obtained from https://api.mercadopublico.cl/modules/Participa.aspx
"""
import logging
import os
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
TICKET = os.environ.get("MERCADOPUBLICO_TICKET", "")
RATE_LIMIT_DELAY = 1.1  # Seconds between requests (max 1 req/sec)

_last_request_time = 0.0


def _get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Rate-limited GET request to Mercado Público API."""
    global _last_request_time

    if not TICKET:
        logger.warning("MERCADOPUBLICO_TICKET not configured")
        return None

    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)

    url = f"{BASE_URL}/{endpoint}"
    params = params or {}
    params["ticket"] = TICKET

    try:
        resp = requests.get(url, params=params, timeout=15)
        _last_request_time = time.time()
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"API returned {resp.status_code} for {endpoint}")
            return None
    except Exception as e:
        logger.error(f"Mercado Público API error: {e}")
        return None


def buscar_proveedor(rut: str) -> Optional[dict]:
    """
    Search for a provider by RUT.
    Returns provider data dict or None.
    """
    # Normalize RUT (remove dots and dash, add dash before last digit)
    rut = rut.replace(".", "").replace("-", "").strip().upper()
    if len(rut) > 1:
        rut = rut[:-1] + "-" + rut[-1]

    data = _get("Empresas/BuscarProveedor", {"CodigoEmpresa": rut})
    if data and data.get("Listado"):
        return data["Listado"][0] if data["Listado"] else None
    return None


def get_licitacion(code: str) -> Optional[dict]:
    """
    Get full licitacion data by code.
    """
    data = _get("licitaciones", {"codigo": code})
    if data and data.get("Listado"):
        return data["Listado"][0] if data["Listado"] else None
    return None


def buscar_comprador(rut: str) -> Optional[dict]:
    """Get buyer (organismo) data by RUT."""
    rut = rut.replace(".", "").replace("-", "").strip().upper()
    if len(rut) > 1:
        rut = rut[:-1] + "-" + rut[-1]
    data = _get("Empresas/BuscarComprador", {"CodigoOrganismo": rut})
    if data and data.get("Listado"):
        return data["Listado"][0] if data["Listado"] else None
    return None


def get_ordenes_compra_proveedor(rut: str) -> Optional[list]:
    """Get purchase orders for a specific supplier."""
    rut = rut.replace(".", "").replace("-", "").strip().upper()
    if len(rut) > 1:
        rut = rut[:-1] + "-" + rut[-1]
    data = _get("ordenesdecompra", {"CodigoProveedor": rut})
    if data and data.get("Listado"):
        return data["Listado"]
    return None
