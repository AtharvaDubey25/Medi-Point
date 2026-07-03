from datetime import date, timedelta, datetime
from typing import Optional
from prisma import Prisma
from prisma.models import Appointment as AppointmentModel
import asyncio

from app.services.notification_service import notify_booking_confirmation

ACTIVE_APPOINTMENT_STATUSES = ["SCHEDULED", "RESCHEDULED"]


def _time_to_minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Invalid time")
    return hour * 60 + minute


def _format_minutes(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _date_string(value) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value).split("T", 1)[0].split(" ", 1)[0]


async def _available_end_time(
    db: Prisma,
    doctor_profile,
    doctor_user_id: int,
    appointment_date: date,
    start_time: str,
    exclude_appointment_id: int | None = None,
) -> Optional[str]:
    if appointment_date < date.today():
        return None
    if doctor_profile.is_on_leave:
        return None

    if any(leave.leave_date.date() == appointment_date for leave in doctor_profile.leaves):
        return None

    day_of_week = appointment_date.weekday()
    availabilities = [
        availability
        for availability in doctor_profile.availability
        if availability.day_of_week == day_of_week and availability.is_available
    ]
    if not availabilities:
        return None

    try:
        start_total = _time_to_minutes(start_time)
    except (TypeError, ValueError):
        return None

    slot_min = doctor_profile.slot_duration_minutes
    end_total = start_total + slot_min
    matching_availability = None

    for availability in availabilities:
        try:
            availability_start = _time_to_minutes(availability.start_time)
            availability_end = _time_to_minutes(availability.end_time)
        except (TypeError, ValueError):
            continue

        aligns_to_slot = (start_total - availability_start) % slot_min == 0
        if availability_start <= start_total and end_total <= availability_end and aligns_to_slot:
            matching_availability = availability
            break

    if not matching_availability:
        return None

    apt_datetime = datetime.combine(appointment_date, datetime.min.time())
    where = {
        "doctor_id": doctor_user_id,
        "appointment_date": apt_datetime,
        "start_time": start_time,
        "status": {"in": ACTIVE_APPOINTMENT_STATUSES},
    }
    if exclude_appointment_id is not None:
        where["id"] = {"not": exclude_appointment_id}

    existing = await db.appointment.find_first(where=where)
    if existing:
        return None

    return _format_minutes(end_total)


async def book_appointment(
    db: Prisma,
    patient_id: int,
    doctor_id: int,
    appointment_date: date,
    start_time: str,
) -> Optional[AppointmentModel]:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with db.tx() as tx:
                doctor_profile = await tx.doctorprofile.find_first(
                    where={"user_id": doctor_id},
                    include={"availability": True, "leaves": True},
                )
                if not doctor_profile:
                    return None

                end_time = await _available_end_time(
                    tx, doctor_profile, doctor_id, appointment_date, start_time,
                )
                if not end_time:
                    return None

                apt_datetime = datetime.combine(appointment_date, datetime.min.time())
                appointment = await tx.appointment.create(
                    data={
                        "patient_id": patient_id,
                        "doctor_id": doctor_id,
                        "appointment_date": apt_datetime,
                        "start_time": start_time,
                        "end_time": end_time,
                        "status": "SCHEDULED",
                    },
                    include={
                        "patient": True,
                        "doctor": {"include": {"doctor_profile": True}},
                    },
                )
            asyncio.create_task(notify_booking_confirmation(db, appointment))
            return appointment
        except Exception as e:
            if "appointment_active_slot_unique" in str(e) or "Unique constraint" in str(e):
                return None
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1 * (attempt + 1))

    return None


async def cancel_appointment(db: Prisma, appointment_id: int, reason: Optional[str] = None):
    appointment = await db.appointment.find_first(
        where={"id": appointment_id},
        include={
            "patient": True,
            "doctor": {"include": {"doctor_profile": True}},
        },
    )
    if not appointment:
        return None

    updated = await db.appointment.update(
        where={"id": appointment_id},
        data={
            "status": "CANCELLED",
            "cancellation_reason": reason,
        },
    )

    from app.services.notification_service import notify_cancellation

    from app.services.calendar_service import delete_calendar_event
    if appointment.google_calendar_event_id:
        asyncio.create_task(delete_calendar_event(db, appointment.patient_id, appointment.google_calendar_event_id))
    if appointment.doctor_calendar_event_id:
        asyncio.create_task(delete_calendar_event(db, appointment.doctor_id, appointment.doctor_calendar_event_id))

    asyncio.create_task(notify_cancellation(db, appointment, reason))
    return updated

async def reschedule_appointment(
    db: Prisma,
    appointment_id: int,
    new_date: date,
    new_start_time: str,
):
    appointment = await db.appointment.find_first(where={"id": appointment_id})
    if not appointment:
        return None
    try:
        async with db.tx() as tx:
            doctor_profile = await tx.doctorprofile.find_first(
                where={"user_id": appointment.doctor_id},
                include={"availability": True, "leaves": True},
            )
            if not doctor_profile:
                return None

            new_end_time = await _available_end_time(
                tx,
                doctor_profile,
                appointment.doctor_id,
                new_date,
                new_start_time,
                exclude_appointment_id=appointment_id,
            )
            if not new_end_time:
                return None

            new_apt_datetime = datetime.combine(new_date, datetime.min.time())
            updated = await tx.appointment.update(
                where={"id": appointment_id},
                data={
                    "appointment_date": new_apt_datetime,
                    "start_time": new_start_time,
                    "end_time": new_end_time,
                    "status": "RESCHEDULED",
                },
                include={
                    "patient": True,
                    "doctor": {"include": {"doctor_profile": True}},
                },
            )
    except Exception as e:
        if "appointment_active_slot_unique" in str(e) or "Unique constraint" in str(e):
            return None
        raise

    from app.services.calendar_service import update_calendar_event
    if appointment.google_calendar_event_id:
        asyncio.create_task(update_calendar_event(
            db, updated.patient_id,
            updated.google_calendar_event_id, updated,
        ))
    if appointment.doctor_calendar_event_id:
        asyncio.create_task(update_calendar_event(
            db, updated.doctor_id,
            updated.doctor_calendar_event_id, updated,
        ))

    return updated


async def notify_affected_patients(
    db: Prisma,
    doctor_user_id: int,
    leave_date: date,
):
    leave_datetime = datetime.combine(leave_date, datetime.min.time())
    appointments = await db.appointment.find_many(
        where={
            "doctor_id": doctor_user_id,
            "appointment_date": leave_datetime,
            "status": {"in": ACTIVE_APPOINTMENT_STATUSES},
        },
        include={"patient": True, "doctor": True},
    )

    from app.services.notification_service import notify_leave_cancellation
    for apt in appointments:
        await db.appointment.update(
            where={"id": apt.id},
            data={
                "status": "CANCELLED",
                "cancellation_reason": f"Doctor on leave for {leave_date.isoformat()}",
            },
        )
        asyncio.create_task(notify_leave_cancellation(db, apt))


async def get_patient_appointments(db: Prisma, patient_id: int, status_filter: Optional[str] = None):
    where = {"patient_id": patient_id}
    if status_filter:
        where["status"] = status_filter

    appointments = await db.appointment.find_many(
        where=where,
        include={
            "patient": True,
            "doctor": True,
            "symptom_form": True,
        },
        order={"created_at": "desc"},
    )
    return _format_appointments(appointments)


async def get_doctor_appointments(db: Prisma, doctor_id: int, status_filter: Optional[str] = None):
    where = {"doctor_id": doctor_id}
    if status_filter:
        where["status"] = status_filter

    appointments = await db.appointment.find_many(
        where=where,
        include={
            "patient": True,
            "doctor": True,
            "symptom_form": True,
        },
        order={"appointment_date": "desc"},
    )
    return _format_appointments(appointments)


def _format_appointments(appointments):
    result = []
    for a in appointments:
        result.append({
            "id": a.id,
            "patient_id": a.patient_id,
            "doctor_id": a.doctor_id,
            "patient_name": a.patient.full_name,
            "doctor_name": a.doctor.full_name,
            "appointment_date": _date_string(a.appointment_date),
            "start_time": a.start_time,
            "end_time": a.end_time,
            "status": a.status,
            "cancellation_reason": a.cancellation_reason,
            "created_at": a.created_at.isoformat(),
            "has_symptom_form": a.symptom_form is not None,
            "has_pre_visit_summary": a.symptom_form is not None and a.symptom_form.pre_visit_summary is not None,
            "has_post_visit_summary": a.symptom_form is not None and a.symptom_form.post_visit_summary is not None,
        })
    return result
