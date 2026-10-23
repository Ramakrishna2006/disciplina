"""Small helpers shared by every model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always UTC with a timezone. PostgreSQL keeps the timezone itself; SQLite drops it, so
    values read back from SQLite get UTC attached again. Either way Python sees aware datetimes."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware (use utcnow())")
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def created_at():
    return mapped_column(UTCDateTime(), default=utcnow, nullable=False)


def in_list(column, values):
    """SQL for a CHECK constraint: column IN ('a', 'b')."""
    return f"{column} IN ({', '.join(repr(v) for v in values)})"

