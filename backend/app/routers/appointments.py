from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Prisma
from typing import Optional
import json

from app.prisma_client import get_db
from app.schemas.appointment import AppointmentBook, AppointmentReschedule, AppointmentResponse, AppointmentListResponse
from app.dependencies.auth import get_current_user, get_current_patient, get_current_doctor
from app.services.appointment_service import (
    book_appointment, cancel_appointment, reschedule_appointment,
    get_patient_appointments, get_doctor_appointments,
)
from app.services.llm_service import generate_pre_visit_summary

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


def _date_string(value) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value).split("T", 1)[0].split(" ", 1)[0]


@router.post("/book", status_code=201)
async def book(
    data: AppointmentBook,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_patient),
):
    from datetime import date
    try:
        apt_date = date.fromisoformat(data.appointment_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    appointment = await book_appointment(
        db, current_user.id, data.doctor_id, apt_date, data.start_time,
    )
    if not appointment:
        raise HTTPException(status_code=409, detail="Slot not available or already booked")

    if data.symptoms.strip():
        summary = await generate_pre_visit_summary(data.symptoms)
        await db.symptomform.create(data={
            "appointment_id": appointment.id,
            "symptoms_text": data.symptoms,
            "pre_visit_summary": json.dumps(summary),
        })

    return {"message": "Appointment booked successfully", "appointment_id": appointment.id}


@router.post("/{appointment_id}/cancel")
async def cancel(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.patient_id != current_user.id and apt.doctor_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorised to cancel this appointment")

    updated = await cancel_appointment(db, appointment_id, reason)
    return {"message": "Appointment cancelled", "appointment_id": updated.id}


@router.put("/{appointment_id}/reschedule")
async def reschedule(
    appointment_id: int,
    data: AppointmentReschedule,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_patient),
):
    from datetime import date
    try:
        new_date = date.fromisoformat(data.appointment_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt or apt.patient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Cannot reschedule a cancelled appointment")

    updated = await reschedule_appointment(db, appointment_id, new_date, data.start_time)
    if not updated:
        raise HTTPException(status_code=409, detail="New slot not available")

    return {"message": "Appointment rescheduled", "appointment_id": updated.id}


@router.get("/my", response_model=AppointmentListResponse)
async def list_my_appointments(
    status: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "PATIENT":
        appointments = await get_patient_appointments(db, current_user.id, status)
    elif current_user.role == "DOCTOR":
        appointments = await get_doctor_appointments(db, current_user.id, status)
    else:
        appointments = []

    return AppointmentListResponse(appointments=appointments, total=len(appointments))


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    apt = await db.appointment.find_first(
        where={"id": appointment_id},
        include={"patient": True, "doctor": True, "symptom_form": True},
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.patient_id != current_user.id and apt.doctor_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorised")

    return {
        "id": apt.id,
        "patient_id": apt.patient_id,
        "doctor_id": apt.doctor_id,
        "patient_name": apt.patient.full_name,
        "doctor_name": apt.doctor.full_name,
        "appointment_date": _date_string(apt.appointment_date),
        "start_time": apt.start_time,
        "end_time": apt.end_time,
        "status": apt.status,
        "cancellation_reason": apt.cancellation_reason,
        "created_at": apt.created_at.isoformat(),
        "has_symptom_form": apt.symptom_form is not None,
        "has_pre_visit_summary": apt.symptom_form is not None and apt.symptom_form.pre_visit_summary is not None,
        "has_post_visit_summary": apt.symptom_form is not None and apt.symptom_form.post_visit_summary is not None,
    }
