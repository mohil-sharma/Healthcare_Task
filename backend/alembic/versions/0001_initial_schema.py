"""Initial schema — all tables, enums, indexes, and constraints.

Revision ID: 0001
Revises:
Create Date: 2026-08-20

SCHEMA OVERVIEW
───────────────
  users                → all authenticated principals (patient / doctor / admin)
  doctor_profiles      → 1:1 extension of users for doctors
  doctor_leave_days    → dates a doctor is unavailable
  appointments         → core scheduling entity
  symptom_forms        → patient-submitted symptoms (pre-visit)
  pre_visit_summaries  → LLM-generated triage summary (pre-visit)
  prescriptions        → medication lines (post-visit, many per appointment)
  post_visit_summaries → LLM-generated plain-language summary (post-visit)
  notifications_log    → outbound notification audit trail
  calendar_events      → Google Calendar event IDs per (appointment, user)

DOUBLE-BOOKING PREVENTION
─────────────────────────
  See the partial index 'uix_doctor_slot_active' on appointments.
  Full rationale is documented in app/models/appointment.py.
"""

from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = "0001"
down_revision: Optional[str] = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ── 1. users ───────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role", 
            sa.Enum("patient", "doctor", "admin", name="user_role"), 
            nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. doctor_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "doctor_profiles",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("specialisation", sa.String(255), nullable=False),
        sa.Column("working_hours", JSONB, nullable=False, server_default="{}"),
        sa.Column("slot_duration_minutes", sa.SmallInteger, nullable=False, server_default="30"),
    )

    # ── 3. doctor_leave_days ───────────────────────────────────────────────────
    op.create_table(
        "doctor_leave_days",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "doctor_id",
            sa.BigInteger,
            sa.ForeignKey("doctor_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("leave_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.UniqueConstraint("doctor_id", "leave_date", name="uq_doctor_leave_date"),
    )
    op.create_index("ix_doctor_leave_days_doctor_id", "doctor_leave_days", ["doctor_id"])

    # ── 4. appointments ────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("held", "confirmed", "cancelled", "completed", name="appointment_status"),
            nullable=False,
            server_default="held",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("slot_end > slot_start", name="chk_slot_end_after_start"),
        sa.CheckConstraint("patient_id != doctor_id", name="chk_patient_ne_doctor"),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])

    # Double-booking prevention index
    op.create_index(
        "uix_doctor_slot_active",
        "appointments",
        ["doctor_id", "slot_start"],
        unique=True,
        postgresql_where=sa.text("status IN ('held', 'confirmed')"),
    )

    # ── 5. symptom_forms ──────────────────────────────────────────────────────
    op.create_table(
        "symptom_forms",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symptoms_text", sa.Text, nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("appointment_id", name="uq_symptom_form_appointment"),
    )
    op.create_index("ix_symptom_forms_appointment_id", "symptom_forms", ["appointment_id"])

    # ── 6. pre_visit_summaries ─────────────────────────────────────────────────
    op.create_table(
        "pre_visit_summaries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("urgency_level", sa.String(50), nullable=False),
        sa.Column("chief_complaint", sa.Text, nullable=False),
        sa.Column("suggested_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("raw_llm_response", sa.Text, nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("appointment_id", name="uq_pre_visit_summary_appointment"),
    )
    op.create_index(
        "ix_pre_visit_summaries_appointment_id", "pre_visit_summaries", ["appointment_id"]
    )

    # ── 7. prescriptions ──────────────────────────────────────────────────────
    op.create_table(
        "prescriptions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("medication_name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(100), nullable=False),
        sa.Column("duration_days", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("duration_days > 0", name="chk_prescription_duration_positive"),
    )
    op.create_index("ix_prescriptions_appointment_id", "prescriptions", ["appointment_id"])

    # ── 8. post_visit_summaries ────────────────────────────────────────────────
    op.create_table(
        "post_visit_summaries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doctor_notes", sa.Text, nullable=False),
        sa.Column("patient_friendly_summary", sa.Text, nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("appointment_id", name="uq_post_visit_summary_appointment"),
    )
    op.create_index(
        "ix_post_visit_summaries_appointment_id", "post_visit_summaries", ["appointment_id"]
    )

    # ── 9. notifications_log ─────────────────────────────────────────────────
    op.create_table(
        "notifications_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("booking_confirmation", "reminder", "cancellation", "medication_reminder", name="notification_type"),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum("email", "calendar", name="notification_channel"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("sent", "failed", "retrying", name="notification_status"),
            nullable=False,
            server_default="retrying",
        ),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notifications_log_appointment_id", "notifications_log", ["appointment_id"]
    )

    # ── 10. calendar_events ────────────────────────────────────────────────────
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.BigInteger,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("google_event_id", sa.String(255), nullable=False),
        sa.UniqueConstraint(
            "appointment_id", "user_id", name="uq_calendar_event_appt_user"
        ),
    )
    op.create_index("ix_calendar_events_appointment_id", "calendar_events", ["appointment_id"])
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"])


def downgrade() -> None:
    # Drop tables in reverse FK dependency order
    op.drop_table("calendar_events")
    op.drop_table("notifications_log")
    op.drop_table("post_visit_summaries")
    op.drop_table("prescriptions")
    op.drop_table("pre_visit_summaries")
    op.drop_table("symptom_forms")
    op.drop_table("appointments")
    op.drop_table("doctor_leave_days")
    op.drop_table("doctor_profiles")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE notification_status")
    op.execute("DROP TYPE notification_channel")
    op.execute("DROP TYPE notification_type")
    op.execute("DROP TYPE appointment_status")
    op.execute("DROP TYPE user_role")
