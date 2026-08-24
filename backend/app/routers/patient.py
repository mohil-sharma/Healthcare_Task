"""Patient router for managing bookings."""

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_patient
from app.db.session import get_db
from app.models.enums import UserRole, AppointmentStatus
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.models.doctor_leave_day import DoctorLeaveDay
from app.models.appointment import Appointment
from app.models.symptom_form import SymptomForm
from app.models.pre_visit_summary import PreVisitSummary
from app.services.llm import analyze_symptoms_with_llm
from app.schemas.patient import (
    DoctorSearchResponse,
    AvailableSlotsResponse,
    AvailableSlot,
    HoldSlotRequest,
    AppointmentResponse,
    SymptomFormRequest,
    SymptomFormResponse
)

router = APIRouter(prefix="/api/patient", tags=["patient"])


@router.get("/doctors", response_model=List[DoctorSearchResponse])
async def search_doctors(
    specialisation: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """Search for active doctors, optionally filtered by specialisation."""
    stmt = (
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.role == UserRole.doctor, User.is_active == True)
    )
    users = (await db.execute(stmt)).scalars().all()

    results = []
    for u in users:
        if not u.doctor_profile:
            continue
        if specialisation and specialisation.lower() not in u.doctor_profile.specialisation.lower():
            continue
        results.append(
            DoctorSearchResponse(
                id=u.id,
                name=u.name,
                specialisation=u.doctor_profile.specialisation,
                slot_duration_minutes=u.doctor_profile.slot_duration_minutes,
                working_hours=u.doctor_profile.working_hours
            )
        )
    return results


@router.get("/doctors/{doctor_id}/slots", response_model=AvailableSlotsResponse)
async def get_available_slots(
    doctor_id: int,
    date: datetime.date,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """Compute available slots for a given doctor and date."""
    doc_user = await db.get(User, doctor_id)
    if not doc_user or not doc_user.is_active or doc_user.role != UserRole.doctor:
        raise HTTPException(status_code=404, detail="Active doctor not found")
        
    doc = await db.get(DoctorProfile, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    # Check if doctor is on leave
    stmt_leave = select(DoctorLeaveDay).where(
        DoctorLeaveDay.doctor_id == doctor_id,
        DoctorLeaveDay.leave_date == date
    )
    if (await db.execute(stmt_leave)).scalar_one_or_none():
        return AvailableSlotsResponse(doctor_id=doctor_id, date=date, available_slots=[])

    # Parse working hours for the day (e.g. {"Monday": ["09:00-12:00"]})
    weekday = date.strftime("%A")
    ranges = doc.working_hours.get(weekday, [])
    
    generated_slots = []
    duration = datetime.timedelta(minutes=doc.slot_duration_minutes)

    for time_range in ranges:
        start_str, end_str = time_range.split("-")
        t_start = datetime.datetime.strptime(start_str.strip(), "%H:%M").time()
        t_end = datetime.datetime.strptime(end_str.strip(), "%H:%M").time()
        
        current = datetime.datetime.combine(date, t_start, tzinfo=datetime.timezone.utc)
        end_dt = datetime.datetime.combine(date, t_end, tzinfo=datetime.timezone.utc)
        
        while current + duration <= end_dt:
            generated_slots.append(current)
            current += duration

    # Query existing appointments for this date
    start_of_day = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_of_day = start_of_day + datetime.timedelta(days=1)
    
    stmt_appts = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.slot_start >= start_of_day,
        Appointment.slot_start < end_of_day,
        Appointment.status.in_([AppointmentStatus.held, AppointmentStatus.confirmed])
    )
    existing_appts = (await db.execute(stmt_appts)).scalars().all()
    booked_starts = {appt.slot_start for appt in existing_appts}

    # Filter out booked slots
    available_slots = [
        AvailableSlot(slot_start=s, slot_end=s + duration) 
        for s in generated_slots 
        if s not in booked_starts
    ]

    return AvailableSlotsResponse(
        doctor_id=doctor_id, 
        date=date, 
        available_slots=available_slots
    )


@router.post("/appointments/hold", response_model=AppointmentResponse)
async def hold_appointment(
    req: HoldSlotRequest,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """
    Temporarily hold a slot for 5 minutes.
    Relies on the DB unique partial index (doctor_id, slot_start) WHERE status IN ('held', 'confirmed').
    """
    doc = await db.get(DoctorProfile, req.doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    duration = datetime.timedelta(minutes=doc.slot_duration_minutes)
    
    # held_until = now + 5 minutes
    held_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=req.doctor_id,
        slot_start=req.slot_start,
        slot_end=req.slot_start + duration,
        status=AppointmentStatus.held,
        held_until=held_until
    )
    db.add(appt)
    
    try:
        await db.commit()
        await db.refresh(appt)
        return appt
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Slot is no longer available")


@router.post("/appointments/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    appointment_id: int,
    req: SymptomFormRequest,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """
    Confirm a previously held appointment and submit symptoms.
    Automatically triggers an LLM to generate a pre-visit summary for the doctor.
    """
    appt = await db.get(Appointment, appointment_id)
    
    if not appt or appt.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if appt.status == AppointmentStatus.confirmed:
        return appt  # Already confirmed
        
    if appt.status != AppointmentStatus.held:
        raise HTTPException(status_code=400, detail=f"Cannot confirm appointment with status {appt.status.value}")
        
    if appt.held_until and appt.held_until < datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=400, detail="Hold has expired")

    # 1. Save the symptom form
    existing_form = (await db.execute(select(SymptomForm).where(SymptomForm.appointment_id == appointment_id))).scalar_one_or_none()
    if not existing_form:
        form = SymptomForm(
            appointment_id=appointment_id,
            symptoms_text=req.symptoms_text
        )
        db.add(form)
        
        # 2. Call LLM
        llm_result = await analyze_symptoms_with_llm(req.symptoms_text)
        
        # 3. Save the Pre-Visit Summary
        summary = PreVisitSummary(
            appointment_id=appointment_id,
            urgency_level=llm_result["urgency_level"],
            chief_complaint=llm_result["chief_complaint"],
            suggested_questions=llm_result["suggested_questions"],
            raw_llm_response=llm_result["raw_llm_response"]
        )
        db.add(summary)

    # 4. Confirm the appointment
    appt.status = AppointmentStatus.confirmed
    
    from app.services.notifications import queue_notification
    from app.models.enums import NotificationType
    from app.services.calendar import sync_calendar_event
    await queue_notification(db, appt.id, NotificationType.booking_confirmation)
    await sync_calendar_event(db, appt, 'create')
    
    await db.commit()
    await db.refresh(appt)
    return appt

from app.schemas.patient import RescheduleRequest


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """Cancel an existing appointment and notify all parties."""
    from app.services.notifications import queue_notification
    from app.models.enums import NotificationType
    from app.services.calendar import sync_calendar_event
    
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if appt.status == AppointmentStatus.cancelled:
        return appt
        
    if appt.status not in (AppointmentStatus.confirmed, AppointmentStatus.held):
        raise HTTPException(status_code=400, detail="Cannot cancel this appointment")
        
    appt.status = AppointmentStatus.cancelled
    
    await queue_notification(db, appt.id, NotificationType.cancellation)
    await sync_calendar_event(db, appt, 'delete')
    
    await db.commit()
    await db.refresh(appt)
    return appt

@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: int,
    req: RescheduleRequest,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """
    Reschedule an existing confirmed appointment.
    """
    from sqlalchemy.exc import IntegrityError
    from app.services.calendar import sync_calendar_event
    from app.models.doctor_profile import DoctorProfile
    
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if appt.status not in (AppointmentStatus.confirmed, AppointmentStatus.held):
        raise HTTPException(status_code=400, detail="Cannot reschedule this appointment")
        
    doc_prof = (await db.execute(select(DoctorProfile).where(DoctorProfile.user_id == appt.doctor_id))).scalar_one_or_none()
    slot_end = req.new_slot_start + datetime.timedelta(minutes=doc_prof.slot_duration_minutes)
    
    appt.slot_start = req.new_slot_start
    appt.slot_end = slot_end
    
    try:
        await db.commit()
        await db.refresh(appt)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Slot is no longer available")
        
    if appt.status == AppointmentStatus.confirmed:
        await sync_calendar_event(db, appt, 'update')
        
    return appt


from app.models.post_visit_summary import PostVisitSummary
from app.models.prescription import Prescription
from app.schemas.patient import PostVisitPatientDetailsResponse

@router.get("/appointments/{appointment_id}/post-visit-summary", response_model=PostVisitPatientDetailsResponse)
async def get_post_visit_summary(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    """
    View the patient-friendly post-visit summary and prescriptions for a completed appointment.
    """
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    summary = (await db.execute(select(PostVisitSummary).where(PostVisitSummary.appointment_id == appointment_id))).scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Post-visit summary not available yet")
        
    prescriptions = (await db.execute(select(Prescription).where(Prescription.appointment_id == appointment_id))).scalars().all()
    
    return {
        "summary": summary,
        "prescriptions": prescriptions
    }

