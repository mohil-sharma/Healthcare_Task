"""Pydantic schemas for Patient booking flow."""

import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class DoctorSearchResponse(BaseModel):
    id: int
    name: str
    specialisation: str
    slot_duration_minutes: int
    working_hours: dict

    model_config = ConfigDict(from_attributes=True)


class AvailableSlot(BaseModel):
    slot_start: datetime.datetime
    slot_end: datetime.datetime


class AvailableSlotsResponse(BaseModel):
    doctor_id: int
    date: datetime.date
    available_slots: List[AvailableSlot]


class HoldSlotRequest(BaseModel):
    doctor_id: int
    slot_start: datetime.datetime

class RescheduleRequest(BaseModel):
    new_slot_start: datetime.datetime


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    slot_start: datetime.datetime
    slot_end: datetime.datetime
    status: str
    held_until: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SymptomFormRequest(BaseModel):
    symptoms_text: str


class SymptomFormResponse(BaseModel):
    id: int
    appointment_id: int
    symptoms_text: str
    submitted_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class PrescriptionPatientResponse(BaseModel):
    id: int
    medication_name: str
    frequency: str
    duration_days: int
    
    model_config = ConfigDict(from_attributes=True)

class PostVisitSummaryPatientResponse(BaseModel):
    id: int
    appointment_id: int
    patient_friendly_summary: str
    generated_at: datetime.datetime
    # We deliberately omit doctor_notes in this schema as they are raw clinical notes, though they can be included if desired. We will just return the patient_friendly_summary.

    model_config = ConfigDict(from_attributes=True)

class PostVisitPatientDetailsResponse(BaseModel):
    summary: PostVisitSummaryPatientResponse
    prescriptions: List[PrescriptionPatientResponse]
