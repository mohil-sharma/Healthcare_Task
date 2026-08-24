"""Authentication routers (Login & Registration)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.schemas.auth import Token
from app.schemas.user import DoctorRegister, PatientRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()] = None,
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id, role=user.role.value)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register/patient", response_model=UserResponse)
async def register_patient(
    user_in: PatientRegister, db: AsyncSession = Depends(get_db)
):
    """Register a new patient."""
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    user = User(
        email=user_in.email,
        name=user_in.name,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.patient,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user, ["doctor_profile"])
    return user


@router.post("/register/doctor", response_model=UserResponse)
async def register_doctor(
    user_in: DoctorRegister, db: AsyncSession = Depends(get_db)
):
    """Register a new doctor, generating their associated profile."""
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    # 1. Create the base User
    user = User(
        email=user_in.email,
        name=user_in.name,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.doctor,
    )
    db.add(user)
    await db.flush()  # to get the user.id

    # 2. Create the DoctorProfile
    doctor_profile = DoctorProfile(
        user_id=user.id,
        specialisation=user_in.specialisation,
        slot_duration_minutes=user_in.slot_duration_minutes,
        working_hours={},
    )
    db.add(doctor_profile)
    await db.commit()
    
    # Refresh and load relations to satisfy the return schema
    await db.refresh(user, ["doctor_profile"])
    return user
