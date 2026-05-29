# ============================================================
#   BOT DE TRADING — SISTEMA DE EMAILS
#   Archivo: email_bot.py
#   Descripción: Envía reportes HTML por Gmail.
#                Usa SMTP seguro (TLS).
# ============================================================

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import config


def enviar_email(asunto: str, cuerpo_html: str) -> bool:
    """
    Envía un email HTML.

    asunto     : Asunto del correo
    cuerpo_html: Contenido en HTML
    Devuelve True si se envió, False si hubo error.
    """
    try:
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = asunto
        mensaje["From"]    = config.EMAIL_REMITENTE
        mensaje["To"]      = config.EMAIL_DESTINATARIO

        parte_html = MIMEText(cuerpo_html, "html", "utf-8")
        mensaje.attach(parte_html)

        with smtplib.SMTP("smtp.gmail.com", 587) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.login(config.EMAIL_REMITENTE, config.EMAIL_CONTRASENA)
            servidor.sendmail(
                config.EMAIL_REMITENTE,
                config.EMAIL_DESTINATARIO,
                mensaje.as_string()
            )

        print(f"[Email] ✅ Enviado: {asunto}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[Email] ❌ Error de autenticación — revisa EMAIL_CONTRASENA en config.py")
        print("[Email]    Necesitas una 'Contraseña de aplicación' de Google, no tu contraseña normal")
        return False

    except smtplib.SMTPException as e:
        print(f"[Email] ❌ Error SMTP: {e}")
        return False

    except Exception as e:
        print(f"[Email] ❌ Error inesperado: {e}")
        return False


def enviar_alerta(titulo: str, mensaje: str) -> bool:
    """Envía una alerta simple (texto, no HTML complejo)."""
    cuerpo = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px">
    <div style="max-width:500px;margin:auto;background:white;border-radius:10px;
                padding:20px;border-left:4px solid #e53935">
        <h2 style="color:#e53935">🚨 {titulo}</h2>
        <p>{mensaje}</p>
        <p style="color:#aaa;font-size:12px">{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
    </div>
    </body></html>
    """
    return enviar_email(f"🚨 {titulo}", cuerpo)


# ════════════════════════════════════════════
# TEST RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    print("[Email] Enviando email de prueba...")
    resultado = enviar_email(
        "✅ Bot de Trading — Test de email",
        """
        <html><body style="font-family:Arial,sans-serif;padding:20px">
        <h2>✅ El sistema de email funciona correctamente</h2>
        <p>Si recibes este mensaje, el bot puede enviarte reportes.</p>
        </body></html>
        """
    )
    print(f"[Email] Resultado: {'✅ OK' if resultado else '❌ Falló'}")
