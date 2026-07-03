from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SymptomFormSubmit(BaseModel):
    symptoms: str


class PreVisitSummary(BaseModel):
    urgency_level: str
    chief_complaint: str
    suggested_questions: list[str]


class PostVisitData(BaseModel):
    notes: str
    prescription: str
    medications: Optional[list[dict]] = None  # [{name, dosage, frequency, duration_days, start_date}]


class PostVisitSummary(BaseModel):
    diagnosis_explanation: str
    treatment_plan: str
    medication_instructions: str
    follow_up_advice: str
    when_to_seek_help: str


class SymptomFormResponse(BaseModel):
    id: int
    appointment_id: int
    symptoms_text: str
    pre_visit_summary: Optional[str]
    post_visit_notes: Optional[str]
    post_visit_prescription: Optional[str]
    post_visit_summary: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
