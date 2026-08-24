"""
CalendarEvent model.

Tracks Google Calendar events created for appointments.
One row per (appointment, user) pair — both the patient and the doctor
get their own calendar invite, so a single appointment can have two rows.

google_event_id is the event ID returned by the Google Calendar API;
stored here so we can update or delete the event when the appointment changes.
"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    google_event_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    __table_args__ = (
        # Each user should have at most one calendar event per appointment
        sa.UniqueConstraint("appointment_id", "user_id", name="uq_calendar_event_appt_user"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="calendar_events"
    )
    user: Mapped["User"] = relationship("User", back_populates="calendar_events")  # type: ignore[name-defined]
