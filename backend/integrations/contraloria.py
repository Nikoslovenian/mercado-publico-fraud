"""
Integration: Contraloría General de la República (contraloria.cl)
Searches for audit reports and observations related to buyer organizations.
"""
import logging
import time
import requests
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.contraloria.cl"
AUDIT_SEARCH_URL = f"{BASE_URL}/web/cgr/informes-de-auditorias"
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
        }
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        _last_request = time.time()
        return resp
    except Exception as e:
        logger.error(f"Contraloría request failed: {e}")
        return None


def search_audit_reports(organism_name: str) -> list[dict]:
    """
    Search Contraloría for audit reports related to a buyer organization.
    Returns list of report summaries.
    """
    resp = _get(AUDIT_SEARCH_URL, params={"search": organism_name})
    if not resp or resp.status_code != 200:
        return []

    return _parse_audit_results(resp.text, organism_name)


def _parse_audit_results(html: str, search_term: str) -> list[dict]:
    """Parse Contraloría audit report search results."""
    results = []
    try:
        soup = BeautifulSoup(html, "lxml")
        # Look for report links/titles
        report_elements = soup.find_all(["article", "div"], class_=lambda c: c and "informe" in c.lower())

        if not report_elements:
            # Fallback: look for any link with "informe" in href
            links = soup.find_all("a", href=lambda h: h and ("informe" in h.lower() or "auditoria" in h.lower()))
            for link in links[:10]:
                results.append({
                    "title": link.get_text(strip=True),
                    "url": BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
                    "organism": search_term,
                    "source": "Contraloría General de la República",
                })
        else:
            for elem in report_elements[:10]:
                title_tag = elem.find(["h2", "h3", "a"])
                title = title_tag.get_text(strip=True) if title_tag else "Informe"
                link_tag = elem.find("a")
                url = ""
                if link_tag and link_tag.get("href"):
                    href = link_tag["href"]
                    url = BASE_URL + href if href.startswith("/") else href
                results.append({
                    "title": title,
                    "url": url,
                    "organism": search_term,
                    "source": "Contraloría General de la República",
                })
    except Exception as e:
        logger.debug(f"Failed to parse Contraloría results: {e}")
    return results
