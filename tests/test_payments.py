from datetime import date, timedelta
from decimal import Decimal

from src.payments import accrue_all, apply_payment, check_default
from tests.helpers import D, make_lease

JAN = (2026, 1)


def jan(lease):
    return next(i for i in lease.invoices if (i.year, i.month) == JAN)


def test_payment_on_the_10th_has_no_late_fee():  # EC-02, BR-11
    lease = make_lease()
    applied = apply_payment(lease, date(2026, 1, 10), D("10000"))
    assert applied["rent"] == D("10000")
    assert not jan(lease).late_fee_charged
    assert jan(lease).interest_due == 0


def test_payment_on_the_11th_charges_fee_and_interest():  # BR-12, BR-13
    lease = make_lease()
    applied = apply_payment(lease, date(2026, 1, 11), D("10000"))
    assert applied["late_fee"] == D("500")
    assert applied["interest"] == D("7")          # 10000 x 2% x 1/30 = 6.67
    assert jan(lease).outstanding == D("507")


def test_interest_accrues_daily():  # BR-13
    lease = make_lease()
    accrue_all(lease, date(2026, 1, 31))          # 21 days overdue
    assert jan(lease).interest_due == D("140")    # 10000 x 2% x 21/30


def test_late_fee_charged_once_per_invoice():  # BR-12
    lease = make_lease()
    apply_payment(lease, date(2026, 1, 11), D("2000"))
    apply_payment(lease, date(2026, 1, 20), D("2000"))
    inv = jan(lease)
    assert inv.late_fee_paid + inv.late_fee_due == D("500")


def test_payment_order_interest_then_late_fee_then_rent():  # BR-14
    lease = make_lease()
    # Jan and Feb both overdue on 12 Feb: interest 220 + 13, late fees 500 + 500
    applied = apply_payment(lease, date(2026, 2, 12), D("1000"))
    assert applied["interest"] == D("233")
    assert applied["late_fee"] == D("767")
    assert applied["rent"] == D("0")


def test_rent_paid_oldest_invoice_first():  # BR-14
    lease = make_lease()
    apply_payment(lease, date(2026, 1, 5), D("15000"))
    assert jan(lease).outstanding == D("0")
    feb = next(i for i in lease.invoices if i.month == 2)
    assert feb.outstanding == D("5000")


def test_partial_payment_covering_interest_and_late_fee_only():  # EC-08, BR-15
    lease = make_lease()
    applied = apply_payment(lease, date(2026, 1, 11), D("507"))
    assert applied["interest"] == D("7") and applied["late_fee"] == D("500")
    assert applied["rent"] == D("0")
    assert jan(lease).outstanding == D("10000")


def test_overpayment_kept_as_credit():
    lease = make_lease()
    apply_payment(lease, date(2026, 1, 5), D("500000"))
    assert lease.credit > 0


def test_default_after_60_days_unpaid():  # BR-16
    lease = make_lease()
    due = jan(lease).due_date
    assert check_default(lease, due + timedelta(days=59)) is False
    assert check_default(lease, due + timedelta(days=60)) is True
    assert "DEFAULT" in lease.flags


def test_paid_invoice_never_defaults():  # BR-16
    lease = make_lease(term_months=1)
    apply_payment(lease, date(2026, 1, 5), D("10000"))
    assert check_default(lease, date(2026, 6, 1)) is False
