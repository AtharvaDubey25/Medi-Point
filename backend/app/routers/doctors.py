from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Prisma
from typing import Optional

from app.prisma_client import get_db
from app.schemas.doctor import (
    DoctorProfileUpdate, DoctorAvailabilityCreate, DoctorLeaveCreate,
    DoctorResponse, DoctorSearchResult,
    DoctorAvailabilityResponse, DoctorLeaveResponse,
)
from app.schemas.appointment import SlotRequest, SlotResponse
from app.dependencies.auth import get_current_user, get_current_doctor
from app.services.doctor_service import generate_slots, get_doctors_by_specialization, get_doctor_detail
from app.services.appointment_service import notify_affected_patients

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


@router.get("/search", response_model=list[DoctorSearchResult])
async def search_doctors(
    specialization: Optional[str] = Query(None),
    db: Prisma = Depends(get_db),
):
    return await get_doctors_by_specialization(db, specialization)


@router.get("/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(doctor_id: int, db: Prisma = Depends(get_db)):
    doctor = await get_doctor_detail(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.get("/{doctor_id}/slots", response_model=list[SlotResponse])
async def get_doctor_slots(
    doctor_id: int,
    date: str = Query(...),
    db: Prisma = Depends(get_db),
):
    from datetime import date as date_type
    try:
        target_date = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (use YYYY-MM-DD)")

    slots = await generate_slots(db, doctor_id, target_date)
    return slots


@router.put("/profile", response_model=DoctorResponse)
async def update_doctor_profile(
    data: DoctorProfileUpdate,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    profile = await db.doctorprofile.find_first(where={"user_id": current_user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    update_data = data.model_dump(exclude_none=True)
    if update_data:
        await db.doctorprofile.update(
            where={"id": profile.id},
            data=update_data,
        )

    return await get_doctor_detail(db, current_user.id)


@router.post("/availability", response_model=DoctorAvailabilityResponse)
async def add_availability(
    data: DoctorAvailabilityCreate,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    profile = await db.doctorprofile.find_first(where={"user_id": current_user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    avail = await db.doctoravailability.create(data={
        "doctor_id": profile.id,
        "day_of_week": data.day_of_week,
        "start_time": data.start_time,
        "end_time": data.end_time,
        "is_available": data.is_available,
    })
    return avail


@router.delete("/availability/{avail_id}")
async def remove_availability(
    avail_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    profile = await db.doctorprofile.find_first(where={"user_id": current_user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    avail = await db.doctoravailability.find_first(
        where={"id": avail_id, "doctor_id": profile.id},
    )
    if not avail:
        raise HTTPException(status_code=404, detail="Availability not found")
    await db.doctoravailability.delete(where={"id": avail_id})
    return {"message": "Availability removed"}


@router.post("/leave", response_model=DoctorLeaveResponse)
async def add_leave(
    data: DoctorLeaveCreate,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    profile = await db.doctorprofile.find_first(where={"user_id": current_user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    from datetime import date, datetime
    leave_date = date.fromisoformat(data.leave_date)
    leave_datetime = datetime.combine(leave_date, datetime.min.time())

    leave = await db.doctorleave.create(data={
        "doctor_id": profile.id,
        "leave_date": leave_datetime,
        "reason": data.reason,
    })

    await notify_affected_patients(db, current_user.id, leave_date)

    return DoctorLeaveResponse(
        id=leave.id,
        leave_date=leave.leave_date.isoformat(),
        reason=leave.reason,
        created_at=leave.created_at.isoformat(),
    )


@router.delete("/leave/{leave_id}")
async def remove_leave(
    leave_id: int,
    db: Prisma = Depends(get_db),
    current_user=Depends(get_current_doctor),
):
    profile = await db.doctorprofile.find_first(where={"user_id": current_user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    leave = await db.doctorleave.find_first(
        where={"id": leave_id, "doctor_id": profile.id},
    )
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    await db.doctorleave.delete(where={"id": leave_id})
    return {"message": "Leave removed"}
