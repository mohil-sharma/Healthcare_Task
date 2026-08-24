"""
Prescription model.

Each row is one medication line item attached to an appointment.
Multiple prescriptions per appointment are allowed (one row per drug).
"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medication_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(
        sa.String(100), nullable=False
    )  # e.g. "twice daily", "every 8 hours"
    duration_days: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)

    __table_args__ = (
        sa.CheckConstraint("duration_days > 0", name="chk_prescription_duration_positive"),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="prescriptions"
    )
