import re

with open('/Users/apple/Downloads/Healthcare/backend/app/routers/patient.py', 'r') as f:
    content = f.read()

# Replace confirm_appointment to take SymptomFormRequest
new_confirm = """@router.post("/appointments/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    appointment_id: int,
    req: SymptomFormRequest,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    \"\"\"
    Confirm a previously held appointment and submit symptoms.
    Automatically triggers an LLM to generate a pre-visit summary for the doctor.
    \"\"\"
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
    return appt"""

# Find the start of confirm_appointment and the start of reschedule_appointment to replace
start_idx = content.find('@router.post("/appointments/{appointment_id}/confirm"')
end_idx = content.find('from app.schemas.patient import RescheduleRequest')

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_confirm + "\n\n" + content[end_idx:]

# Now remove submit_symptoms
start_idx_symp = content.find('@router.post("/appointments/{appointment_id}/symptoms"')
end_idx_symp = content.find('from app.models.post_visit_summary import PostVisitSummary')

if start_idx_symp != -1 and end_idx_symp != -1:
    content = content[:start_idx_symp] + content[end_idx_symp:]

with open('/Users/apple/Downloads/Healthcare/backend/app/routers/patient.py', 'w') as f:
    f.write(content)
print("patient.py updated")
