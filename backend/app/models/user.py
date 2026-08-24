"""
User model.

Represents every person who can log in: patients, doctors, and admins.
Role is stored as a native PostgreSQL enum for type safety at the DB level.
"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="user_role", create_type=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.true(), nullable=False
    )
    google_refresh_token: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    doctor_profile: Mapped["DoctorProfile"] = relationship(  # type: ignore[name-defined]
        "DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # Appointments where this user is the patient
    patient_appointments: Mapped[list["Appointment"]] = relationship(  # type: ignore[name-defined]
        "Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient"
    )
    # Appointments where this user is the doctor
    doctor_appointments: Mapped[list["Appointment"]] = relationship(  # type: ignore[name-defined]
        "Appointment", foreign_keys="[Appointment.doctor_id]", back_populates="doctor"
    )
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(  # type: ignore[name-defined]
        "CalendarEvent", back_populates="user"
    )
