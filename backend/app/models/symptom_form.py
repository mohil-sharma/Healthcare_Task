"""
SymptomForm model.

Stores the patient-submitted symptom questionnaire attached to an appointment.
Submitted before the visit so the LLM can generate a PreVisitSummary.
One form per appointment (enforced by the unique FK / uselist=False relationship).
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class SymptomForm(Base):
    __tablename__ = "symptom_forms"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one form per appointment
        index=True,
    )
    symptoms_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="symptom_form"
    )
