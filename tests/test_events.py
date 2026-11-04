from datetime import date, timedelta

import pytest

from src import events as ev
from tests.helpers import D, make_lease


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


def test_break_is_notice_and_vacation_on_the_same_day():
    lease = make_lease()
    ev.break_lease(lease, date(2026, 3, 10))
    assert lease.vacate_date == date(2026, 3, 10)
    assert lease.notice["shortfall_days"] == 30


def test_billing_stops_at_vacation_date():  # BR-05
    lease = make_lease()
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 3, 31))
    assert lease.invoices[-1].month == 3
    assert len(lease.invoices) == 3


def test_second_notice_rejected():
    lease = make_lease()
    ev.give_notice(lease, date(2026, 3, 1), "TENANT", date(2026, 3, 31))
    with pytest.raises(ev.RuleError):
        ev.give_notice(lease, date(2026, 3, 2), "TENANT", date(2026, 4, 5))


def test_default_triggers_termination_notice():  # BR-18
    lease = make_lease()
    message = ev.default_notice(lease, date(2026, 3, 10))
    assert "DEFAULT" in message
    assert lease.status == "NOTICE_GIVEN"
    assert lease.notice["vacate"] == date(2026, 3, 10) + timedelta(days=60)


# ---- renewal ----
def offer(lease, when=date(2026, 10, 1)):
    ev.make_offer(lease, when)


def test_renewal_offered_45_days_before_expiry():  # BR-39
    lease = make_lease()                       # term ends 2026-11-30
    ev.make_offer(lease, date(2026, 10, 16))   # exactly 45 days before
    assert lease.status == "RENEWAL_OFFERED"


def test_renewal_offer_too_late_rejected():  # BR-39
    lease = make_lease()
    with pytest.raises(ev.RuleError):
        ev.make_offer(lease, date(2026, 10, 20))


def test_renewal_with_exactly_10_percent_increase_accepted():  # EC-07, BR-42
    lease = make_lease()
    offer(lease)
    ev.accept_renewal(lease, date(2026, 10, 5), new_rent=D("11000"))
    assert lease.status == "ACTIVE" and lease.renewed


def test_renewal_above_10_percent_needs_negotiated_flag():  # BR-41
    lease = make_lease()
    offer(lease)
    with pytest.raises(ev.RuleError):
        ev.accept_renewal(lease, date(2026, 10, 5), new_rent=D("11001"))
    assert lease.status == "RENEWAL_OFFERED"
    ev.accept_renewal(lease, date(2026, 10, 6), new_rent=D("11001"), negotiated=True)
    assert lease.status == "ACTIVE"


def test_renewal_resets_lock_in_to_zero():  # BR-40
    lease = make_lease(lock_in_months=6)
    offer(lease)
    ev.accept_renewal(lease, date(2026, 10, 5))
    assert lease.lock_in_months == 0


def test_renewal_can_specify_a_new_lock_in():  # BR-40
    lease = make_lease(lock_in_months=6)
    offer(lease)
    ev.accept_renewal(lease, date(2026, 10, 5), lock_in=3)
    assert lease.lock_in_months == 3


def test_renewal_extends_term_and_adds_invoices():
    lease = make_lease()
    offer(lease)
    ev.accept_renewal(lease, date(2026, 10, 5))
    assert lease.term_end() == date(2027, 10, 31)
    assert len(lease.invoices) == 22


def test_renewed_lease_escalates_after_12_months():  # BR-07
    lease = make_lease()
    offer(lease)
    ev.accept_renewal(lease, date(2026, 10, 5))
    jan27 = next(i for i in lease.invoices if (i.year, i.month) == (2027, 1))
    assert jan27.base_due == D("10500")


def test_default_blocks_renewal():  # BR-17
    lease = make_lease()
    lease.flags.add("DEFAULT")
    with pytest.raises(ev.RuleError):
        ev.make_offer(lease, date(2026, 10, 1))


def test_accept_without_offer_rejected():
    lease = make_lease()
    with pytest.raises(ev.RuleError):
        ev.accept_renewal(lease, date(2026, 10, 5))


def test_extension_adds_months():
    lease = make_lease()
    ev.extend_term(lease, date(2026, 6, 1), 3)
    assert lease.term_end() == date(2027, 2, 28)
