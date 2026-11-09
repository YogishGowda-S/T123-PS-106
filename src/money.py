"""Money helpers. All amounts are Decimal, rounded half-up to 2 places (BR-44)."""
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def to_money(amount) -> Decimal:
    """Round to paise (2 decimals), half-up (BR-44, A-08)."""
    return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def rs(amount) -> str:
    """Format for printing, e.g. Rs 12,500.00."""
    return f"Rs {Decimal(amount):,.2f}"
