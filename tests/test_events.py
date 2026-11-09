from datetime import date

import pytest

from src import events as ev
from tests.helpers import D, make_lease


def invoice(lease, year, month):
    return next(i for i in lease.invoices if (i.year, i.month) == (year, month))


def test_landlord_notice_under_60_days_rejected():  # BR-24
    lease = make_lease()
    with pytest.raises(ev.RuleError):
        ev.give_notice(lease, date(2026, 2, 1), "LANDLORD", date(2026, 4, 1))  # 59 days
    assert lease.status == "ACTIVE"          # rejected command changes nothing


def test_landlord_notice_of_60_days_accepted():  # BR-24
    lease = make_lease()
    ev.give_notice(lease, date(2026, 2, 1), "LANDLORD", date(2026, 4, 2))      # 60 days
    assert lease.status == "NOTICE_GIVEN"
    assert lease.notice["shortfall_days"] == 0


def test_tenant_notice_shortfall_29_days_on_30_day_period():  # EC-04, BR-22, BR-23
    lease = make_lease()
    ev.give_notice(lease, date(2026, 1, 2), "TENANT", date(2026, 1, 31))       # 29 days
    assert lease.notice["shortfall_days"] == 1


def test_tenant_notice_meeting_the_period_has_no_shortfall():  # BR-22
    lease = make_lease()
    ev.give_notice(lease, date(2026, 1, 1), "TENANT", date(2026, 1, 31))       # 30 days
    assert lease.notice["shortfall_days"] == 0


def test_notice_period_of_60_days_per_lease():  # BR-22
    lease = make_lease(notice_days=60)
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 4, 15))       # 45 days
    assert lease.notice["shortfall_days"] == 15


def test_break_without_notice_counts_the_full_notice_period_as_short():  # A-14
    lease = make_lease()
    ev.break_lease(lease, date(2026, 3, 10))
    assert lease.vacate_date == date(2026, 3, 10)
    assert lease.notice["shortfall_days"] == 30


def test_break_after_notice_keeps_the_notice_date():  # A-14
    lease = make_lease(notice_days=60, lock_in_months=6)
    ev.give_notice(lease, date(2026, 7, 1), "TENANT", date(2026, 9, 1))
    ev.break_lease(lease, date(2026, 9, 1), date(2026, 9, 1))
    assert lease.notice["shortfall_days"] == 0


def test_billing_stops_at_vacation_date():  # BR-05
    lease = make_lease()
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 3, 31))
    assert lease.invoices[-1].month == 3
    assert len(lease.invoices) == 3


def test_billing_continues_to_a_vacation_date_after_the_term_ends():
    lease = make_lease(term_months=1)             # term ends 31 Jan
    ev.give_notice(lease, date(2026, 1, 2), "TENANT", date(2026, 2, 10))
    assert lease.invoices[-1].month == 2 and lease.invoices[-1].days == 10


def test_second_notice_rejected():
    lease = make_lease()
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 3, 31))
    with pytest.raises(ev.RuleError):
        ev.give_notice(lease, date(2026, 3, 2), "TENANT", date(2026, 4, 5))


# ---- renewal ----
def test_renewal_with_exactly_10_percent_increase_accepted():  # EC-07, BR-42
    lease = make_lease()
    ev.accept_renewal(lease, date(2026, 10, 5), D("11000"))
    assert lease.status == "ACTIVE" and lease.renewed


def test_renewal_above_10_percent_needs_negotiated_flag():  # BR-41
    lease = make_lease()
    with pytest.raises(ev.RuleError):
        ev.accept_renewal(lease, date(2026, 10, 5), D("11001"))
    assert not lease.renewed
    ev.accept_renewal(lease, date(2026, 10, 6), D("11001"), negotiated=True)
    assert lease.renewed


def test_renewal_resets_lock_in_to_zero():  # BR-40
    lease = make_lease(lock_in_months=6)
    ev.accept_renewal(lease, date(2026, 10, 5), D("10000"))
    assert lease.lock_in_months == 0


def test_renewal_can_specify_a_new_lock_in():  # BR-40
    lease = make_lease(lock_in_months=6)
    ev.accept_renewal(lease, date(2026, 10, 5), D("10000"), lock_in=3)
    assert lease.lock_in_months == 3


def test_renewal_extends_term_and_adds_invoices():
    lease = make_lease()
    ev.accept_renewal(lease, date(2026, 10, 5), D("10000"))
    assert lease.term_end() == date(2027, 10, 31)
    assert len(lease.invoices) == 22


def test_new_rent_applies_from_the_month_after_the_old_term():  # A-19
    lease = make_lease()                          # old term ends 30 Nov 2026
    ev.accept_renewal(lease, date(2026, 10, 5), D("11000"))
    assert invoice(lease, 2026, 11).base_due == D("10000")   # last old month, full month
    assert invoice(lease, 2026, 12).base_due == D("11000")


def test_default_blocks_renewal():  # BR-17
    lease = make_lease()
    lease.flags.add("DEFAULT")
    with pytest.raises(ev.RuleError):
        ev.accept_renewal(lease, date(2026, 10, 5), D("10000"))


def test_renewal_rejected_after_notice():
    lease = make_lease()
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 3, 31))
    with pytest.raises(ev.RuleError):
        ev.accept_renewal(lease, date(2026, 3, 5), D("10000"))
