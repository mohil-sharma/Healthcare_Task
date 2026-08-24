"""
NotificationLog model.

Audit trail for every outbound notification (email, calendar invite, etc.).
Multiple notifications per appointment are expected (booking confirmation,
24 h reminder, medication reminders, etc.).

The combination of (appointment_id, type, channel) is NOT unique because
we may legitimately retry a failed notification or send the same type again
after a cancellation/rebooking.  The status column tracks retry state.
"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import NotificationChannel, NotificationStatus, NotificationType


class NotificationLog(Base):
    __tablename__ = "notifications_log"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        sa.Enum(NotificationType, name="notification_type", create_type=False),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        sa.Enum(NotificationChannel, name="notification_channel", create_type=False),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        sa.Enum(NotificationStatus, name="notification_status", create_type=False),
        nullable=False,
        default=NotificationStatus.retrying,
        server_default=NotificationStatus.retrying.value,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        sa.Integer, default=0, server_default="0", nullable=False
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship(  # type: ignore[name-defined]
        "Appointment", back_populates="notifications"
    )
