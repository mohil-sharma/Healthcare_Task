import asyncio
import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create users
        admin_token = (await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})).json()["access_token"]
        ts = int(datetime.datetime.now().timestamp())
        
        doc_email = f"doc_{ts}@test.com"
        doc_res = await client.post("/api/admin/doctors", json={"email": doc_email, "name": "Dr. Cal", "password": "pass", "specialisation": "test", "slot_duration_minutes": 30}, headers={"Authorization": f"Bearer {admin_token}"})
        doctor_id = doc_res.json()["id"]

        pat_email = f"pat_{ts}@test.com"
        await client.post("/api/auth/register/patient", json={"email": pat_email, "name": "Pat", "password": "pass"})
        pat_token = (await client.post("/api/auth/login", data={"username": pat_email, "password": "pass"})).json()["access_token"]
        pat_headers = {"Authorization": f"Bearer {pat_token}"}

        # Let Pat "connect" calendar via mocked callback
        from app.db.session import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            pat_user = (await db.execute(select(User).where(User.email == pat_email))).scalar_one()
            pat_user_id = pat_user.id
            doc_user = (await db.execute(select(User).where(User.email == doc_email))).scalar_one()
            doc_user_id = doc_user.id
            
        print("Connecting Patient Calendar (Mock)...")
        cb_res = await client.get(f"/api/calendar/callback?code=fakecode&state={pat_user_id}")
        print("Callback response:", cb_res.json())

        # Book & Confirm -> should not crash even if the sync is skipped or fails 
        slot = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).replace(microsecond=0, second=0).isoformat()
        hold_res = await client.post("/api/patient/appointments/hold", json={"doctor_id": doctor_id, "slot_start": slot}, headers=pat_headers)
        appt_id = hold_res.json()["id"]
        conf_res = await client.post(f"/api/patient/appointments/{appt_id}/confirm", json={"symptoms_text": "I have a headache and I feel dizzy."}, headers=pat_headers)
        print("Booking confirmed status:", conf_res.status_code)
        
        # Reschedule 
        new_slot = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).replace(microsecond=0, second=0).isoformat()
        res_res = await client.post(f"/api/patient/appointments/{appt_id}/reschedule", json={"new_slot_start": new_slot}, headers=pat_headers)
        print("Reschedule status:", res_res.status_code)
        
        # Cancel (Admin leaves on that day)
        new_slot_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        leave_res = await client.post(f"/api/admin/doctors/{doctor_id}/leave", json={"leave_date": new_slot_date, "reason": "sick"}, headers={"Authorization": f"Bearer {admin_token}"})
        print("Admin leave/cancellation status:", leave_res.status_code)

if __name__ == "__main__":
    asyncio.run(run())
