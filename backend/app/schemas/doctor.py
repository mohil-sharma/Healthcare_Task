"""Pydantic schemas for Doctor endpoints."""

import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class PreVisitSummaryResponse(BaseModel):
    id: int
    appointment_id: int
    urgency_level: str
    chief_complaint: str
    suggested_questions: List[str]
    generated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class SymptomFormDetailResponse(BaseModel):
    symptoms_text: str
    submitted_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class PreVisitDetailsResponse(BaseModel):
    symptom_form: SymptomFormDetailResponse
    summary: PreVisitSummaryResponse

class PrescriptionInput(BaseModel):
    medication_name: str
    frequency: str
    duration_days: int

class PostVisitRequest(BaseModel):
    doctor_notes: str
    prescriptions: List[PrescriptionInput] = []

class PrescriptionResponse(BaseModel):
    id: int
    medication_name: str
    frequency: str
    duration_days: int

    model_config = ConfigDict(from_attributes=True)

class PostVisitSummaryResponse(BaseModel):
    id: int
    appointment_id: int
    doctor_notes: str
    patient_friendly_summary: str
    generated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class PostVisitDetailsResponse(BaseModel):
    summary: PostVisitSummaryResponse
    prescriptions: List[PrescriptionResponse]
