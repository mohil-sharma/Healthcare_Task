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
        # Register a doctor
        admin_token = (await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})).json()["access_token"]
        
        # We need distinct emails in case the DB is not wiped
        ts = int(datetime.datetime.now().timestamp())
        doc_res = await client.post("/api/admin/doctors", json={"email": f"doc_{ts}@test.com", "name": "Dr. C", "password": "pass", "specialisation": "test", "slot_duration_minutes": 30}, headers={"Authorization": f"Bearer {admin_token}"})
        doctor_id = doc_res.json()["id"]

        # Patients
        p1_res = (await client.post("/api/auth/register/patient", json={"email": f"p1_{ts}@test.com", "name": "P1", "password": "pass"}))
        p1_token = (await client.post("/api/auth/login", data={"username": f"p1_{ts}@test.com", "password": "pass"})).json()["access_token"]
        
        p2_res = (await client.post("/api/auth/register/patient", json={"email": f"p2_{ts}@test.com", "name": "P2", "password": "pass"}))
        p2_token = (await client.post("/api/auth/login", data={"username": f"p2_{ts}@test.com", "password": "pass"})).json()["access_token"]

        slot = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, second=0).isoformat()

        async def book(token, name):
            print(f"[{name}] Sending request...")
            res = await client.post("/api/patient/appointments/hold", json={"doctor_id": doctor_id, "slot_start": slot}, headers={"Authorization": f"Bearer {token}"})
            print(f"[{name}] Response: {res.status_code} {res.text}")
            return res

        await asyncio.gather(book(p1_token, "Patient 1"), book(p2_token, "Patient 2"))

if __name__ == "__main__":
    asyncio.run(run())
