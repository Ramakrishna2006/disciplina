"""token_blocklist: login tokens that were logged out before they expired (used from stage 3)."""
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import UTCDateTime, utcnow


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)   # the token's unique id
    revoked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
