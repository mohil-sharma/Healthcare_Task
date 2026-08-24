"""
DoctorLeaveDay model.

Records individual dates when a doctor is unavailable.
The appointment-slot generation logic must check this table before
offering a slot to a patient.
"""

import datetime as dt
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DoctorLeaveDay(Base):
    __tablename__ = "doctor_leave_days"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("doctor_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_date: Mapped[dt.date] = mapped_column(sa.Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        # A doctor should only have one leave record per date
        sa.UniqueConstraint("doctor_id", "leave_date", name="uq_doctor_leave_date"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    doctor_profile: Mapped["DoctorProfile"] = relationship(  # type: ignore[name-defined]
        "DoctorProfile", back_populates="leave_days"
    )
