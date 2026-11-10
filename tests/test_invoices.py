from datetime import date
from decimal import Decimal

from src.billing import rent_for_month
from tests.helpers import D, make_lease


def invoice(lease, year, month):
    return next(i for i in lease.invoices if (i.year, i.month) == (year, month))


def test_standard_lease_has_11_monthly_invoices():  # BR-01
    assert len(make_lease().invoices) == 11


def test_rent_due_on_the_5th():  # BR-03
    lease = make_lease()
    assert all(i.due_date.day == 5 for i in lease.invoices)


def test_first_month_prorated():  # BR-04
    lease = make_lease(start=date(2026, 1, 15), rent="31000", deposit="93000")
    assert invoice(lease, 2026, 1).base_due == D("17000")


def test_last_month_prorated_by_actual_days():  # BR-05
    # starts 15 Jan, 11 months ends 14 Dec: 14 of 31 days
    lease = make_lease(start=date(2026, 1, 15), rent="31000", deposit="93000")
    assert invoice(lease, 2026, 12).base_due == D("14000")


def test_start_on_31st_with_30_day_next_month():  # EC-01, BR-06
    lease = make_lease(start=date(2026, 3, 31), rent="31000", deposit="93000")
    assert invoice(lease, 2026, 3).base_due == D("1000")      # 1 of 31 days
    assert invoice(lease, 2026, 4).base_due == D("31000")     # April billed as a full month


def test_first_invoice_not_due_before_lease_starts():
    lease = make_lease(start=date(2026, 1, 20))
    first = lease.invoices[0]
    assert first.due_date == date(2026, 1, 20)
    assert first.grace_end == date(2026, 1, 25)


def test_no_escalation_for_non_renewed_lease():  # BR-07
    lease = make_lease(rent="20000", deposit="60000", term_months=30)
    assert rent_for_month(lease, 2027, 1) == D("20000")


def test_no_escalation_within_first_11_months():  # BR-10
    lease = make_lease(rent="20000", deposit="60000")
    lease.renewed = True
    assert rent_for_month(lease, 2026, 11) == D("20000")


def test_default_escalation_5_percent_each_anniversary():  # BR-07
    lease = make_lease(rent="20000", deposit="60000")
    lease.renewed = True
    assert rent_for_month(lease, 2027, 1) == D("21000")
    assert rent_for_month(lease, 2028, 1) == D("22050")


def test_lease_escalation_overrides_default():  # BR-08
    lease = make_lease(rent="20000", deposit="60000", escalation_pct=D("8"))
    lease.renewed = True
    assert rent_for_month(lease, 2027, 1) == D("21600")


def test_escalation_applies_to_base_rent_only():  # BR-09
    lease = make_lease(rent="20000", deposit="60000", term_months=24, maintenance="1000")
    lease.renewed = True
    from src.billing import sync_invoices
    sync_invoices(lease)
    jan26, jan27 = invoice(lease, 2026, 1), invoice(lease, 2027, 1)
    assert jan27.base_due == D("21000")
    assert jan27.maint_due == jan26.maint_due == D("1000")


def test_maintenance_passed_through_at_actuals():  # BR-26
    lease = make_lease(rent="10000", maintenance="800")
    assert invoice(lease, 2026, 2).maint_due == D("800")


def test_maintenance_prorated_for_partial_month():  # BR-27
    lease = make_lease(start=date(2026, 1, 16), maintenance="800")
    assert invoice(lease, 2026, 1).maint_due == D("412.90")   # 800 x 16 / 31


def test_maintenance_capped_at_10_percent_of_rent():  # BR-28
    lease = make_lease(rent="10000", maintenance="1500")
    assert invoice(lease, 2026, 2).maint_due == D("1000")


def test_uncapped_flag_removes_maintenance_cap():  # BR-28
    lease = make_lease(rent="10000", maintenance="1500", uncapped=True)
    assert invoice(lease, 2026, 2).maint_due == D("1500")


def test_rent_paid_for_a_shortened_month_is_returned_as_credit():
    # BUG FIX: the excess must be measured against base rent (payments never pay maintenance)
    from datetime import date
    from src import events as ev
    from src.payments import apply_payment
    lease = make_lease(maintenance="800")
    apply_payment(lease, date(2026, 1, 5), D("10000"))      # January in full
    apply_payment(lease, date(2026, 1, 6), D("10000"))      # February in advance
    ev.give_notice(lease, date(2026, 1, 10), "TENANT", date(2026, 1, 20))
    # January now 20 of 31 days = 6451.61; February is dropped, so both payments flow back
    assert invoice(lease, 2026, 1).base_due == D("6451.61")
    assert lease.credit == D("20000") - D("6451.61")


def test_late_fee_and_interest_paid_on_a_dropped_month_are_returned():
    # money paid on a month that is no longer billed must flow back, never vanish
    from datetime import date
    from src import events as ev
    from src.payments import apply_payment
    lease = make_lease()
    apply_payment(lease, date(2026, 2, 20), D("10000"))     # February paid 10 days late
    feb = invoice(lease, 2026, 2)                           # (the payment hits January first)
    paid_total = D("10000")
    ev.give_notice(lease, date(2026, 2, 21), "TENANT", date(2026, 2, 21))
    kept = sum((i.rent_paid + i.interest_paid + i.late_fee_paid for i in lease.invoices), D(0))
    assert kept + lease.credit == paid_total
