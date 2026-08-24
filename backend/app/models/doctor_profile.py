"""
DoctorProfile model.

One-to-one extension of User (for role == doctor).
working_hours is stored as JSONB so it can be queried efficiently.

Expected working_hours shape:
    {
      "monday":    {"start": "09:00", "end": "17:00"},
      "tuesday":   {"start": "09:00", "end": "17:00"},
      ...
    }
Days with no entry are treated as non-working days.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    # Use the same PK as User for a true 1-to-1 (no surrogate PK needed)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    specialisation: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # JSONB gives us partial-index capability and efficient querying later
    working_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    slot_duration_minutes: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=30)

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="doctor_profile")  # type: ignore[name-defined]
    leave_days: Mapped[list["DoctorLeaveDay"]] = relationship(  # type: ignore[name-defined]
        "DoctorLeaveDay", back_populates="doctor_profile", cascade="all, delete-orphan"
    )
