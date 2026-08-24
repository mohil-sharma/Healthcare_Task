"""Pydantic schemas for User entities."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


# ── Common User Base ──────────────────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    name: str


# ── Registration Schemas ──────────────────────────────────────────────────────
class PatientRegister(UserBase):
    password: str


class DoctorRegister(UserBase):
    password: str
    specialisation: str
    slot_duration_minutes: int = 30


# ── Response Schemas ──────────────────────────────────────────────────────────
class DoctorProfileResponse(BaseModel):
    specialisation: str
    working_hours: dict
    slot_duration_minutes: int

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: int
    role: UserRole
    created_at: datetime
    
    # Only populated if role == 'doctor'
    doctor_profile: Optional[DoctorProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)
