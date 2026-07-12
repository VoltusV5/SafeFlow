"""Сервис для отправки email сообщений."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_otp_email(to_email: str, code: str) -> bool:
    """Отправляет OTP-код на указанный email.

    Args:
        to_email: Адрес получателя.
        code: 6-значный OTP код.

    Returns:
        bool: True если отправлено успешно, False если ошибка.
    """
    message = EmailMessage()
    import os
    default_from = settings.smtp_user if settings.smtp_user else "auth@yourdomain.com"
    message["From"] = os.getenv("EMAIL_DEFAULT_FROM", default_from)
    
    message["To"] = to_email
    message["Subject"] = f"Ваш код для входа: {code}"
    
    html_content = f"""
    <html>
      <head></head>
      <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2>Код подтверждения</h2>
          <p>Вы (или кто-то другой) запросили вход по email в VPN.</p>
          <p>Ваш код для входа:</p>
          <h1 style="color: #4CAF50; letter-spacing: 5px;">{code}</h1>
          <p>Код действителен в течение 5 минут. Если вы не запрашивали код, просто проигнорируйте это письмо.</p>
        </div>
      </body>
    </html>
    """
    message.set_content("Ваш код для входа: " + code)
    message.add_alternative(html_content, subtype='html')

    smtp_host = os.getenv("EMAIL_HOST", settings.smtp_host)
    smtp_port = int(os.getenv("EMAIL_PORT", settings.smtp_port))
    smtp_user = os.getenv("EMAIL_HOST_USER", settings.smtp_user)
    smtp_password = os.getenv("EMAIL_HOST_PASSWORD", settings.smtp_password)
    use_tls = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")

    try:
        if use_tls:
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=True
            )
        else:
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                use_tls=False
            )
        logger.info(f"OTP sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP to {to_email}: {e}")
        return False
