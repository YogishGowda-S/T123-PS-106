"""Lease events: notice, break, renewal, inspection, settlement."""
from datetime import timedelta
from decimal import Decimal

from src.billing import rent_for_month, sync_invoices
from src.dates import add_months
from src.settlement import compute_settlement

LANDLORD_MIN_NOTICE = 60                   # BR-24
RENEWAL_INCREASE_LIMIT = Decimal("10")     # BR-41, percent
RENEWAL_TERM_MONTHS = 11


class RuleError(Exception):
    """A command that breaks a business rule; reported, state unchanged."""


def _tenant_shortfall(lease, notice_date, vacate) -> int:
    return max(0, lease.notice_days - (vacate - notice_date).days)  # BR-22, BR-23


def give_notice(lease, when, by, vacate) -> str:
    if by not in ("TENANT", "LANDLORD"):
        raise RuleError("notice 'by' must be TENANT or LANDLORD")
    if lease.status != "ACTIVE":
        raise RuleError(f"notice not allowed while lease is {lease.status}")
    if vacate < when:
        raise RuleError("vacation date is before the notice date")
    given = (vacate - when).days
    if by == "LANDLORD":
        if given < LANDLORD_MIN_NOTICE:  # BR-24
            raise RuleError(f"landlord notice must be at least {LANDLORD_MIN_NOTICE} days, got {given}")
        shortfall = 0
    else:
        shortfall = _tenant_shortfall(lease, when, vacate)
    lease.notice = {"date": when, "vacate": vacate, "by": by, "shortfall_days": shortfall}
    lease.vacate_date = vacate
    lease.status = "NOTICE_GIVEN"
    sync_invoices(lease)
    text = f"{by.lower()} notice accepted, vacating {vacate} ({given} days notice)"
    if shortfall:
        text += f", {shortfall} day(s) short of the {lease.notice_days}-day period"
    return text


def break_lease(lease, when, vacate=None) -> str:
    """Tenant ends the lease early, effective on `vacate`.

    If the tenant already gave notice, the notice date is kept (so a break that
    meets the notice period has no shortfall); otherwise the break date counts
    as the notice date (A-14).
    """
    vacate = vacate or when
    if lease.status == "ACTIVE":
        notice_date = when
    elif lease.status in ("NOTICE_GIVEN", "TERMINATED") and lease.notice and lease.notice["by"] == "TENANT":
        notice_date = lease.notice["date"]
    else:
        raise RuleError(f"break not allowed while lease is {lease.status}")
    if vacate < notice_date:
        raise RuleError("vacation date is before the notice date")
    shortfall = _tenant_shortfall(lease, notice_date, vacate)
    lease.notice = {"date": notice_date, "vacate": vacate, "by": "TENANT", "shortfall_days": shortfall}
    lease.vacate_date = vacate
    lease.status = "NOTICE_GIVEN"
    sync_invoices(lease)
    return f"break accepted, vacating {vacate}, {shortfall} day(s) of notice short"


def accept_renewal(lease, when, new_rent, negotiated=False, lock_in=0) -> str:
    """Renewal acceptance (BR-17, BR-40 to BR-42)."""
    if "DEFAULT" in lease.flags:
        raise RuleError("lease is in DEFAULT; renewal blocked")  # BR-17
    if lease.status != "ACTIVE":
        raise RuleError(f"renewal not allowed while lease is {lease.status}")
    if new_rent <= 0:
        raise RuleError("new rent must be positive")
    term_end = lease.term_end()
    current = rent_for_month(lease, term_end.year, term_end.month)
    increase = (new_rent - current) / current * 100
    # BR-41 / BR-42: above 10% needs NEGOTIATED; exactly 10% is fine
    if increase > RENEWAL_INCREASE_LIMIT and not negotiated:
        raise RuleError(f"rent increase of {increase:.2f}% exceeds 10% and the lease is not NEGOTIATED")
    # The new rent applies from the first full month after the old term's last month (A-19)
    from datetime import date
    first_new_month = add_months(date(term_end.year, term_end.month, 1), 1)
    lease.rent_periods.append((first_new_month, new_rent))
    lease.renewed = True
    lease.term_months += RENEWAL_TERM_MONTHS
    lease.lock_in_months = lock_in         # BR-40: resets to 0 unless specified
    lease.lock_in_start = term_end + timedelta(days=1)
    sync_invoices(lease)
    return (f"renewal accepted at {new_rent} ({increase:.2f}% change), "
            f"new term ends {lease.term_end()}, lock-in {lock_in} months")


def record_inspection(lease, when, area, painting, deep_clean, damages, wear=(), vacated=None) -> str:
    if lease.status == "SETTLED":
        raise RuleError("lease already settled")
    lease.inspection = {"area": area, "painting": painting, "deep_clean": deep_clean,
                        "damages": list(damages), "wear": list(wear)}
    if vacated is not None:
        lease.actual_vacated = vacated
    return f"inspection recorded ({len(damages)} damage item(s))"


def settle(lease, when):
    if lease.status == "SETTLED":
        raise RuleError("lease already settled")
    vacate = lease.actual_vacated or lease.vacate_date
    if vacate is None:
        if lease.notice is None and lease.status == "ACTIVE" and when >= lease.term_end():
            vacate = lease.term_end()  # natural expiry
            lease.vacate_date = vacate
            lease.notice = {"date": vacate, "vacate": vacate, "by": "EXPIRY", "shortfall_days": 0}
        else:
            raise RuleError("no vacation date yet; notice or expiry required before settlement")
    if when < vacate:
        raise RuleError("cannot settle before the vacation date")
    statement = compute_settlement(lease, when)
    lease.settlement = statement
    lease.status = "SETTLED"
    return statement
