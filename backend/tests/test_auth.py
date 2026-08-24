import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login_patient(client: AsyncClient):
    # 1. Register a new patient
    reg_response = await client.post(
        "/api/auth/register/patient",
        json={
            "email": "patient@test.com",
            "name": "Test Patient",
            "password": "password123"
        }
    )
    assert reg_response.status_code == 200
    data = reg_response.json()
    assert data["email"] == "patient@test.com"
    assert data["role"] == "patient"

    # 2. Login
    login_response = await client.post(
        "/api/auth/login",
        data={"username": "patient@test.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    # 3. Check /me endpoint
    me_response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "patient"


@pytest.mark.asyncio
async def test_register_and_login_doctor(client: AsyncClient):
    # 1. Register a new doctor
    reg_response = await client.post(
        "/api/auth/register/doctor",
        json={
            "email": "doctor@test.com",
            "name": "Test Doctor",
            "password": "docpassword",
            "specialisation": "Cardiology",
            "slot_duration_minutes": 30
        }
    )
    assert reg_response.status_code == 200
    data = reg_response.json()
    assert data["role"] == "doctor"
    assert "doctor_profile" in data
    assert data["doctor_profile"]["specialisation"] == "Cardiology"


@pytest.mark.asyncio
async def test_role_based_access_control(client: AsyncClient):
    # 1. Get a patient token
    await client.post(
        "/api/auth/register/patient",
        json={"email": "rbac_patient@test.com", "name": "RBAC Patient", "password": "123"}
    )
    pat_token = (await client.post("/api/auth/login", data={"username": "rbac_patient@test.com", "password": "123"})).json()["access_token"]

    # 2. Get a doctor token
    await client.post(
        "/api/auth/register/doctor",
        json={"email": "rbac_doctor@test.com", "name": "RBAC Doctor", "password": "123", "specialisation": "GP"}
    )
    doc_token = (await client.post("/api/auth/login", data={"username": "rbac_doctor@test.com", "password": "123"})).json()["access_token"]

    # 3. Get the pre-seeded admin token
    admin_token = (await client.post("/api/auth/login", data={"username": "admin@system.local", "password": "admin123"})).json()["access_token"]

    # --- Test Patient restrictions ---
    headers = {"Authorization": f"Bearer {pat_token}"}
    assert (await client.get("/api/users/patient-only", headers=headers)).status_code == 200
    assert (await client.get("/api/users/doctor-only", headers=headers)).status_code == 403
    assert (await client.get("/api/users/admin-only", headers=headers)).status_code == 403

    # --- Test Doctor restrictions ---
    headers = {"Authorization": f"Bearer {doc_token}"}
    assert (await client.get("/api/users/patient-only", headers=headers)).status_code == 403
    assert (await client.get("/api/users/doctor-only", headers=headers)).status_code == 200
    assert (await client.get("/api/users/admin-only", headers=headers)).status_code == 403

    # --- Test Admin restrictions ---
    headers = {"Authorization": f"Bearer {admin_token}"}
    assert (await client.get("/api/users/patient-only", headers=headers)).status_code == 403
    assert (await client.get("/api/users/doctor-only", headers=headers)).status_code == 403
    assert (await client.get("/api/users/admin-only", headers=headers)).status_code == 200
