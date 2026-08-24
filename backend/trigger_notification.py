import asyncio
import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app

async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create doc and pat
        admin_token = (await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})).json()["access_token"]
        ts = int(datetime.datetime.now().timestamp())
        
        doc_res = await client.post("/api/admin/doctors", json={"email": f"doc_{ts}@test.com", "name": "Dr. E", "password": "pass", "specialisation": "test", "slot_duration_minutes": 30}, headers={"Authorization": f"Bearer {admin_token}"})
        doctor_id = doc_res.json()["id"]

        await client.post("/api/auth/register/patient", json={"email": f"pat_{ts}@test.com", "name": "Pat", "password": "pass"})
        pat_token = (await client.post("/api/auth/login", data={"username": f"pat_{ts}@test.com", "password": "pass"})).json()["access_token"]
        pat_headers = {"Authorization": f"Bearer {pat_token}"}
        
        # Book and confirm appointment -> triggers booking_confirmation notification
        slot = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).replace(microsecond=0, second=0).isoformat()
        hold_res = await client.post("/api/patient/appointments/hold", json={"doctor_id": doctor_id, "slot_start": slot}, headers=pat_headers)
        appt_id = hold_res.json()["id"]
        conf_res = await client.post(f"/api/patient/appointments/{appt_id}/confirm", json={"symptoms_text": "I have a headache and I feel dizzy."}, headers=pat_headers)
        print("Booking confirmed status:", conf_res.status_code)
        
if __name__ == "__main__":
    asyncio.run(run())
