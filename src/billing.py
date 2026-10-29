"""Invoice calculations. Pro-rating follows BR-04 to BR-06."""
import calendar
from decimal import Decimal

from src.money import to_rupees


def days_in_month(year: int, month: int) -> int:
    """Actual days in the calendar month (BR-06)."""
    return calendar.monthrange(year, month)[1]


def first_month_rent(lease) -> Decimal:
    """BR-04: base rent x days occupied / days in month, rounded to rupee."""
    start = lease.start_date
    dim = days_in_month(start.year, start.month)
    days_occupied = dim - start.day + 1
    return to_rupees(lease.base_rent * days_occupied / dim)
