import asyncio
import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import get_password_hash
from sqlalchemy import select

async def ensure_admin():
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.email=="admin@system.local"))).scalar_one_or_none()
        if not admin:
            admin = User(email="admin@system.local", name="Super Admin", password_hash=get_password_hash("admin123"), role=UserRole.admin)
            db.add(admin)
            await db.commit()

async def run():
    await ensure_admin()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Setup doc and patient
        admin_token = (await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})).json()["access_token"]
        ts = int(datetime.datetime.now().timestamp())
        doc_res = await client.post("/api/admin/doctors", json={"email": f"doc_{ts}@test.com", "name": "Dr. L", "password": "pass", "specialisation": "test", "slot_duration_minutes": 30}, headers={"Authorization": f"Bearer {admin_token}"})
        doctor_id = doc_res.json()["id"]

        await client.post("/api/auth/register/patient", json={"email": f"pat_{ts}@test.com", "name": "Pat", "password": "pass"})
        pat_token = (await client.post("/api/auth/login", data={"username": f"pat_{ts}@test.com", "password": "pass"})).json()["access_token"]
        pat_headers = {"Authorization": f"Bearer {pat_token}"}
        
        doc_token = (await client.post("/api/auth/login", data={"username": f"doc_{ts}@test.com", "password": "pass"})).json()["access_token"]
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # 2. Book and confirm appointment
        slot = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, second=0).isoformat()
        hold_res = await client.post("/api/patient/appointments/hold", json={"doctor_id": doctor_id, "slot_start": slot}, headers=pat_headers)
        appt_id = hold_res.json()["id"]
        conf_res = await client.post(f"/api/patient/appointments/{appt_id}/confirm", json={"symptoms_text": "I have a headache and I feel dizzy."}, headers=pat_headers)
        
        # 3. Doctor submits post-visit notes
        print("Doctor submitting post-visit notes...")
        post_visit_payload = {
            "doctor_notes": "Patient presented with a mild headache. Recommended rest and ibuprofen. Re-evaluate if symptoms persist.",
            "prescriptions": [
                {
                    "medication_name": "Ibuprofen 400mg",
                    "frequency": "Every 6 hours as needed for pain",
                    "duration_days": 3
                }
            ]
        }
        post_res = await client.post(f"/api/doctor/appointments/{appt_id}/post-visit", json=post_visit_payload, headers=doc_headers)
        print("Doctor Post-Visit status:", post_res.status_code)
        
        # 4. Patient views post-visit summary
        print("Patient viewing summary...")
        sum_res = await client.get(f"/api/patient/appointments/{appt_id}/post-visit-summary", headers=pat_headers)
        print("Summary status:", sum_res.status_code)
        print("Summary response:", sum_res.json())

if __name__ == "__main__":
    asyncio.run(run())
