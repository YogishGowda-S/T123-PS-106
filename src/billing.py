"""Invoice calculations: pro-rating, escalation, maintenance (BR-03 to BR-10, BR-26 to BR-28)."""
from datetime import date, timedelta
from decimal import Decimal

from src.dates import days_in_month
from src.models import Invoice
from src.money import to_money

MAINTENANCE_CAP = Decimal("0.10")  # BR-28: 10% of rent


def first_month_rent(lease) -> Decimal:
    """BR-04: base rent x days occupied / days in month, rounded to rupee."""
    start = lease.start_date
    dim = days_in_month(start.year, start.month)
    days_occupied = dim - start.day + 1
    return to_money(lease.base_rent * days_occupied / dim)


def rent_for_month(lease, year: int, month: int) -> Decimal:
    """Base rent for a billing month, with escalation (BR-07 to BR-10).

    Escalation applies only to renewed leases, on each 12-month anniversary of
    the rent period, to base rent only.
    """
    period_start, rent = lease.rent_periods[0]
    for p_start, p_rent in lease.rent_periods:
        if (p_start.year, p_start.month) <= (year, month):
            period_start, rent = p_start, p_rent
    if not lease.renewed:
        return rent
    months_since = (year - period_start.year) * 12 + (month - period_start.month)
    for _ in range(max(0, months_since) // 12):
        rent = to_money(rent * (1 + lease.escalation_pct / 100))
    return rent


def _billing_months(lease):
    end = lease.effective_end()
    year, month = lease.start_date.year, lease.start_date.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            year, month = year + 1, 1


def sync_invoices(lease) -> None:
    """(Re)build the invoice list, keeping payments already applied.

    Called whenever the billable period changes (creation, notice, renewal).
    """
    end = lease.effective_end()
    existing = {(i.year, i.month): i for i in lease.invoices}
    result = []
    for year, month in _billing_months(lease):
        dim = days_in_month(year, month)
        period_start = max(date(year, month, 1), lease.start_date)
        period_end = min(date(year, month, dim), end)
        days = (period_end - period_start).days + 1
        if days <= 0:
            continue
        rent = rent_for_month(lease, year, month)
        # BR-28: cap at 10% of full-month rent unless UNCAPPED; BR-26: no markup
        maint = lease.maintenance_actuals.get((year, month), lease.maintenance)
        if not lease.uncapped:
            maint = min(maint, rent * MAINTENANCE_CAP)
        if days == dim:
            base_due, maint_due = rent, to_money(maint)
        else:  # BR-04, BR-05, BR-27: pro-rate by actual days
            base_due = to_money(rent * days / dim)
            maint_due = to_money(maint * days / dim)
        due = date(year, month, 5)  # BR-03
        if (year, month) == (lease.start_date.year, lease.start_date.month) \
                and lease.start_date > due:
            due = lease.start_date  # first invoice cannot fall due before the lease starts
        grace_end = due + timedelta(days=5)  # the 10th (BR-11)
        inv = existing.pop((year, month), None)
        if inv is None:
            inv = Invoice(lease.lease_id, year, month, days, due, grace_end,
                          base_due, maint_due)
        else:
            inv.days, inv.due_date, inv.grace_end = days, due, grace_end
            inv.base_due, inv.maint_due = base_due, maint_due
        excess = inv.rent_paid - inv.total_due
        if excess > 0:  # payment made for an amount that no longer falls due
            lease.credit += excess
            inv.rent_paid -= excess
        result.append(inv)
    for dropped in existing.values():
        lease.credit += dropped.rent_paid
    lease.invoices = sorted(result, key=lambda i: (i.year, i.month))
