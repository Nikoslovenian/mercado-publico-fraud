import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logger = logging.getLogger(__name__)

def send_critical_alerts_email(sys_stats):
    """
    Envía una notificación por correo si el motor de fraude detecta alertas CRÍTICAS.
    """
    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    recipient = os.environ.get("ALERT_RECIPIENT", "")

    if not all([smtp_server, smtp_user, smtp_pass, recipient]):
        logger.warning("Credenciales SMTP no configuradas. Omitiendo notificación por correo electrónico.")
        return

    critical_count = sys_stats.get("by_severity", {}).get("alta", 0)
    
    # Sólo enviar alertas si hay nuevas críticas (ALTA)
    if critical_count == 0:
        logger.info("No se hallaron alertas de severidad crítica. No se enviará notificación.")
        return

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg['Subject'] = f"🚨 [ALERTA CRÍTICA SOC] {critical_count} Casos Graves de Fraude Detectados"

    # Construir cuerpo del correo usando HTML limpio simulando un poco el estilo del Dashboard
    body = f"""
    <html>
      <body style="font-family: 'Courier New', monospace; color: #333; background: #fdfdfd; padding: 20px;">
        <h2 style="color: #ff3355; border-bottom: 2px solid #ff3355; padding-bottom: 5px;">
          URGENTE: RIESGO DE FRAUDE EN MERCADO PÚBLICO
        </h2>
        <p>El motor inteligente ha concluido su ciclo de auditoría y ha marcado nuevas anomalías graves.</p>
        
        <div style="background: #f4f4f4; padding: 15px; border-left: 4px solid #ffaa00; margin: 20px 0;">
            <h3 style="margin-top: 0;">Resumen del Análisis OCDS:</h3>
            <ul style="list-style-type: none; padding-left: 0;">
              <li style="margin-bottom: 5px;">🔴 <strong>Alertas Críticas (ALTA severidad):</strong> <span style="font-size: 18px; color: #ff3355;">{critical_count}</span></li>
              <li style="margin-bottom: 5px;">🟡 Alertas Moderadas (MEDIA): {sys_stats.get("by_severity", {}).get("media", 0)}</li>
              <li>🔵 Total General Evaluado: {sys_stats.get('total_alerts', 0)} expedientes</li>
            </ul>
        </div>
        
        <h3>Distribución por Vector de Fraude:</h3>
        <ul>
          {"".join(f"<li><strong>{k}:</strong> {v} detecciones</li>" for k, v in sys_stats.get("by_type", {}).items())}
        </ul>
        
        <p style="margin-top: 30px;">
          <a href="http://localhost:5173/alerts?severity=alta" 
             style="background: #00e5a0; color: #000; padding: 10px 15px; text-decoration: none; font-weight: bold; border-radius: 4px;">
            ABRIR CENTRO DE OPERACIONES (SOC)
          </a>
        </p>
        
        <br><br>
        <hr style="border: 0; border-top: 1px solid #ccc;">
        <p style="font-size: 11px; color: #888;">Mensaje automatizado del Centro Global de Detección de Fraudes - Operación MP 2025.</p>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'html'))

    logger.info(f"Intentando enviar notificación de {critical_count} alerta(s) crítica(s) a {recipient}...")

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Notificación enviada exitosamente a {recipient}")
    except Exception as e:
        logger.error(f"Fallo al enviar correo mediante SMTP: {e}")

