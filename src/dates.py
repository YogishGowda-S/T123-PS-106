"""Date helpers. Month lengths always come from the real calendar (BR-06)."""
import calendar
from datetime import date


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def add_months(d: date, n: int) -> date:
    """Add n months, clamping the day (31 Jan + 1 month = 28/29 Feb)."""
    index = d.year * 12 + (d.month - 1) + n
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(d.day, days_in_month(year, month)))


def months_between(a: date, b: date) -> int:
    """Whole months from a to b."""
    months = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        months -= 1
    return months
