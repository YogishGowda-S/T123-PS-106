from decimal import Decimal

from src.money import to_money


def test_rounds_half_up_to_two_places():  # BR-44
    assert to_money(Decimal("2.345")) == Decimal("2.35")
    assert to_money(Decimal("2.344")) == Decimal("2.34")
    assert to_money(Decimal("774.1935")) == Decimal("774.19")
