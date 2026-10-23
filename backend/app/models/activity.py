"""activity_events: the Activity page and the notification bell."""
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import UTCDateTime, created_at


class ActivityEvent(db.Model):
    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)        # e.g. "experiment.completed"
    message: Mapped[str] = mapped_column(String(200), nullable=False)
    # If the experiment is deleted the event stays, without its link (ON DELETE SET NULL).
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created_at()
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user = relationship("User", back_populates="activity")
