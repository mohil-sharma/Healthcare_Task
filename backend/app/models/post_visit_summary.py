"""
PostVisitSummary model.

LLM-generated summary created after the doctor adds their notes.
doctor_notes is the raw clinical note; patient_friendly_summary is the
plain-language version the patient sees in their portal.

One summary per appointment (enforced by unique FK).
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PostVisitSummary(Base):
    __tablename__ = "post_visit_summaries"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one post-visit summary per appointment
        index=True,
    )
    doctor_notes: Mapped[str] = mapped_column(sa.Text, nullable=False)
    patient_friendly_summary: Mapped[str] = mapped_column(sa.Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="post_visit_summary"
    )
