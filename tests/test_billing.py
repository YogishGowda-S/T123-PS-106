from datetime import date
from decimal import Decimal

from src.billing import first_month_rent
from src.models import Lease


def lease(start, rent="31000"):
    return Lease("L1", "Asha", start, Decimal(rent), Decimal(rent) * 3)


def test_first_month_full_when_start_on_1st():  # BR-04
    assert first_month_rent(lease(date(2026, 1, 1))) == Decimal("31000")


def test_first_month_prorated_mid_month():  # BR-04
    # 17 days of 31 in January: 31000 x 17 / 31 = 17000
    assert first_month_rent(lease(date(2026, 1, 15))) == Decimal("17000")


def test_lease_starting_on_31st_bills_one_day():  # EC-01, BR-06
    assert first_month_rent(lease(date(2026, 1, 31))) == Decimal("1000")


def test_prorating_uses_actual_days_in_30_day_month():  # BR-06
    # April has 30 days: start on 16th = 15 days. 30000 x 15 / 30 = 15000
    assert first_month_rent(lease(date(2026, 4, 16), "30000")) == Decimal("15000")
