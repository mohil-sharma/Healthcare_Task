"""Pydantic schemas for Admin endpoints."""

import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from app.schemas.user import UserResponse


class DoctorCreateAdmin(BaseModel):
    email: str
    name: str
    password: str
    specialisation: str
    slot_duration_minutes: int = 30


class DoctorUpdateAdmin(BaseModel):
    name: Optional[str] = None
    specialisation: Optional[str] = None
    slot_duration_minutes: Optional[int] = None
    working_hours: Optional[Dict] = None
    is_active: Optional[bool] = None


class LeaveDayCreate(BaseModel):
    leave_date: datetime.date
    reason: Optional[str] = None


class LeaveDayResponse(BaseModel):
    id: int
    doctor_id: int
    leave_date: datetime.date
    reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CancelledAppointmentResponse(BaseModel):
    id: int
    patient_id: int
    slot_start: datetime.datetime
    slot_end: datetime.datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class LeaveDayImpactResponse(BaseModel):
    leave_day: LeaveDayResponse
    cancelled_appointments: List[CancelledAppointmentResponse]
