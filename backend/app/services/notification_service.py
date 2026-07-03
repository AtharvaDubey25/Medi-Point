from prisma import Prisma
from app.services.email_service import send_email, format_appointment_email
from app.services.calendar_service import create_calendar_event, delete_calendar_event


def _appointment_date_string(appointment) -> str:
    raw_date = appointment.appointment_date
    if hasattr(raw_date, "date"):
        return raw_date.date().isoformat()
    return str(raw_date).split("T", 1)[0].split(" ", 1)[0]


async def notify_booking_confirmation(db: Prisma, appointment):
    patient_email_data = format_appointment_email(
        appointment,
        appointment.patient.full_name,
        appointment.doctor.full_name,
    )

    doctor_name = appointment.doctor.full_name
    patient_name = appointment.patient.full_name
    date_str = _appointment_date_string(appointment)

    doctor_email_data = {
        "subject": f"New Appointment - {patient_name}",
        "body": (
            f"Dear Dr. {doctor_name},\n\n"
            f"A new appointment has been booked.\n\n"
            f"Patient: {patient_name}\n"
            f"Date: {date_str}\n"
            f"Time: {appointment.start_time} - {appointment.end_time}\n\n"
            f"Please check the portal for symptom details.\n\n"
            f"Thank you,\nMedi Point"
        ),
    }

    await send_email(
        appointment.patient.email,
        patient_email_data["subject"],
        patient_email_data["body"],
        appointment.patient.full_name,
    )
    await send_email(
        appointment.doctor.email,
        doctor_email_data["subject"],
        doctor_email_data["body"],
        appointment.doctor.full_name,
    )

    patient_event_id = await create_calendar_event(db, appointment.patient_id, appointment)
    doctor_event_id = await create_calendar_event(db, appointment.doctor_id, appointment)

    update_data = {}
    if patient_event_id:
        update_data["google_calendar_event_id"] = patient_event_id
    if doctor_event_id:
        update_data["doctor_calendar_event_id"] = doctor_event_id
    if update_data:
        await db.appointment.update(
            where={"id": appointment.id},
            data=update_data,
        )


async def notify_cancellation(db: Prisma, appointment, reason: str = None):
    date_str = _appointment_date_string(appointment)
    reason_text = f"\nReason: {reason}" if reason else ""

    patient_body = (
        f"Dear {appointment.patient.full_name},\n\n"
        f"Your appointment has been cancelled.\n\n"
        f"Doctor: Dr. {appointment.doctor.full_name}\n"
        f"Date: {date_str}\n"
        f"Time: {appointment.start_time} - {appointment.end_time}"
        f"{reason_text}\n\n"
        f"Please book a new appointment at your convenience.\n\n"
        f"Thank you,\nMedi Point"
    )

    doctor_body = (
        f"Dear Dr. {appointment.doctor.full_name},\n\n"
        f"The following appointment has been cancelled.\n\n"
        f"Patient: {appointment.patient.full_name}\n"
        f"Date: {date_str}\n"
        f"Time: {appointment.start_time} - {appointment.end_time}"
        f"{reason_text}\n\n"
        f"Thank you,\nMedi Point"
    )

    await send_email(
        appointment.patient.email,
        "Appointment Cancelled",
        patient_body,
        appointment.patient.full_name,
    )
    await send_email(
        appointment.doctor.email,
        "Appointment Cancelled",
        doctor_body,
        appointment.doctor.full_name,
    )


async def notify_leave_cancellation(db: Prisma, appointment):
    date_str = _appointment_date_string(appointment)

    body = (
        f"Dear {appointment.patient.full_name},\n\n"
        f"Unfortunately, your appointment with Dr. {appointment.doctor.full_name} "
        f"on {date_str} at {appointment.start_time} has been cancelled "
        f"because the doctor is on leave.\n\n"
        f"We apologise for the inconvenience. Please book a new appointment.\n\n"
        f"Thank you,\nMedi Point"
    )

    await send_email(
        appointment.patient.email,
        "Appointment Cancelled - Doctor on Leave",
        body,
        appointment.patient.full_name,
    )

    if appointment.google_calendar_event_id:
        await delete_calendar_event(db, appointment.patient_id, appointment.google_calendar_event_id)
    if appointment.doctor_calendar_event_id:
        await delete_calendar_event(db, appointment.doctor_id, appointment.doctor_calendar_event_id)


async def send_medication_reminder(db: Prisma, medication, patient_email: str, patient_name: str):
    body = (
        f"Dear {patient_name},\n\n"
        f"Medication Reminder:\n\n"
        f"Medication: {medication.medication_name}\n"
        f"Dosage: {medication.dosage}\n"
        f"Frequency: {medication.frequency}\n\n"
        f"Please take your medication as prescribed.\n\n"
        f"Thank you,\nMedi Point"
    )

    await send_email(
        patient_email,
        f"Medication Reminder - {medication.medication_name}",
        body,
        patient_name,
    )


async def send_appointment_reminder(db: Prisma, appointment):
    date_str = _appointment_date_string(appointment)

    patient_body = (
        f"Dear {appointment.patient.full_name},\n\n"
        f"This is a reminder for your upcoming appointment.\n\n"
        f"Doctor: Dr. {appointment.doctor.full_name}\n"
        f"Date: {date_str}\n"
        f"Time: {appointment.start_time} - {appointment.end_time}\n\n"
        f"Please arrive on time.\n\n"
        f"Thank you,\nMedi Point"
    )

    doctor_body = (
        f"Dear Dr. {appointment.doctor.full_name},\n\n"
        f"This is a reminder for your upcoming appointment.\n\n"
        f"Patient: {appointment.patient.full_name}\n"
        f"Date: {date_str}\n"
        f"Time: {appointment.start_time} - {appointment.end_time}\n\n"
        f"Thank you,\nMedi Point"
    )

    await send_email(
        appointment.patient.email,
        "Appointment Reminder",
        patient_body,
        appointment.patient.full_name,
    )
    await send_email(
        appointment.doctor.email,
        "Appointment Reminder",
        doctor_body,
        appointment.doctor.full_name,
    )
