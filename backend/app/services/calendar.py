"""Google Calendar Sync Service."""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.appointment import Appointment
from app.models.calendar_event import CalendarEvent
from app.core.config import settings

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def get_google_credentials(refresh_token: str) -> Optional[Credentials]:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return None
    return Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET
    )

async def sync_calendar_event(db: AsyncSession, appt: Appointment, action: str):
    """
    action can be: 'create', 'update', 'delete'
    Called when appointment is confirmed (create), rescheduled (update), or cancelled (delete).
    Syncs for both the patient and the doctor if they have connected Google Calendar.
    Does not block if they haven't connected it or if it fails.
    """
    for user_id in (appt.patient_id, appt.doctor_id):
        user = await db.get(User, user_id)
        if not user or not user.google_refresh_token:
            continue
            
        creds = get_google_credentials(user.google_refresh_token)
        if not creds:
            continue
            
        try:
            # We use the synchronous build/execute for simplicity since it's an MVP,
            # but in a high-throughput env, this should run in a threadpool or use an async HTTP client.
            service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
            
            stmt = select(CalendarEvent).where(
                CalendarEvent.appointment_id == appt.id,
                CalendarEvent.user_id == user_id
            )
            cal_event = (await db.execute(stmt)).scalar_one_or_none()
            
            if action == 'create':
                if cal_event:
                    continue # Already created
                
                event_body = {
                    'summary': "Healthcare Appointment",
                    'description': "Confirmed medical appointment.",
                    'start': {
                        'dateTime': appt.slot_start.isoformat(),
                        'timeZone': 'UTC',
                    },
                    'end': {
                        'dateTime': appt.slot_end.isoformat(),
                        'timeZone': 'UTC',
                    },
                }
                event = service.events().insert(calendarId='primary', body=event_body).execute()
                new_cal_event = CalendarEvent(
                    appointment_id=appt.id,
                    user_id=user_id,
                    google_event_id=event['id']
                )
                db.add(new_cal_event)
                
            elif action == 'update':
                if not cal_event:
                    continue
                event = service.events().get(calendarId='primary', eventId=cal_event.google_event_id).execute()
                event['start']['dateTime'] = appt.slot_start.isoformat()
                event['end']['dateTime'] = appt.slot_end.isoformat()
                service.events().update(calendarId='primary', eventId=cal_event.google_event_id, body=event).execute()
                
            elif action == 'delete':
                if not cal_event:
                    continue
                service.events().delete(calendarId='primary', eventId=cal_event.google_event_id).execute()
                await db.delete(cal_event)
                
        except Exception as e:
            logger.error(f"Failed to sync calendar for user {user_id}, action {action}: {e}")
            
    await db.commit()
