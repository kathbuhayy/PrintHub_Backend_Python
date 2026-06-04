from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC time as a naive datetime.
    asyncpg's timestamp codec requires naive datetimes — it uses its own
    offset-naive epoch internally and fails if tzinfo is present."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
