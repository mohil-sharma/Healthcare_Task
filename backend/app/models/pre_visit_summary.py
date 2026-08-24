"""
PreVisitSummary model.

LLM-generated summary produced after the patient submits their symptom form.
Includes urgency level, chief complaint, and suggested questions for the doctor.

suggested_questions is JSONB — expected shape:
    ["Have you had this pain before?", "Is it worse after eating?", ...]

raw_llm_response preserves the unprocessed API response for auditability /
re-parsing if the prompt changes.
"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PreVisitSummary(Base):
    __tablename__ = "pre_visit_summaries"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one summary per appointment
        index=True,
    )
    urgency_level: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )  # e.g. "low" | "medium" | "high" | "emergency"
    chief_complaint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    suggested_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_llm_response: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="pre_visit_summary"
    )
