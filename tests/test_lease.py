from datetime import date
from decimal import Decimal

import pytest

from src.models import Lease


def make(deposit, **kw):
    return Lease("L1", "Asha", date(2026, 1, 1), Decimal("10000"), Decimal(deposit), **kw)


def test_default_term_is_11_months():  # BR-01
    assert make("30000").term_months == 11


def test_deposit_two_months_accepted():  # BR-02 lower boundary
    make("20000")


def test_deposit_ten_months_accepted():  # BR-02 upper boundary
    make("100000")


def test_deposit_below_two_months_rejected():  # BR-02
    with pytest.raises(ValueError):
        make("19999")


def test_deposit_above_ten_months_rejected():  # BR-02
    with pytest.raises(ValueError):
        make("100001")


def test_invalid_notice_period_rejected():  # BR-22
    with pytest.raises(ValueError):
        make("30000", notice_days=45)
