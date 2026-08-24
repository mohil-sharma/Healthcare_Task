"""
Import all SQLAlchemy models here so that Alembic autogenerate
picks them up when it inspects Base.metadata.

Add every new model file as an import below — the import itself is
the side effect that registers the model with Base.metadata.
"""

from app.db.base_class import Base  # noqa: F401

# ── All models ────────────────────────────────────────────────────────────────
from app.models.user import User  # noqa: F401
from app.models.doctor_profile import DoctorProfile  # noqa: F401
from app.models.doctor_leave_day import DoctorLeaveDay  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.symptom_form import SymptomForm  # noqa: F401
from app.models.pre_visit_summary import PreVisitSummary  # noqa: F401
from app.models.prescription import Prescription  # noqa: F401
from app.models.post_visit_summary import PostVisitSummary  # noqa: F401
from app.models.notification_log import NotificationLog  # noqa: F401
from app.models.calendar_event import CalendarEvent  # noqa: F401
