from datetime import datetime, date, time, timedelta, timezone
from prisma import Prisma

from app.services.notification_service import send_medication_reminder
from app.prisma_client import prisma


async def check_medication_reminders():
    if not prisma.is_connected():
        await prisma.connect()

    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=23)

    medications = await prisma.medication.find_many(
        where={
            "start_date": {"lte": today_start},
        },
        include={
            "appointment": {
                "include": {"patient": True},
            },
        },
    )

    for med in medications:
        if not med.start_date:
            continue

        if med.start_date.date() > today:
            continue

        if med.duration_days:
            end_date = med.start_date.date() + timedelta(days=med.duration_days)
            if end_date < today:
                continue

        if med.last_reminded_at and med.last_reminded_at > cutoff:
            continue

        patient = med.appointment.patient
        await send_medication_reminder(
            prisma, med, patient.email, patient.full_name,
        )

        await prisma.medication.update(
            where={"id": med.id},
            data={"last_reminded_at": datetime.now(timezone.utc)},
        )


async def check_appointment_reminders():
    if not prisma.is_connected():
        await prisma.connect()

    tomorrow = datetime.utcnow().date() + timedelta(days=1)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time())

    appointments = await prisma.appointment.find_many(
        where={
            "appointment_date": tomorrow_start,
            "status": {"in": ["SCHEDULED", "RESCHEDULED"]},
        },
        include={"patient": True, "doctor": True},
    )

    from app.services.notification_service import send_appointment_reminder
    for apt in appointments:
        await send_appointment_reminder(prisma, apt)
