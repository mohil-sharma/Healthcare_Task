"""
Shared SQLAlchemy / Python enums used across multiple models.
Defined once here to avoid circular imports.
"""

import enum


class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"


class AppointmentStatus(str, enum.Enum):
    held = "held"           # slot reserved, payment/confirmation pending
    confirmed = "confirmed" # patient + doctor both confirmed
    cancelled = "cancelled"
    completed = "completed"


class NotificationType(str, enum.Enum):
    booking_confirmation = "booking_confirmation"
    reminder = "reminder"
    cancellation = "cancellation"
    medication_reminder = "medication_reminder"


class NotificationChannel(str, enum.Enum):
    email = "email"
    calendar = "calendar"


class NotificationStatus(str, enum.Enum):
    sent = "sent"
    failed = "failed"
    retrying = "retrying"
