from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time


class SlotRequest(BaseModel):
    doctor_id: int
    date: str  # YYYY-MM-DD


class SlotResponse(BaseModel):
    start_time: str
    end_time: str
    available: bool


class AppointmentBook(BaseModel):
    doctor_id: int
    appointment_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    symptoms: str


class AppointmentReschedule(BaseModel):
    appointment_date: str
    start_time: str


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    patient_name: str
    doctor_name: str
    appointment_date: str
    start_time: str
    end_time: str
    status: str
    cancellation_reason: Optional[str]
    created_at: str
    has_symptom_form: bool = False
    has_pre_visit_summary: bool = False
    has_post_visit_summary: bool = False

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    appointments: List[AppointmentResponse]
    total: int
