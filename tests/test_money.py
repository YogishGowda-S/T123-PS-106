from decimal import Decimal

from src.money import to_rupees


def test_rounds_half_up():  # BR-44
    assert to_rupees(Decimal("2.5")) == Decimal("3")
    assert to_rupees(Decimal("3.5")) == Decimal("4")
    assert to_rupees(Decimal("2.49")) == Decimal("2")
