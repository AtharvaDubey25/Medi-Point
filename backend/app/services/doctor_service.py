from datetime import datetime, date, timedelta
from typing import List, Optional
from prisma import Prisma


async def generate_slots(
    db: Prisma,
    doctor_user_id: int,
    target_date: date,
) -> List[dict]:
    target_datetime = datetime.combine(target_date, datetime.min.time())
    doctor_profile = await db.doctorprofile.find_first(
        where={"user_id": doctor_user_id},
        include={"availability": True, "leaves": True},
    )
    if not doctor_profile:
        return []

    if doctor_profile.is_on_leave:
        return []

    day_of_week = target_date.weekday()

    is_on_leave = any(
        l.leave_date.date() == target_date
        for l in doctor_profile.leaves
    )
    if is_on_leave:
        return []

    avail_slots = [
        a for a in doctor_profile.availability
        if a.day_of_week == day_of_week and a.is_available
    ]

    if not avail_slots:
        return []

    existing_appts = await db.appointment.find_many(
        where={
            "doctor_id": doctor_user_id,
            "appointment_date": target_datetime,
            "status": {"in": ["SCHEDULED", "RESCHEDULED"]},
        },
    )
    booked_times = {(a.start_time, a.end_time) for a in existing_appts}

    slot_min = doctor_profile.slot_duration_minutes
    slots = []

    for avail in avail_slots:
        try:
            start_h, start_m = map(int, avail.start_time.split(":"))
            end_h, end_m = map(int, avail.end_time.split(":"))
        except (ValueError, AttributeError, TypeError):
            continue

        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m

        current = start_total
        while current + slot_min <= end_total:
            h = current // 60
            m = current % 60
            slot_start = f"{h:02d}:{m:02d}"
            end_current = current + slot_min
            eh = end_current // 60
            em = end_current % 60
            slot_end = f"{eh:02d}:{em:02d}"

            is_booked = (slot_start, slot_end) in booked_times
            slots.append({
                "start_time": slot_start,
                "end_time": slot_end,
                "available": not is_booked,
            })
            current = end_current

    slots.sort(key=lambda s: s["start_time"])
    return slots


async def get_doctors_by_specialization(
    db: Prisma,
    specialization: Optional[str] = None,
) -> list:
    where = {
        "user": {"is_active": True},
    }
    if specialization:
        where["specialization"] = {"contains": specialization}

    doctors = await db.doctorprofile.find_many(
        where=where,
        include={"user": True},
    )
    return [
        {
            "id": d.id,
            "user_id": d.user_id,
            "full_name": d.user.full_name,
            "specialization": d.specialization,
            "experience_years": d.experience_years,
            "is_on_leave": d.is_on_leave,
            "bio": d.bio,
        }
        for d in doctors
    ]


async def get_doctor_detail(db: Prisma, doctor_user_id: int) -> Optional[dict]:
    profile = await db.doctorprofile.find_first(
        where={"user_id": doctor_user_id},
        include={
            "user": True,
            "availability": True,
            "leaves": True,
        },
    )
    if not profile:
        return None
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.user.full_name,
        "email": profile.user.email,
        "phone": profile.user.phone,
        "specialization": profile.specialization,
        "qualification": profile.qualification,
        "experience_years": profile.experience_years,
        "slot_duration_minutes": profile.slot_duration_minutes,
        "is_on_leave": profile.is_on_leave,
        "bio": profile.bio,
        "availability": [
            {
                "id": a.id,
                "day_of_week": a.day_of_week,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "is_available": a.is_available,
            }
            for a in profile.availability
        ],
        "leaves": [
            {
                "id": l.id,
                "leave_date": l.leave_date.isoformat(),
                "reason": l.reason,
                "created_at": l.created_at.isoformat(),
            }
            for l in profile.leaves
        ],
    }
