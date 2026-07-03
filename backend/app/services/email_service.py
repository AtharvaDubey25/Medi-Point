import asyncio
from typing import Optional
from app.config import settings


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    to_name: Optional[str] = None,
    retry_on_failure: bool = True,
):
    backend = settings.EMAIL_BACKEND

    try:
        if backend == "sendgrid":
            await _send_sendgrid(to_email, subject, body)
        else:
            await _send_console(to_email, subject, body, to_name)
    except Exception as e:
        if retry_on_failure:
            print(f"Failed to send email to {to_email}, queueing for retry. Error: {e}")
            from app.background.email_retry import queue_email
            queue_email(to_email, subject, body, to_name)
        else:
            raise


async def _send_console(to_email: str, subject: str, body: str, to_name: Optional[str] = None):
    name = to_name or to_email
    print(f"\n=== EMAIL (console) ===")
    print(f"To: {name} <{to_email}>")
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    print(f"=== END EMAIL ===\n")


async def _send_sendgrid(to_email: str, subject: str, body: str):
    if not settings.SENDGRID_API_KEY:
        print("SendGrid API key not configured, falling back to console")
        await _send_console(to_email, subject, body)
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=settings.EMAIL_FROM,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, sg.send, message)


def _appointment_date_string(appointment) -> str:
    raw_date = appointment.appointment_date
    if hasattr(raw_date, "date"):
        return raw_date.date().isoformat()
    return str(raw_date).split("T", 1)[0].split(" ", 1)[0]


def format_appointment_email(appointment, patient_name: str, doctor_name: str) -> dict:
    date_str = _appointment_date_string(appointment)
    return {
        "subject": f"Appointment Confirmation - Dr. {doctor_name}",
        "body": (
            f"Dear {patient_name},\n\n"
            f"Your appointment has been confirmed.\n\n"
            f"Doctor: Dr. {doctor_name}\n"
            f"Date: {date_str}\n"
            f"Time: {appointment.start_time} - {appointment.end_time}\n\n"
            f"Please arrive 10 minutes early.\n\n"
            f"Thank you,\nHealthcare Platform"
        ),
    }
