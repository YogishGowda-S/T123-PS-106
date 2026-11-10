from datetime import date

from src import events as ev
from tests.helpers import D, make_lease, pay_all_on_due_dates


def line(statement, prefix):
    return next(l for l in statement.lines if l[0].startswith(prefix))


def tenant_exit(lease, notice, vacate):
    ev.give_notice(lease, notice, "TENANT", vacate)


def inspect(lease, area=0, painting=False, deep_clean=False, damages=(), wear=()):
    ev.record_inspection(lease, date(2026, 6, 1), D(area), painting, deep_clean,
                         list(damages), list(wear))


# ---- lock-in forfeiture ----
def test_break_in_first_3_months_of_6_month_lock_in_forfeits_2_months():  # BR-20
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 2, 15))
    s = ev.settle(lease, date(2026, 2, 15))
    assert line(s, "Lock-in")[1] == D("20000")


def test_break_at_exactly_3_months_counts_as_first_3_months():  # EC-03, A-01
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 4, 1))
    assert line(ev.settle(lease, date(2026, 4, 1)), "Lock-in")[1] == D("20000")


def test_break_after_3_months_inside_lock_in_forfeits_1_month():  # BR-19
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 4, 2))
    assert line(ev.settle(lease, date(2026, 4, 2)), "Lock-in")[1] == D("10000")


def test_short_lock_in_always_forfeits_1_month():  # BR-19
    lease = make_lease(lock_in_months=3)
    ev.break_lease(lease, date(2026, 2, 15))
    assert line(ev.settle(lease, date(2026, 2, 15)), "Lock-in")[1] == D("10000")


def test_leaving_on_the_lock_in_end_date_still_forfeits_1_month():  # BR-19, A-21
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 7, 1))        # lock-in runs to 1 July inclusive
    assert line(ev.settle(lease, date(2026, 7, 1)), "Lock-in")[1] == D("10000")


def test_leaving_after_lock_in_has_no_forfeiture():  # BR-21
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 7, 2))
    assert line(ev.settle(lease, date(2026, 7, 2)), "Lock-in")[1] == D("0")


def test_landlord_notice_waives_lock_in_forfeiture():  # BR-25
    lease = make_lease(lock_in_months=6)
    ev.give_notice(lease, date(2026, 2, 1), "LANDLORD", date(2026, 4, 2))
    s = ev.settle(lease, date(2026, 4, 2))
    label, amount, _ = line(s, "Lock-in")
    assert amount == D("0") and "waived" in label


# ---- notice shortfall ----
def test_notice_shortfall_charged_as_rent_for_missing_days():  # BR-23, EC-04
    lease = make_lease(rent="31000", deposit="93000")
    tenant_exit(lease, date(2026, 1, 2), date(2026, 1, 31))   # 29 days, 1 short
    assert line(ev.settle(lease, date(2026, 1, 31)), "Notice shortfall")[1] == D("1000")


def test_landlord_notice_has_no_shortfall_charge():  # BR-24
    lease = make_lease()
    ev.give_notice(lease, date(2026, 2, 1), "LANDLORD", date(2026, 4, 2))
    assert line(ev.settle(lease, date(2026, 4, 2)), "Notice shortfall")[1] == D("0")


# ---- unpaid rent ----
def test_unpaid_rent_interest_and_late_fee_deducted_first():  # BR-43
    lease = make_lease()
    tenant_exit(lease, date(2026, 1, 1), date(2026, 1, 31))
    s = ev.settle(lease, date(2026, 1, 31))
    unpaid = line(s, "Unpaid")[1]
    assert unpaid > D("10000")                    # rent plus late fee and interest


# ---- inspection ----
def test_painting_rs15_per_sqft_for_short_stay():  # BR-29
    lease = make_lease()
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    pay_all_on_due_dates(lease)
    inspect(lease, area=800, painting=True)
    assert line(ev.settle(lease, date(2026, 5, 31)), "Painting")[1] == D("12000")


def test_painting_half_rate_after_24_months():  # BR-30
    lease = make_lease(start=date(2024, 1, 1), term_months=30)
    tenant_exit(lease, date(2026, 3, 1), date(2026, 3, 31))
    inspect(lease, area=1000, painting=True)
    assert line(ev.settle(lease, date(2026, 3, 31)), "Painting")[1] == D("7500")


def test_deep_cleaning_flat_3000():  # BR-31
    lease = make_lease()
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    inspect(lease, deep_clean=True)
    assert line(ev.settle(lease, date(2026, 5, 31)), "Deep")[1] == D("3000")


def test_itemised_damages_at_listed_amounts():  # BR-32
    lease = make_lease()
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    inspect(lease, damages=[("Door", D("1200")), ("Tap", D("300"))])
    s = ev.settle(lease, date(2026, 5, 31))
    assert line(s, "Damage: Door")[1] == D("1200")
    assert line(s, "Damage: Tap")[1] == D("300")


def test_normal_wear_is_excluded():  # BR-33
    lease = make_lease()
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    inspect(lease, wear=["Faded paint"])
    s = ev.settle(lease, date(2026, 5, 31))
    assert not any("Faded" in l[0] for l in s.lines)
    assert any("Faded paint" in n for n in s.notes)


def test_inspection_deductions_capped_at_deposit_plus_one_month():  # EC-06, BR-34
    lease = make_lease()                           # deposit 30000, rent 10000
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    pay_all_on_due_dates(lease)
    inspect(lease, damages=[("Structural", D("50000"))])
    s = ev.settle(lease, date(2026, 5, 31))
    charged = line(s, "Damage")[1] + line(s, "Cap adjustment")[1]
    assert charged == D("40000")
    assert s.net_refund == D("-10000")             # tenant owes the 1 month beyond deposit


# ---- deposit interest ----
def test_deposit_interest_on_excess_over_3_months():  # BR-35
    lease = make_lease(deposit="50000")
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    pay_all_on_due_dates(lease)
    s = ev.settle(lease, date(2026, 5, 31))
    assert s.deposit_interest == D("493.15")       # 20000 x 6% x 150 / 365


def test_no_deposit_interest_when_deposit_is_exactly_3_months():  # EC-05, BR-36
    lease = make_lease(deposit="30000")
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    pay_all_on_due_dates(lease)
    assert ev.settle(lease, date(2026, 5, 31)).deposit_interest == D("0")


# ---- refund timing ----
def settled_on(days_after_vacation):
    lease = make_lease()
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    pay_all_on_due_dates(lease)
    from datetime import timedelta
    return ev.settle(lease, date(2026, 5, 31) + timedelta(days=days_after_vacation))


def test_refund_within_15_days_has_no_late_interest():  # BR-37
    s = settled_on(15)
    assert s.late_interest == D("0") and s.net_refund == D("30000")


def test_late_refund_earns_1_percent_per_month():  # BR-38
    s = settled_on(25)                             # 10 days late
    assert s.late_interest == D("100")             # 30000 x 1% x 10 / 30
    assert s.net_refund == D("30100")


# ---- precedence and rounding ----
def test_charges_follow_precedence_order():  # BR-43
    lease = make_lease(lock_in_months=6)
    tenant_exit(lease, date(2026, 3, 1), date(2026, 3, 10))   # short notice, in lock-in
    inspect(lease, area=100, painting=True, damages=[("Door", D("500"))])
    labels = [l[0] for l in ev.settle(lease, date(2026, 3, 10)).lines]
    order = ["Unpaid", "Notice shortfall", "Lock-in", "Painting", "Damage"]
    positions = [next(i for i, text in enumerate(labels) if text.startswith(p)) for p in order]
    assert positions == sorted(positions)


def test_deposit_balance_runs_down_with_each_charge():  # BR-43
    lease = make_lease(lock_in_months=6)
    ev.break_lease(lease, date(2026, 2, 15))
    s = ev.settle(lease, date(2026, 2, 15))
    balances = [b for _, _, b in s.lines]
    assert balances[0] == s.deposit - s.lines[0][1]
    assert balances == sorted(balances, reverse=True)


def test_natural_expiry_has_no_forfeiture_or_shortfall():
    lease = make_lease(lock_in_months=6)
    pay_all_on_due_dates(lease)
    s = ev.settle(lease, date(2026, 12, 5))
    assert line(s, "Lock-in")[1] == D("0") and line(s, "Notice")[1] == D("0")


def test_cannot_settle_before_vacation_or_twice():
    import pytest
    lease = make_lease()
    with pytest.raises(ev.RuleError):
        ev.settle(lease, date(2026, 5, 1))         # no notice, not expired
    tenant_exit(lease, date(2026, 5, 1), date(2026, 5, 31))
    with pytest.raises(ev.RuleError):
        ev.settle(lease, date(2026, 5, 20))        # before vacation date
    ev.settle(lease, date(2026, 6, 1))
    with pytest.raises(ev.RuleError):
        ev.settle(lease, date(2026, 6, 2))


def test_cap_can_be_switched_to_cover_all_deductions_together():  # BR-34, A-07
    from src import settlement
    lease = make_lease()                           # deposit 30000, rent 10000, cap 40000
    tenant_exit(lease, date(2026, 1, 2), date(2026, 1, 31))   # January rent is unpaid
    inspect(lease, damages=[("Structural", D("50000"))])
    settlement.CAP_APPLIES_TO_ALL_DEDUCTIONS = True
    try:
        s = ev.settle(lease, date(2026, 1, 31))
    finally:
        settlement.CAP_APPLIES_TO_ALL_DEDUCTIONS = False
    assert s.unpaid + s.shortfall + s.forfeiture + s.inspection_total == D("40000")
    assert s.inspection_total < D("40000")
