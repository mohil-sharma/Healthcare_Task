"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, health, users, admin, patient, doctor, calendar
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
from sqlalchemy import delete
from app.db.session import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus

scheduler = AsyncIOScheduler()

async def cleanup_expired_holds():
    """Background job to delete 'held' appointments that have expired."""
    async with AsyncSessionLocal() as db:
        stmt = delete(Appointment).where(
            Appointment.status == AppointmentStatus.held,
            Appointment.held_until < datetime.datetime.now(datetime.timezone.utc)
        )
        await db.execute(stmt)
        await db.commit()

from sqlalchemy import select
from app.services.notifications import process_pending_notifications, queue_notification
from app.models.enums import NotificationType
from app.models.notification_log import NotificationLog
from app.models.prescription import Prescription
import sqlalchemy as sa

async def run_notification_sweeper():
    """Sweep and send pending/retrying emails."""
    async with AsyncSessionLocal() as db:
        await process_pending_notifications(db)

async def schedule_appointment_reminders():
    """Send reminder 24h before slot_start."""
    async with AsyncSessionLocal() as db:
        now = datetime.datetime.now(datetime.timezone.utc)
        target = now + datetime.timedelta(hours=24)
        target_end = target + datetime.timedelta(hours=1)
        
        stmt = select(Appointment).where(
            Appointment.status == AppointmentStatus.confirmed,
            Appointment.slot_start >= target,
            Appointment.slot_start < target_end
        )
        appts = (await db.execute(stmt)).scalars().all()
        
        for appt in appts:
            existing = await db.execute(select(NotificationLog).where(
                NotificationLog.appointment_id == appt.id,
                NotificationLog.type == NotificationType.reminder
            ))
            if not existing.scalar_one_or_none():
                await queue_notification(db, appt.id, NotificationType.reminder)
        
        await db.commit()

async def schedule_medication_reminders():
    """Parse prescriptions and send medication reminders at correct intervals."""
    async with AsyncSessionLocal() as db:
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # We need prescriptions for completed appointments that haven't expired
        stmt = select(Prescription, Appointment).join(Appointment).where(
            Appointment.status == AppointmentStatus.completed
        )
        results = (await db.execute(stmt)).all()
        
        for p, appt in results:
            # Check if duration has passed
            end_date = appt.slot_start + datetime.timedelta(days=p.duration_days)
            if now > end_date:
                continue
                
            interval_hours = 24
            freq = p.frequency.lower()
            if "twice" in freq or "2" in freq: interval_hours = 12
            elif "8 hours" in freq: interval_hours = 8
            elif "6 hours" in freq: interval_hours = 6
            elif "4 hours" in freq: interval_hours = 4
            
            last_log = (await db.execute(
                select(NotificationLog).where(
                    NotificationLog.appointment_id == p.appointment_id,
                    NotificationLog.type == NotificationType.medication_reminder
                ).order_by(NotificationLog.attempted_at.desc())
            )).scalar_one_or_none()
            
            last_time = last_log.attempted_at if last_log else appt.slot_start
            if (now - last_time).total_seconds() / 3600 >= interval_hours:
                await queue_notification(db, p.appointment_id, NotificationType.medication_reminder)
                
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(cleanup_expired_holds, 'interval', minutes=1, id="cleanup_holds", replace_existing=True)
    scheduler.add_job(run_notification_sweeper, 'interval', minutes=1, id="notif_sweeper", replace_existing=True)
    scheduler.add_job(schedule_appointment_reminders, 'interval', hours=1, id="appt_reminders", replace_existing=True)
    scheduler.add_job(schedule_medication_reminders, 'interval', hours=1, id="med_reminders", replace_existing=True)
    
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(
    title="Healthcare Appointment Platform",
    description="Backend API with SvelteKit proxy via Vite",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(patient.router)
app.include_router(doctor.router)
app.include_router(calendar.router)
