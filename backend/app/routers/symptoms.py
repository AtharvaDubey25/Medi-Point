from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma
import json
import asyncio

from app.prisma_client import get_db
from app.schemas.symptom import SymptomFormSubmit, PostVisitData, SymptomFormResponse
from app.dependencies.auth import get_current_user, get_current_patient, get_current_doctor
from app.services.llm_service import generate_pre_visit_summary, generate_post_visit_summary

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])


@router.post("/appointment/{appointment_id}", status_code=201)
async def submit_symptoms(
    appointment_id: int,
    data: SymptomFormSubmit,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_patient),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt or apt.patient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.status not in ("SCHEDULED", "RESCHEDULED"):
        raise HTTPException(status_code=400, detail="Can only submit symptoms for active scheduled or rescheduled appointments")

    existing = await db.symptomform.find_first(where={"appointment_id": appointment_id})
    if existing:
        raise HTTPException(status_code=400, detail="Symptoms already submitted")

    summary = await generate_pre_visit_summary(data.symptoms)

    symptom_form = await db.symptomform.create(data={
        "appointment_id": appointment_id,
        "symptoms_text": data.symptoms,
        "pre_visit_summary": json.dumps(summary),
    })

    return {"message": "Symptoms submitted", "id": symptom_form.id, "summary": summary}


@router.get("/appointment/{appointment_id}", response_model=SymptomFormResponse)
async def get_symptom_form(
    appointment_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.patient_id != current_user.id and apt.doctor_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorised")

    symptom_form = await db.symptomform.find_first(
        where={"appointment_id": appointment_id},
    )
    if not symptom_form:
        raise HTTPException(status_code=404, detail="Symptom form not found")

    return symptom_form


@router.get("/appointment/{appointment_id}/pre-visit-summary")
async def get_pre_visit_summary(
    appointment_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.doctor_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only the doctor can view pre-visit summary")

    symptom_form = await db.symptomform.find_first(
        where={"appointment_id": appointment_id},
    )
    if not symptom_form or not symptom_form.pre_visit_summary:
        raise HTTPException(status_code=404, detail="Pre-visit summary not available")

    try:
        summary = json.loads(symptom_form.pre_visit_summary)
    except json.JSONDecodeError:
        summary = {"raw": symptom_form.pre_visit_summary}

    return {
        "appointment_id": appointment_id,
        "symptoms": symptom_form.symptoms_text,
        "summary": summary,
    }


@router.post("/appointment/{appointment_id}/post-visit")
async def submit_post_visit(
    appointment_id: int,
    data: PostVisitData,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt or apt.doctor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Appointment not found")

    symptom_form = await db.symptomform.find_first(where={"appointment_id": appointment_id})
    if not symptom_form:
        raise HTTPException(status_code=400, detail="No symptom form found. Patient must submit symptoms first.")

    llm_summary = await generate_post_visit_summary(data.notes, data.prescription)

    await db.symptomform.update(
        where={"id": symptom_form.id},
        data={
            "post_visit_notes": data.notes,
            "post_visit_prescription": data.prescription,
            "post_visit_summary": json.dumps(llm_summary),
        },
    )

    await db.appointment.update(
        where={"id": appointment_id},
        data={"status": "COMPLETED"},
    )

    if data.medications:
        for med in data.medications:
            start_date_raw = med.get("start_date")
            parsed_date = datetime.combine(datetime.utcnow().date(), datetime.min.time())
            if start_date_raw:
                try:
                    parsed_date = datetime.strptime(start_date_raw, "%Y-%m-%d")
                except (ValueError, TypeError):
                    parsed_date = datetime.combine(datetime.utcnow().date(), datetime.min.time())
            await db.medication.create(data={
                "appointment_id": appointment_id,
                "medication_name": med.get("name", ""),
                "dosage": med.get("dosage", ""),
                "frequency": med.get("frequency", ""),
                "duration_days": med.get("duration_days"),
                "start_date": parsed_date,
            })

    return {
        "message": "Post-visit data submitted",
        "patient_summary": llm_summary,
    }


@router.get("/appointment/{appointment_id}/post-visit-summary")
async def get_post_visit_summary(
    appointment_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_user),
):
    apt = await db.appointment.find_first(where={"id": appointment_id})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.patient_id != current_user.id and apt.doctor_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorised to view this post-visit summary")

    symptom_form = await db.symptomform.find_first(
        where={"appointment_id": appointment_id},
    )
    if not symptom_form or not symptom_form.post_visit_summary:
        raise HTTPException(status_code=404, detail="Post-visit summary not available")

    try:
        summary = json.loads(symptom_form.post_visit_summary)
    except json.JSONDecodeError:
        summary = {"raw": symptom_form.post_visit_summary}

    return {
        "appointment_id": appointment_id,
        "summary": summary,
        "prescription": symptom_form.post_visit_prescription,
    }
