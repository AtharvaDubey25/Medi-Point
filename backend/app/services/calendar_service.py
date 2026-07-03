from datetime import datetime, timedelta
from typing import Optional
from prisma import Prisma

from app.config import settings


def _appointment_date_string(appointment) -> str:
    raw_date = appointment.appointment_date
    if hasattr(raw_date, "date"):
        return raw_date.date().isoformat()
    return str(raw_date).split("T", 1)[0].split(" ", 1)[0]


async def create_calendar_event(
    db: Prisma,
    user_id: int,
    appointment,
):
    token = await _get_calendar_token(db, user_id)
    if not token:
        return None

    try:
        service = _build_service(token)
        date_str = _appointment_date_string(appointment)
        start_dt = f"{date_str}T{appointment.start_time}:00"
        end_dt = f"{date_str}T{appointment.end_time}:00"

        event = {
            "summary": f"Appointment with {appointment.patient.full_name if user_id == appointment.doctor_id else 'Dr. ' + appointment.doctor.full_name}",
            "description": f"Medi Point Appointment\nStatus: {appointment.status}",
            "start": {
                "dateTime": start_dt,
                "timeZone": settings.CALENDAR_TIMEZONE,
            },
            "end": {
                "dateTime": end_dt,
                "timeZone": settings.CALENDAR_TIMEZONE,
            },
        }

        created = service.events().insert(calendarId="primary", body=event).execute()
        return created.get("id")
    except Exception as e:
        print(f"Google Calendar create event failed: {e}")
        return None


async def update_calendar_event(
    db: Prisma,
    user_id: int,
    event_id: str,
    appointment,
):
    token = await _get_calendar_token(db, user_id)
    if not token:
        return

    try:
        service = _build_service(token)
        date_str = _appointment_date_string(appointment)

        event = {
            "summary": f"Appointment with {appointment.patient.full_name if user_id == appointment.doctor_id else 'Dr. ' + appointment.doctor.full_name}",
            "start": {
                "dateTime": f"{date_str}T{appointment.start_time}:00",
                "timeZone": settings.CALENDAR_TIMEZONE,
            },
            "end": {
                "dateTime": f"{date_str}T{appointment.end_time}:00",
                "timeZone": settings.CALENDAR_TIMEZONE,
            },
        }

        service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
    except Exception as e:
        print(f"Google Calendar update event failed: {e}")


async def delete_calendar_event(
    db: Prisma,
    user_id: int,
    event_id: str,
):
    token = await _get_calendar_token(db, user_id)
    if not token:
        return

    try:
        service = _build_service(token)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception as e:
        print(f"Google Calendar delete event failed: {e}")


async def _get_calendar_token(db: Prisma, user_id: int) -> Optional[str]:
    user = await db.user.find_first(where={"id": user_id})
    if user and user.google_calendar_token:
        return user.google_calendar_token
    return None


def _build_service(access_token: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(token=access_token)
    return build("calendar", "v3", credentials=creds)
