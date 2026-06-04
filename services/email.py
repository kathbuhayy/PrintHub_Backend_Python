import aiosmtplib
from email.message import EmailMessage
from core.config import settings


async def send_otp_email(to: str, otp: str) -> None:
    if not settings.smtp_enabled:
        print(f"[EMAIL DISABLED] OTP for {to}: {otp}")
        return

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_USER
    msg["To"] = to
    msg["Subject"] = "Your PrintHub Verification Code"
    msg.set_content(
        f"Your verification code is: {otp}\n\nThis code expires in 5 minutes."
    )

    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=settings.EMAIL_USER,
        password=settings.EMAIL_PASS,
    )
