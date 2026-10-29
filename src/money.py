"""Money helpers. All amounts are Decimal; never use float (BR-44)."""
from decimal import Decimal, ROUND_HALF_UP


def to_rupees(amount) -> Decimal:
    """Round to a whole rupee, half-up (BR-44)."""
    return Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
