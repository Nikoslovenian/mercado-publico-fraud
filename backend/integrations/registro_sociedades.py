"""
Integration: Registro de Empresas y Sociedades (RES) / Tu Empresa en Un Dia
Queries public records to identify the legal representatives and shareholders of a given company RUT.
Due to lack of an open unauthenticated API, this acts as a Scraper / Data Fetcher.
Includes fallback mock logic for the MVP demonstration.
"""
import logging
import random
from typing import Optional, List, Dict
import requests  # type: ignore

logger = logging.getLogger(__name__)

def parse_res_data(rut: str, name: str) -> Dict:
    """
    Fetch and parse the corporate constitution of a company.
    Returns a dict with:
    {
       "representantes_legales": ["Juan Perez", ...],
       "siguientes_socios": ["Maria Gonzalez", ...]
    }
    """
    clean_rut = rut.replace(".", "").upper() if rut else ""
    
    # In a full production version, this would call an RPA bot (Selenium/Playwright)
    # scraping the Diario Oficial or Tu Empresa en un Dia using the company RUT.
    # Alternatively it could call a third-party KYC API like Floid.
    
    # FALLBACK MVP LOGIC
    if not clean_rut: return {}
    random.seed(clean_rut)
    
    # 60% chance of successfully decoding the society
    if random.random() < 0.6:
        surnames = ["Perez", "Gonzalez", "Silva", "Rojas", "Soto", "Contreras", "Mendez", "Vidal", "Munos", "Tapia", "Castro"]
        names = ["Juan", "Maria", "Carlos", "Ana", "Luis", "Jose", "Camila", "Javiera", "Diego", "Matias"]
        
        # If the name already has a surname, we might use it to seed the generated socio to create realistic mock links
        company_parts = (name or "").split()
        potential_surname1 = company_parts[0] if len(company_parts) > 0 else random.choice(surnames)
        potential_surname2 = company_parts[-1] if len(company_parts) > 1 else random.choice(surnames)
        
        # Avoid standard corporate words
        if potential_surname1.lower() in ["sociedad", "spa", "comercial", "constructora"]: potential_surname1 = random.choice(surnames)
        if potential_surname2.lower() in ["spa", "ltda", "sa", "servicios"]: potential_surname2 = random.choice(surnames)
        
        rep_legal = f"{random.choice(names)} {potential_surname1} {random.choice(surnames)}"
        socio_1 = f"{random.choice(names)} {potential_surname2} {random.choice(surnames)}"
        
        return {
            "representantes_legales": [rep_legal],
            "socios": [socio_1] if random.random() > 0.5 else []
        }
    
    return {}
