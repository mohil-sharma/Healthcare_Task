import re

# 1. Update llm.py prompts to use < > brackets
with open('/Users/apple/Downloads/Healthcare/backend/app/services/llm.py', 'r') as f:
    content = f.read()

content = content.replace(
    'Symptoms: {symptoms}"""',
    'Symptoms: <{symptoms}>"""'
)
content = content.replace(
    'follow-up steps: {notes}"""',
    'follow-up steps: <{notes}>"""'
)

with open('/Users/apple/Downloads/Healthcare/backend/app/services/llm.py', 'w') as f:
    f.write(content)

# 2. Add cancel endpoint to patient.py
with open('/Users/apple/Downloads/Healthcare/backend/app/routers/patient.py', 'r') as f:
    patient_content = f.read()

cancel_endpoint = """
@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    patient: User = Depends(get_current_patient)
):
    \"\"\"Cancel an existing appointment and notify all parties.\"\"\"
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

"""

# Insert before reschedule_appointment
idx = patient_content.find('@router.post("/appointments/{appointment_id}/reschedule"')
if idx != -1:
    patient_content = patient_content[:idx] + cancel_endpoint + patient_content[idx:]

with open('/Users/apple/Downloads/Healthcare/backend/app/routers/patient.py', 'w') as f:
    f.write(patient_content)
print("Updated llm.py and patient.py")
