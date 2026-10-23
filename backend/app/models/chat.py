"""chat_sessions and chat_messages: saved Playground conversations."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import UTCDateTime, created_at, in_list, utcnow
from .user import MODEL_CHOICES

MESSAGE_ROLES = ("user", "assistant")


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint(in_list("model", MODEL_CHOICES), name="model"),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(10), default="lora", nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan",
                            passive_deletes=True, order_by="ChatMessage.id")

    def to_dict(self, message_count=None, last_message=None):
        d = {"id": self.id, "title": self.title, "model": self.model,
             "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}
        if message_count is not None:
            d["message_count"] = message_count
            d["last_message"] = last_message
        return d


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(in_list("role", MESSAGE_ROLES), name="role"),
        CheckConstraint("temperature >= 0 AND temperature <= 2", name="temperature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                                            nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)   # user input is limited to 500 chars by the API
    model: Mapped[str] = mapped_column(String(10), nullable=False)
    temperature: Mapped[float] = mapped_column(default=0.0, nullable=False)
    top_k: Mapped[int | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = created_at()

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {"id": self.id, "role": self.role, "content": self.content, "model": self.model,
                "temperature": self.temperature, "top_k": self.top_k, "latency_ms": self.latency_ms,
                "created_at": self.created_at.isoformat()}
