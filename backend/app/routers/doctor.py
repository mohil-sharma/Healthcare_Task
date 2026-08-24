"""Doctor router for managing appointments and viewing summaries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.user import User
from app.models.appointment import Appointment
from app.models.symptom_form import SymptomForm
from app.models.pre_visit_summary import PreVisitSummary
from app.schemas.doctor import PreVisitDetailsResponse

router = APIRouter(prefix="/api/doctor", tags=["doctor"])

@router.get("/appointments/{appointment_id}/pre-visit-summary", response_model=PreVisitDetailsResponse)
async def get_pre_visit_summary(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    doctor: User = Depends(get_current_doctor)
):
    """
    View the pre-visit summary and raw symptoms for an appointment.
    """
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="Appointment not found")

    form = (await db.execute(select(SymptomForm).where(SymptomForm.appointment_id == appointment_id))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="Symptom form has not been submitted yet")

    summary = (await db.execute(select(PreVisitSummary).where(PreVisitSummary.appointment_id == appointment_id))).scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary is still being generated or failed")

    return {
        "symptom_form": form,
        "summary": summary
    }

from app.models.prescription import Prescription
from app.models.post_visit_summary import PostVisitSummary
from app.models.enums import AppointmentStatus
from app.services.llm import generate_patient_friendly_summary
from app.schemas.doctor import PostVisitRequest, PostVisitDetailsResponse

@router.post("/appointments/{appointment_id}/post-visit", response_model=PostVisitDetailsResponse)
async def submit_post_visit(
    appointment_id: int,
    req: PostVisitRequest,
    db: AsyncSession = Depends(get_db),
    doctor: User = Depends(get_current_doctor)
):
    """
    Submit post-visit notes and prescriptions.
    Automatically marks appointment as completed and generates a patient-friendly summary.
    """
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if appt.status not in (AppointmentStatus.confirmed, AppointmentStatus.completed):
        raise HTTPException(status_code=400, detail="Appointment must be confirmed to add post-visit notes")
        
    # Check if summary already exists
    existing = (await db.execute(select(PostVisitSummary).where(PostVisitSummary.appointment_id == appointment_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Post-visit notes already submitted")

    # 1. Save prescriptions
    prescriptions = []
    for p_in in req.prescriptions:
        p = Prescription(
            appointment_id=appointment_id,
            medication_name=p_in.medication_name,
            frequency=p_in.frequency,
            duration_days=p_in.duration_days
        )
        db.add(p)
        prescriptions.append(p)
        
    # 2. Call LLM for patient-friendly summary (synchronously awaited)
    friendly_summary = await generate_patient_friendly_summary(req.doctor_notes)
    
    # 3. Save summary
    summary = PostVisitSummary(
        appointment_id=appointment_id,
        doctor_notes=req.doctor_notes,
        patient_friendly_summary=friendly_summary
    )
    db.add(summary)
    
    # 4. Mark appointment as completed
    appt.status = AppointmentStatus.completed
    
    await db.commit()
    await db.refresh(summary)
    for p in prescriptions:
        await db.refresh(p)
        
    return {
        "summary": summary,
        "prescriptions": prescriptions
    }
