"""Admin router for managing doctors and leave days."""

import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.core.security import get_password_hash
from app.models.enums import UserRole, AppointmentStatus, NotificationType, NotificationChannel, NotificationStatus
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.models.doctor_leave_day import DoctorLeaveDay
from app.models.appointment import Appointment
from app.models.notification_log import NotificationLog
from app.schemas.user import UserResponse
from app.schemas.admin import (
    DoctorCreateAdmin,
    DoctorUpdateAdmin,
    LeaveDayCreate,
    LeaveDayImpactResponse,
    LeaveDayResponse,
    CancelledAppointmentResponse
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/doctors", response_model=List[UserResponse])
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all doctors (active and inactive)."""
    stmt = (
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.role == UserRole.doctor)
        .order_by(User.name)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/doctors", response_model=UserResponse)
async def create_doctor(
    doc_in: DoctorCreateAdmin,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create a new doctor profile."""
    # Check if email exists
    existing = await db.execute(select(User).where(User.email == doc_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=doc_in.email,
        name=doc_in.name,
        password_hash=get_password_hash(doc_in.password),
        role=UserRole.doctor,
        is_active=True
    )
    db.add(user)
    await db.flush()

    profile = DoctorProfile(
        user_id=user.id,
        specialisation=doc_in.specialisation,
        slot_duration_minutes=doc_in.slot_duration_minutes,
        working_hours={},
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user, ["doctor_profile"])
    return user


@router.put("/doctors/{doctor_id}", response_model=UserResponse)
async def update_doctor(
    doctor_id: int,
    update_data: DoctorUpdateAdmin,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update a doctor's profile, working hours, or active status."""
    stmt = (
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == doctor_id, User.role == UserRole.doctor)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if update_data.name is not None:
        user.name = update_data.name
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
        
    if user.doctor_profile:
        if update_data.specialisation is not None:
            user.doctor_profile.specialisation = update_data.specialisation
        if update_data.slot_duration_minutes is not None:
            user.doctor_profile.slot_duration_minutes = update_data.slot_duration_minutes
        if update_data.working_hours is not None:
            user.doctor_profile.working_hours = update_data.working_hours

    await db.commit()
    await db.refresh(user, ["doctor_profile"])
    return user


@router.post("/doctors/{doctor_id}/leave", response_model=LeaveDayImpactResponse)
async def add_doctor_leave(
    doctor_id: int,
    leave_data: LeaveDayCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Mark a doctor as on leave for a specific date.
    Automatically cancels any confirmed or held appointments on that date,
    and stages a cancellation email notification.
    """
    # Verify doctor exists
    doc = await db.get(DoctorProfile, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Check for existing leave
    stmt_leave = select(DoctorLeaveDay).where(
        DoctorLeaveDay.doctor_id == doctor_id,
        DoctorLeaveDay.leave_date == leave_data.leave_date
    )
    existing_leave = (await db.execute(stmt_leave)).scalar_one_or_none()
    if existing_leave:
        raise HTTPException(status_code=400, detail="Leave day already recorded for this date")

    # 1. Create the Leave Day
    leave_day = DoctorLeaveDay(
        doctor_id=doctor_id,
        leave_date=leave_data.leave_date,
        reason=leave_data.reason
    )
    db.add(leave_day)

    # 2. Find affected appointments
    # Convert local date to UTC range (assuming slots are stored in UTC)
    start_dt = datetime.datetime.combine(leave_data.leave_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = start_dt + datetime.timedelta(days=1)

    stmt_appts = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.slot_start >= start_dt,
        Appointment.slot_start < end_dt,
        Appointment.status.in_([AppointmentStatus.held, AppointmentStatus.confirmed])
    )
    affected_appts = (await db.execute(stmt_appts)).scalars().all()

    cancelled_list = []
    
    # 3. Cancel and log notifications
    from app.services.notifications import queue_notification
    from app.services.calendar import sync_calendar_event
    for appt in affected_appts:
        appt.status = AppointmentStatus.cancelled
        
        # Log notification for the patient
        await queue_notification(db, appt.id, NotificationType.cancellation)
        await sync_calendar_event(db, appt, 'delete')
        
        cancelled_list.append(
            CancelledAppointmentResponse(
                id=appt.id,
                patient_id=appt.patient_id,
                slot_start=appt.slot_start,
                slot_end=appt.slot_end,
                status=appt.status.value
            )
        )

    await db.commit()
    await db.refresh(leave_day)

    return LeaveDayImpactResponse(
        leave_day=LeaveDayResponse.model_validate(leave_day),
        cancelled_appointments=cancelled_list
    )
