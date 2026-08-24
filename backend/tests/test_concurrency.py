import asyncio
import datetime
import pytest
from httpx import AsyncClient
from app.db.session import get_db

@pytest.mark.asyncio
async def test_concurrent_slot_booking():
    from app.main import app
    from tests.conftest import TestingSessionLocal
    
    # We must yield a fresh session per request so the two concurrent requests
    # don't share the same SQLAlchemy session.
    async def fresh_db():
        async with TestingSessionLocal() as session:
            yield session
            
    app.dependency_overrides[get_db] = fresh_db
    
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Setup: Register a doctor, set working hours, and two patients
        admin_token_res = await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})
        admin_token = admin_token_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Register doctor
        doc_res = await client.post(
            "/api/admin/doctors",
            json={
                "email": "doc_conc@test.com",
                "name": "Dr. Concurrency",
                "password": "docpassword",
                "specialisation": "Concurrency",
                "slot_duration_minutes": 30
            },
            headers=admin_headers
        )
        assert doc_res.status_code == 200, doc_res.text
        doctor_id = doc_res.json()["id"]

        # Register Patient 1
        p1_res = await client.post("/api/auth/register/patient", json={"email": "p1@test.com", "name": "Patient 1", "password": "p1"})
        p1_token = (await client.post("/api/auth/login", data={"username": "p1@test.com", "password": "p1"})).json()["access_token"]
        p1_headers = {"Authorization": f"Bearer {p1_token}"}

        # Register Patient 2
        p2_res = await client.post("/api/auth/register/patient", json={"email": "p2@test.com", "name": "Patient 2", "password": "p2"})
        p2_token = (await client.post("/api/auth/login", data={"username": "p2@test.com", "password": "p2"})).json()["access_token"]
        p2_headers = {"Authorization": f"Bearer {p2_token}"}

        # 2. Fire two concurrent requests to hold the EXACT SAME SLOT
        slot_time = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, second=0).isoformat()
        
        async def book(headers):
            return await client.post(
                "/api/patient/appointments/hold",
                json={"doctor_id": doctor_id, "slot_start": slot_time},
                headers=headers
            )

        # We use asyncio.gather to fire them at exactly the same time
        res1, res2 = await asyncio.gather(
            book(p1_headers),
            book(p2_headers)
        )

        # 3. Exactly one should succeed (200), and exactly one should fail (409 Conflict)
        status_codes = {res1.status_code, res2.status_code}
        assert 200 in status_codes, f"Both failed? {res1.text} {res2.text}"
        assert 409 in status_codes, f"Both succeeded? {res1.text} {res2.text}"
        
        # Check the error message of the 409 response
        if res1.status_code == 409:
            assert res1.json()["detail"] == "Slot is no longer available"
        if res2.status_code == 409:
            assert res2.json()["detail"] == "Slot is no longer available"
