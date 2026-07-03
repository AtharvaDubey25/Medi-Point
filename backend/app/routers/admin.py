from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Prisma
from typing import Optional

from app.prisma_client import get_db
from app.schemas.doctor import (
    DoctorCreate, DoctorProfileUpdate, DoctorResponse,
    DoctorAvailabilityCreate, DoctorAvailabilityResponse,
    DoctorLeaveCreate, DoctorLeaveResponse,
)
from app.schemas.user import UserResponse
from app.dependencies.auth import get_current_admin
from app.services.auth_service import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _date_string(value) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value).split("T", 1)[0].split(" ", 1)[0]


@router.post("/doctors", status_code=201)
async def create_doctor(
    data: DoctorCreate,
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    existing = await db.user.find_first(where={"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await db.user.create(data={
        "email": data.email,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "phone": data.phone,
        "role": "DOCTOR",
    })

    await db.doctorprofile.create(data={
        "user_id": user.id,
        "specialization": data.specialization,
        "qualification": data.qualification,
        "experience_years": data.experience_years,
        "slot_duration_minutes": data.slot_duration_minutes,
        "bio": data.bio,
    })

    return {"message": "Doctor created", "user_id": user.id}


@router.get("/doctors", response_model=list[DoctorResponse])
async def list_doctors(
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    profiles = await db.doctorprofile.find_many(
        include={
            "user": True,
            "availability": True,
            "leaves": True,
        },
    )

    result = []
    for p in profiles:
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "full_name": p.user.full_name,
            "email": p.user.email,
            "phone": p.user.phone,
            "specialization": p.specialization,
            "qualification": p.qualification,
            "experience_years": p.experience_years,
            "slot_duration_minutes": p.slot_duration_minutes,
            "is_on_leave": p.is_on_leave,
            "bio": p.bio,
            "availability": [
                {
                    "id": a.id,
                    "day_of_week": a.day_of_week,
                    "start_time": a.start_time,
                    "end_time": a.end_time,
                    "is_available": a.is_available,
                }
                for a in p.availability
            ],
            "leaves": [
                {
                    "id": l.id,
                    "leave_date": l.leave_date.isoformat(),
                    "reason": l.reason,
                    "created_at": l.created_at.isoformat(),
                }
                for l in p.leaves
            ],
        })
    return result


@router.put("/doctors/{doctor_user_id}")
async def update_doctor(
    doctor_user_id: int,
    data: DoctorProfileUpdate,
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    profile = await db.doctorprofile.find_first(where={"user_id": doctor_user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor not found")

    profile_data = data.model_dump(exclude_none=True, exclude={"full_name", "email"})
    if profile_data:
        await db.doctorprofile.update(
            where={"id": profile.id},
            data=profile_data,
        )

    user_data = {}
    if data.full_name is not None:
        user_data["full_name"] = data.full_name
    if data.email is not None:
        existing = await db.user.find_first(where={"email": data.email, "id": {"not": doctor_user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user_data["email"] = data.email
    if user_data:
        await db.user.update(
            where={"id": doctor_user_id},
            data=user_data,
        )

    return {"message": "Doctor updated"}


@router.delete("/doctors/{doctor_user_id}")
async def delete_doctor(
    doctor_user_id: int,
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    user = await db.user.find_first(where={"id": doctor_user_id, "role": "DOCTOR"})
    if not user:
        raise HTTPException(status_code=404, detail="Doctor not found")

    await db.user.delete(where={"id": doctor_user_id})
    return {"message": "Doctor deleted"}


@router.get("/patients", response_model=list[UserResponse])
async def list_patients(
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    patients = await db.user.find_many(where={"role": "PATIENT"})
    return patients


@router.get("/appointments")
async def list_all_appointments(
    status: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
    admin=Depends(get_current_admin),
):
    where = {}
    if status:
        where["status"] = status

    appointments = await db.appointment.find_many(
        where=where,
        include={"patient": True, "doctor": True},
        order={"created_at": "desc"},
    )

    return [
        {
            "id": a.id,
            "patient_name": a.patient.full_name,
            "doctor_name": a.doctor.full_name,
            "appointment_date": _date_string(a.appointment_date),
            "start_time": a.start_time,
            "end_time": a.end_time,
            "status": a.status,
        }
        for a in appointments
    ]
