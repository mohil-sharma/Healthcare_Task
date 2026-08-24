import asyncio
import datetime
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.notification_log import NotificationLog
from app.models.enums import NotificationStatus
from app.services.notifications import process_pending_notifications

async def run():
    async with AsyncSessionLocal() as db:
        # Check current pending queue
        pending = (await db.execute(select(NotificationLog).where(NotificationLog.status == NotificationStatus.retrying))).scalars().all()
        print(f"Found {len(pending)} pending notifications to process.")
        
        if pending:
            print("Triggering background sweeper manually...")
            await process_pending_notifications(db)
            
            # Re-check status
            for log in pending:
                await db.refresh(log)
                print(f"Log ID {log.id} -> Type: {log.type}, Status: {log.status}, Retries: {log.retry_count}")

if __name__ == "__main__":
    asyncio.run(run())
