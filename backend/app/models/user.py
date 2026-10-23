"""users: one row per account."""
from datetime import datetime

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .base import UTCDateTime, created_at, in_list

ROLES = ("member", "admin")
THEMES = ("system", "light", "dark")
MODEL_CHOICES = ("base", "full", "lora")


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(in_list("role", ROLES), name="role"),
        CheckConstraint(in_list("theme", THEMES), name="theme"),
        CheckConstraint(in_list("default_model", MODEL_CHOICES), name="default_model"),
        CheckConstraint("default_temperature >= 0 AND default_temperature <= 2", name="default_temperature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    theme: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    default_model: Mapped[str] = mapped_column(String(10), default="lora", nullable=False)
    default_temperature: Mapped[float] = mapped_column(default=0.0, nullable=False)
    created_at: Mapped[datetime] = created_at()
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Login tokens issued before this moment are refused. Set when the password changes, so a
    # stolen or forgotten session on another device stops working at once.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(UTCDateTime())

    # Deleting a user deletes everything they own (the database does it: ON DELETE CASCADE).
    experiments = relationship("Experiment", back_populates="owner", cascade="all, delete-orphan",
                               passive_deletes=True)
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan",
                                 passive_deletes=True)
    activity = relationship("ActivityEvent", back_populates="user", cascade="all, delete-orphan",
                            passive_deletes=True)

    @validates("email")
    def _lower_email(self, _key, value):
        return value.strip().lower()   # "Asha@Mail.com" and "asha@mail.com" are the same account

    def set_password(self, password):
        # Werkzeug's default is scrypt with a random salt: slow to guess, and two users with the
        # same password get different hashes. The plain password is never stored.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(password) and check_password_hash(self.password_hash, password)

    def to_dict(self):
        """What the API shows about a user. Never includes the password hash."""
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role,
                "theme": self.theme, "default_model": self.default_model,
                "default_temperature": self.default_temperature,
                "created_at": self.created_at.isoformat(),
                "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None}

    def __repr__(self):
        return f"<User {self.id} {self.email}>"
