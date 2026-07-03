from pydantic import BaseModel, ValidationInfo, field_validator
from typing import Optional, List
from datetime import time


class DoctorAvailabilityCreate(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    is_available: bool = True


class DoctorAvailabilityResponse(BaseModel):
    id: int
    day_of_week: int
    start_time: str
    end_time: str
    is_available: bool

    class Config:
        from_attributes = True


class DoctorCreate(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    specialization: str
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    slot_duration_minutes: int = 30
    bio: Optional[str] = None

    @field_validator("experience_years", "slot_duration_minutes", mode="before")
    @classmethod
    def blank_numbers_to_defaults(cls, value, info: ValidationInfo):
        if value == "":
            return 30 if info.field_name == "slot_duration_minutes" else None
        return value


class DoctorProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    slot_duration_minutes: Optional[int] = None
    bio: Optional[str] = None
    is_on_leave: Optional[bool] = None

    @field_validator("experience_years", "slot_duration_minutes", mode="before")
    @classmethod
    def blank_numbers_to_none(cls, value):
        if value == "":
            return None
        return value


class DoctorLeaveCreate(BaseModel):
    leave_date: str  # YYYY-MM-DD
    reason: Optional[str] = None


class DoctorLeaveResponse(BaseModel):
    id: int
    leave_date: str
    reason: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str]
    specialization: str
    qualification: Optional[str]
    experience_years: Optional[int]
    slot_duration_minutes: int
    is_on_leave: bool
    bio: Optional[str]
    availability: List[DoctorAvailabilityResponse] = []
    leaves: List[DoctorLeaveResponse] = []

    class Config:
        from_attributes = True


class DoctorSearchResult(BaseModel):
    id: int
    user_id: int
    full_name: str
    specialization: str
    experience_years: Optional[int]
    is_on_leave: bool
    bio: Optional[str]
