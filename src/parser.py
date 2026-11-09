"""Input parsing helpers."""
from datetime import date


def parse_date(text) -> date:
    return date.fromisoformat(str(text).strip())


def parse_timestamp(text) -> date:
    """'2025-04-10 11:00:00' -> date(2025, 4, 10). Only the date matters for rules."""
    return date.fromisoformat(str(text).strip()[:10])


def truthy(text) -> bool:
    return str(text or "").strip().lower() in ("true", "y", "yes", "1")
