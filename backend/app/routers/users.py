"""User routers — Profile retrieval and role-based test endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_admin,
    get_current_doctor,
    get_current_patient,
    get_current_user,
)
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """Return the profile and role of the currently authenticated user."""
    return current_user


# ── The endpoints below exist primarily to test Role-Based Access Control (RBAC)

@router.get("/patient-only")
async def patient_only(current_user: User = Depends(get_current_patient)):
    """Only patients can access this."""
    return {"message": f"Welcome Patient {current_user.name}"}


@router.get("/doctor-only")
async def doctor_only(current_user: User = Depends(get_current_doctor)):
    """Only doctors can access this."""
    return {"message": f"Welcome Doctor {current_user.name}"}


@router.get("/admin-only")
async def admin_only(current_user: User = Depends(get_current_admin)):
    """Only admins can access this."""
    return {"message": f"Welcome Admin {current_user.name}"}
