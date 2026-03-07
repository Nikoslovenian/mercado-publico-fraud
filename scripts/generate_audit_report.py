#!/usr/bin/env python3
"""
Audit Report Generator: Generates an official "Minuta de Auditoría" for a given supplier 
based on the fraud engine alerts in the database.
Usage: python scripts/generate_audit_report.py --rut <SUPPLIER_RUT>
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import SessionLocal, Party, Alert, Procurement  # type: ignore
from sqlalchemy import func  # type: ignore

def compute_dv(rut_body: str) -> str:
    """Compute check digit for a Chilean RUT body (Modulo 11)."""
    total = 0
    multiplier = 2
    for digit in reversed(rut_body):
        total += int(digit) * multiplier
        multiplier = multiplier % 7 + 2
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    elif remainder == 10:
        return "K"
    else:
        return str(remainder)

def normalize_rut(rut: str) -> str:
    """Ensure RUT is just the upper clean alphanumeric string without dots or dashes."""
    return rut.replace(".", "").replace("-", "").strip().upper()

def generate_report(raw_rut: str):
    rut = normalize_rut(raw_rut)
    db = SessionLocal()
    
    party = db.query(Party).filter(Party.rut == rut).first()
    if not party:
        print(f"Error: Proveedor con RUT '{rut}' no encontrado en la base de datos.")
        sys.exit(1)

    alerts = db.query(Alert).filter(Alert.supplier_rut == rut).all()
    if not alerts:
        print(f"Información: El proveedor {party.name} ({rut}) no registra alertas en el sistema.")
        sys.exit(0)

    total_alerts = len(alerts)
    crit_alerts = sum(1 for a in alerts if a.severity == 'alta')
    mod_alerts = sum(1 for a in alerts if a.severity == 'media')
    low_alerts = sum(1 for a in alerts if a.severity == 'baja')

    total_amount = sum(a.amount_involved for a in alerts if a.amount_involved)

    # Compile the Markdown report
    report = []
    report.append(f"# MINUTA DE INTELIGENCIA Y AUDITORÍA")
    report.append(f"**Fecha de Emisión:** {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    report.append(f"**Clasificación:** CONFIDENCIAL - USO INTERNO")
    report.append(f"**Sujeto de Interés:** {party.name} (RUT: {party.rut})")
    
    if party.sii_activity_code:
        report.append(f"**Actividad SII:** {party.sii_activity_code}")
    if party.sii_start_date:
        report.append(f"**Inicio Actividades:** {party.sii_start_date.strftime('%d-%m-%Y')}")
    
    report.append("\n---")
    report.append("## 1. RESUMEN EJECUTIVO DE RIESGO")
    report.append(f"El sistema de detección ha levantado **{total_alerts} alertas** asociadas a este proveedor, "
                  f"involucrando un monto fiscal aproximado de **${total_amount:,.0f} CLP** bajo observación.")
    
    report.append("\n**Distribución de Severidad:**")
    report.append(f"- Críticas: {crit_alerts}")
    report.append(f"- Moderadas: {mod_alerts}")
    report.append(f"- Bajas: {low_alerts}")

    report.append("\n---")
    report.append("## 2. DETALLE DE HALLAZGOS Y PATRONES")
    
    # Group alerts by type
    alerts_by_type = {}
    for a in alerts:
        if a.alert_type not in alerts_by_type:
            alerts_by_type[a.alert_type] = []
        alerts_by_type[a.alert_type].append(a)

    for atype, alist in alerts_by_type.items():
        report.append(f"\n### PATRÓN: {atype}")
        report.append(f"Se detectaron {len(alist)} ocurrencias de este patrón.")
        for idx, a in enumerate(alist[:5]):  # type: ignore
            report.append(f"\n**Caso #{idx+1}**: {a.title} ({a.severity.upper()})")
            report.append(f"> {a.description}")
            if a.amount_involved:
                report.append(f"> Monto Involucrado: ${a.amount_involved:,.0f} CLP")
            if a.buyer_name:
                report.append(f"> Organismo Comprador: {a.buyer_name}")
            report.append(f"> ID Licitación/Proceso: {a.ocid}")
            
        if len(alist) > 5:
            report.append(f"\n*(...y {len(alist) - 5} casos adicionales omitidos por brevedad)*")

    report.append("\n---")
    report.append("## 3. RECOMENDACIÓN DE ACCIÓN")
    if crit_alerts > 0:
        report.append("**ACCIÓN INMEDIATA REQUERIDA:** Se sugiere congelar preventivamente adjudicaciones pendientes, "
                      "solicitar antecedentes adicionales de malla societaria mediante Registro de Empresas y Sociedades (RES), "
                      "y derivar a auditoría interna o Contraloría.")
    elif mod_alerts > 0:
        report.append("**ACCIÓN RECOMENDADA:** Aumentar nivel de escrutinio en futuras participaciones de este proveedor. "
                      "Verificar validez de documentación y constatar no consanguinidad con funcionarios clave.")
    else:
        report.append("**MONITOREO REGULAR:** Las alertas son de baja intensidad. Mantener en sistema de vigilancia pasiva.")
        
    report_text = "\n".join(report)
    print(report_text)
    
    # Optionally save to file
    out_file = f"minuta_{rut}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n[+] Reporte guardado en: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Generar Minuta de Auditoría")
    parser.add_argument("--rut", required=True, help="RUT del proveedor a auditar (ej: 76123456-K)")
    args = parser.parse_args()
    
    generate_report(args.rut)

if __name__ == "__main__":
    main()
