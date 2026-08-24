"""
Appointment model — the core scheduling entity.

DOUBLE-BOOKING PREVENTION
─────────────────────────
A partial unique index on (doctor_id, slot_start) is applied only to rows
whose status is 'held' OR 'confirmed'.  This is intentional:

  • 'held'      — the slot is temporarily reserved while the patient completes
                  payment / confirmation.  It must block other bookings for the
                  same slot to prevent race conditions.
  • 'confirmed' — the appointment is active; obviously must be exclusive.
  • 'cancelled' — the slot is free again.  A future patient must be able to
                  book the same slot, so cancelled rows are *excluded* from the
                  constraint to avoid blocking re-use.
  • 'completed' — historical record; the same slot on a future date is a
                  different logical slot.  Excluding completed rows also allows
                  the data warehouse to keep the full history without fights
                  with the unique index.

PostgreSQL enforces this as a *partial index*, meaning the uniqueness check
is only evaluated for rows that satisfy the WHERE clause.  Any number of
cancelled/completed rows can share the same (doctor_id, slot_start) pair.

The index name is 'uix_doctor_slot_active' — search for it in migrations.
"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base
from app.models.enums import AppointmentStatus


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slot_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        sa.Enum(AppointmentStatus, name="appointment_status", create_type=False),
        nullable=False,
        default=AppointmentStatus.held,
        server_default=AppointmentStatus.held.value,
    )
    held_until: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        # ── Partial unique index — double-booking prevention ──────────────────
        # See module-level docstring for full rationale.
        sa.Index(
            "uix_doctor_slot_active",
            "doctor_id",
            "slot_start",
            unique=True,
            postgresql_where=sa.text("status IN ('held', 'confirmed')"),
        ),
        # Guard: slot_end must always be after slot_start
        sa.CheckConstraint("slot_end > slot_start", name="chk_slot_end_after_start"),
        # Guard: patient and doctor must be different people
        sa.CheckConstraint("patient_id != doctor_id", name="chk_patient_ne_doctor"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    patient: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[patient_id], back_populates="patient_appointments"
    )
    doctor: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[doctor_id], back_populates="doctor_appointments"
    )
    symptom_form: Mapped["SymptomForm"] = relationship(  # type: ignore[name-defined]
        "SymptomForm", back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )
    pre_visit_summary: Mapped["PreVisitSummary"] = relationship(  # type: ignore[name-defined]
        "PreVisitSummary", back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(  # type: ignore[name-defined]
        "Prescription", back_populates="appointment", cascade="all, delete-orphan"
    )
    post_visit_summary: Mapped["PostVisitSummary"] = relationship(  # type: ignore[name-defined]
        "PostVisitSummary", back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )
    notifications: Mapped[list["NotificationLog"]] = relationship(  # type: ignore[name-defined]
        "NotificationLog", back_populates="appointment", cascade="all, delete-orphan"
    )
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(  # type: ignore[name-defined]
        "CalendarEvent", back_populates="appointment", cascade="all, delete-orphan"
    )
