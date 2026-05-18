from __future__ import annotations

from src.application.notifications.email_service import EmailMessage


def verification_email(
    to: str,
    token: str,
    landing_base_url: str,
    tenant_name: str = "",
) -> EmailMessage:
    verify_url = f"{landing_base_url.rstrip('/')}/verificar/{token}"
    greeting = f"Hola{f', {tenant_name}' if tenant_name else ''}!"

    html_body = f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px 16px;color:#1a1a2e">
  <h1 style="font-size:24px;font-weight:700;margin-bottom:8px">Verifica tu correo</h1>
  <p style="margin:0 0 16px;color:#555">{greeting}</p>
  <p style="margin:0 0 24px;color:#555">
    Gracias por registrarte. Haz clic en el botón para activar tu cuenta y acceder al wizard de configuración.
  </p>
  <a href="{verify_url}"
     style="display:inline-block;background:#1a1a2e;color:#fff;text-decoration:none;
            padding:12px 28px;border-radius:6px;font-weight:600;font-size:15px">
    Verificar mi cuenta
  </a>
  <p style="margin:24px 0 0;font-size:12px;color:#999">
    El enlace expira en 24 horas.<br>
    Si no creaste esta cuenta puedes ignorar este mensaje.<br>
    O copia este enlace en tu navegador:<br>
    <a href="{verify_url}" style="color:#999;word-break:break-all">{verify_url}</a>
  </p>
</body>
</html>
""".strip()

    text_body = (
        f"{greeting}\n\n"
        "Verifica tu cuenta de Agente Citas haciendo clic en el enlace:\n\n"
        f"{verify_url}\n\n"
        "El enlace expira en 24 horas.\n"
        "Si no creaste esta cuenta, ignora este mensaje."
    )

    return EmailMessage(
        to=to,
        subject="Verifica tu correo — Agente Citas",
        html_body=html_body,
        text_body=text_body,
        tags=["verification"],
    )
