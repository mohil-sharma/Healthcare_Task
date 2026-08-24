"""Notification service to handle DB logging, retries, and actual dispatch."""
import datetime
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification_log import NotificationLog
from app.models.enums import NotificationStatus, NotificationType, NotificationChannel
from app.services.email import send_email

logger = logging.getLogger(__name__)

async def queue_notification(
    db: AsyncSession,
    appointment_id: int,
    notif_type: NotificationType
):
    """
    Creates a NotificationLog entry in 'retrying' state (acting as a queue).
    Immediately attempts to process it once.
    """
    log = NotificationLog(
        appointment_id=appointment_id,
        type=notif_type,
        channel=NotificationChannel.email,
        status=NotificationStatus.retrying,
        retry_count=0,
        next_retry_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(log)
from sqlalchemy.orm import selectinload
from app.models.appointment import Appointment
from app.models.user import User

async def get_email_context_for_notification(db: AsyncSession, log: NotificationLog) -> tuple[list[str], str, str]:
    """
    Returns (to_emails, subject, content) based on log type and appointment context.
    Emails are sent to both Patient and Doctor for booking, reminder, and cancellation.
    """
    appt = await db.get(Appointment, log.appointment_id, options=[selectinload(Appointment.patient), selectinload(Appointment.doctor)])
    if not appt:
        raise ValueError("Appointment not found")
        
    patient_email = appt.patient.email
    doctor_email = appt.doctor.email
    
    if log.type == NotificationType.booking_confirmation:
        return [patient_email, doctor_email], "Booking Confirmed", f"Your appointment with {appt.doctor.name} is confirmed for {appt.slot_start}."
        
    if log.type == NotificationType.cancellation:
        return [patient_email, doctor_email], "Appointment Cancelled", f"Your appointment with {appt.doctor.name} on {appt.slot_start} has been cancelled."
        
    if log.type == NotificationType.reminder:
        return [patient_email, doctor_email], "Appointment Reminder", f"Reminder: You have an appointment with {appt.doctor.name} tomorrow at {appt.slot_start}."
        
    if log.type == NotificationType.medication_reminder:
        return [patient_email], "Medication Reminder", f"This is a reminder to take your prescribed medication."
        
    return [patient_email], "Notification", "Important update regarding your appointment."

async def process_notification_attempt(db: AsyncSession, log: NotificationLog):
    """
    Processes a single NotificationLog attempt (send and update status).
    """
    try:
        to_emails, subject, content = await get_email_context_for_notification(db, log)
        success = await send_email(to_emails, subject, content)
        
        if success:
            log.status = NotificationStatus.sent
        else:
            _mark_failed_with_retry(log, "SendGrid API returned False")
    except Exception as e:
        _mark_failed_with_retry(log, str(e))
        
def _mark_failed_with_retry(log: NotificationLog, error_msg: str):
    log.error_message = error_msg
    log.retry_count += 1
    if log.retry_count > 3:
        log.status = NotificationStatus.failed
    else:
        log.status = NotificationStatus.retrying
        # Exponential backoff: 5m, 15m, 45m
        mins = 5 * (3 ** (log.retry_count - 1))
        log.next_retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=mins)


from sqlalchemy import select

async def process_pending_notifications(db: AsyncSession):
    """Background task to sweep and dispatch pending emails."""
    stmt = select(NotificationLog).where(
        NotificationLog.status == NotificationStatus.retrying,
        NotificationLog.next_retry_at <= datetime.datetime.now(datetime.timezone.utc)
    )
    logs = (await db.execute(stmt)).scalars().all()
    
    for log in logs:
        await process_notification_attempt(db, log)
    
    if logs:
        await db.commit()

