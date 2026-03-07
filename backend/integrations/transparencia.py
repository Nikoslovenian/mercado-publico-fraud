"""
Integration: Portal de Transparencia (portaltransparencia.cl)
Scrapes public servant salary/employment information to cross-reference
with suppliers for conflict of interest detection.
Data is public under Law 20.285 (Ley de Transparencia).
"""
import logging
import time
import re
import unicodedata
import requests
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.portaltransparencia.cl"
SEARCH_URL = f"{BASE_URL}/transparencia/busqueda/busquedaAvanzada"
PERSON_SEARCH_URL = f"{BASE_URL}/transparencia/busqueda/resultado"

RATE_DELAY = 2.0
_last_request = 0.0


def _get(url: str, params: dict = None) -> Optional[requests.Response]:
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_DELAY:
        time.sleep(RATE_DELAY - elapsed)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; FraudDetector/1.0; academic-research)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "es-CL,es;q=0.9",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        _last_request = time.time()
        return resp
    except Exception as e:
        logger.error(f"Transparencia request failed: {e}")
        return None


def search_person(name: str) -> list[dict]:
    """
    Search for a person by name in the Portal de Transparencia.
    Returns list of public employee records found.
    """
    resp = _get(SEARCH_URL, params={
        "tipoBusqueda": "funcionarios",
        "search": name,
    })

    if not resp or resp.status_code != 200:
        return []

    return _parse_employee_results(resp.text, name)


def search_by_organism(organism_code: str, page: int = 1) -> list[dict]:
    """
    Get list of public employees for a specific organism.
    Returns list of employee records.
    """
    url = f"{BASE_URL}/transparencia/remuneraciones/{organism_code}"
    resp = _get(url, params={"page": page})

    if not resp or resp.status_code != 200:
        return []

    return _parse_remuneraciones(resp.text)


def _parse_employee_results(html: str, search_term: str) -> list[dict]:
    """Parse search results from Portal de Transparencia."""
    results = []
    try:
        soup = BeautifulSoup(html, "lxml")
        # Find result tables or cards
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            headers = []
            for row in rows:
                cells = row.find_all(["th", "td"])
                cell_texts = [c.get_text(strip=True) for c in cells]
                if not cell_texts:
                    continue
                if not headers:
                    headers = [t.lower() for t in cell_texts]
                else:
                    record = dict(zip(headers, cell_texts))
                    record["source"] = "Portal de Transparencia"
                    record["search_term"] = search_term
                    results.append(record)
    except Exception as e:
        logger.debug(f"Failed to parse Transparencia results: {e}")
    return results


def _parse_remuneraciones(html: str) -> list[dict]:
    """Parse employee salary records from Portal de Transparencia."""
    results = []
    try:
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            headers = []
            for row in rows:
                cells = row.find_all(["th", "td"])
                texts = [c.get_text(strip=True) for c in cells]
                if not texts:
                    continue
                if not headers:
                    headers = [t.lower() for t in texts]
                else:
                    if len(texts) == len(headers):
                        record = dict(zip(headers, texts))
                        record["source"] = "Portal de Transparencia - Remuneraciones"
                        results.append(record)
    except Exception as e:
        logger.debug(f"Failed to parse remuneraciones: {e}")
    return results


def _normalize_name(name: str) -> str:
    """Normalize name for fuzzy comparison: remove accents, lowercase."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_name.lower().strip())


def _extract_surnames(name: str) -> set:
    """Extract likely surnames from a full name (Chilean format)."""
    normalized = _normalize_name(name)
    if not normalized:
        return set()
    parts = normalized.split()
    if len(parts) <= 1:
        return set()
    if len(parts) >= 3:
        return {parts[-2], parts[-1]}
    return {parts[-1]}


def _fuzzy_org_match(buyer_name: str, org_name: str) -> bool:
    """Check if buyer organization name fuzzy-matches an org from Transparencia."""
    if not buyer_name or not org_name:
        return False
    buyer_norm = _normalize_name(buyer_name)
    org_norm = _normalize_name(org_name)
    # Remove common stop words
    stopwords = {"de", "del", "la", "el", "y", "los", "las", "region", "municipal", "gobierno"}
    buyer_words = set(buyer_norm.split()) - stopwords
    org_words = set(org_norm.split()) - stopwords
    if not buyer_words or not org_words:
        return False
    overlap = buyer_words & org_words
    # Match if at least 2 significant words overlap, or 1 if short name
    return len(overlap) >= min(2, len(buyer_words))


def search_by_rut(rut: str) -> list[dict]:
    """
    Search for a person by RUT in Portal de Transparencia.
    Returns list of public employee records found.
    """
    if not rut or len(rut.strip()) < 5:
        return []

    resp = _get(SEARCH_URL, params={
        "tipoBusqueda": "funcionarios",
        "search": rut,
    })

    if not resp or resp.status_code != 200:
        return []

    return _parse_employee_results(resp.text, rut)


def check_conflict_of_interest(supplier_name: str, supplier_rut: str, buyer_name: str) -> Optional[dict]:
    """
    Cross-reference a supplier name/RUT with public employee records
    at the buying organization.
    Uses fuzzy matching for both names and organizations.
    Returns dict with findings if conflict detected, None otherwise.
    """
    # Try searching by name first
    results = search_person(supplier_name)

    # Also try by RUT if available
    if supplier_rut:
        rut_results = search_by_rut(supplier_rut)
        # Merge without duplicates
        existing_orgs = {r.get("organismo", "") for r in results}
        for r in rut_results:
            if r.get("organismo", "") not in existing_orgs:
                results.append(r)

    if not results:
        return None

    # Check if any result matches buyer organization using fuzzy matching
    same_org_conflicts = []
    other_matches = []

    for r in results:
        org = str(r.get("organismo", "") or r.get("institución", "") or r.get("institucion", "") or "")
        if _fuzzy_org_match(buyer_name, org):
            same_org_conflicts.append(r)
        else:
            other_matches.append(r)

    if same_org_conflicts:
        return {
            "supplier_name": supplier_name,
            "supplier_rut": supplier_rut,
            "buyer_name": buyer_name,
            "matches": same_org_conflicts,
            "match_type": "same_organization",
            "source": "Portal de Transparencia",
            "note": (
                f"Se encontraron {len(same_org_conflicts)} registros de funcionario "
                f"publico con nombre similar al proveedor en el MISMO organismo comprador."
            ),
        }
    elif other_matches:
        return {
            "supplier_name": supplier_name,
            "supplier_rut": supplier_rut,
            "buyer_name": buyer_name,
            "matches": other_matches[:5],
            "match_type": "different_organization",
            "source": "Portal de Transparencia",
            "note": (
                f"Se encontraron {len(other_matches)} registros de funcionario "
                f"publico con nombre similar al proveedor (en otro organismo)."
            ),
        }

    return None
