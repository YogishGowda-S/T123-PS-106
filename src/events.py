"""Lease events: notice, break, renewal, extension, inspection, settlement."""
from datetime import timedelta
from decimal import Decimal

from src.billing import rent_for_month, sync_invoices
from src.settlement import compute_settlement

LANDLORD_MIN_NOTICE = 60                   # BR-24
OFFER_LEAD_DAYS = 45                       # BR-39
RENEWAL_INCREASE_LIMIT = Decimal("10")     # BR-41, percent


class RuleError(Exception):
    """A command that breaks a business rule; reported, state unchanged."""


def give_notice(lease, when, by, vacate) -> str:
    if by not in ("TENANT", "LANDLORD"):
        raise RuleError("notice 'by' must be TENANT or LANDLORD")
    if lease.status not in ("ACTIVE", "RENEWAL_OFFERED"):
        raise RuleError(f"notice not allowed while lease is {lease.status}")
    if vacate < when:
        raise RuleError("vacation date is before the notice date")
    given = (vacate - when).days
    if by == "LANDLORD":
        if given < LANDLORD_MIN_NOTICE:  # BR-24
            raise RuleError(f"landlord notice must be at least {LANDLORD_MIN_NOTICE} days, got {given}")
        shortfall = 0
    else:
        shortfall = max(0, lease.notice_days - given)  # BR-22, BR-23
    lease.notice = {"date": when, "vacate": vacate, "by": by, "shortfall_days": shortfall}
    lease.vacate_date = vacate
    lease.offer_made = False
    lease.status = "NOTICE_GIVEN"
    sync_invoices(lease)
    text = f"{by.lower()} notice accepted, vacating {vacate} ({given} days notice)"
    if shortfall:
        text += f", {shortfall} day(s) short of the {lease.notice_days}-day period"
    return text


def break_lease(lease, when) -> str:
    """Tenant leaves immediately: notice given and vacated on the same day."""
    return give_notice(lease, when, "TENANT", when)


def default_notice(lease, when):
    """DEFAULT triggers a termination notice (BR-18): 60 days from today."""
    if lease.notice is not None or lease.status not in ("ACTIVE", "RENEWAL_OFFERED"):
        return None
    vacate = when + timedelta(days=LANDLORD_MIN_NOTICE)
    lease.notice = {"date": when, "vacate": vacate, "by": "LANDLORD-DEFAULT", "shortfall_days": 0}
    lease.vacate_date = vacate
    lease.offer_made = False
    lease.status = "NOTICE_GIVEN"
    sync_invoices(lease)
    return f"DEFAULT flag raised; termination notice issued, vacate by {vacate}"


def make_offer(lease, when) -> str:
    if "DEFAULT" in lease.flags:
        raise RuleError("lease is in DEFAULT; renewal blocked")  # BR-17
    if lease.status != "ACTIVE":
        raise RuleError(f"renewal cannot be offered while lease is {lease.status}")
    lead = (lease.term_end() - when).days
    if lead < OFFER_LEAD_DAYS:  # BR-39
        raise RuleError(f"renewal must be offered {OFFER_LEAD_DAYS} days before expiry, got {lead}")
    lease.offer_made = True
    lease.status = "RENEWAL_OFFERED"
    return f"renewal offered ({lead} days before expiry on {lease.term_end()})"


def accept_renewal(lease, when, new_rent=None, negotiated=False, lock_in=0, months=11) -> str:
    if "DEFAULT" in lease.flags:
        raise RuleError("lease is in DEFAULT; renewal blocked")  # BR-17
    if not lease.offer_made:
        raise RuleError("no renewal offer is pending")
    term_end = lease.term_end()
    current = rent_for_month(lease, term_end.year, term_end.month)
    new_start = term_end + timedelta(days=1)
    if new_rent is not None:
        if new_rent <= 0:
            raise RuleError("new rent must be positive")
        increase = (new_rent - current) / current * 100
        # BR-41 / BR-42: above 10% needs NEGOTIATED; exactly 10% is fine
        if increase > RENEWAL_INCREASE_LIMIT and not negotiated:
            raise RuleError(f"rent increase of {increase:.2f}% exceeds 10% and the lease is not NEGOTIATED")
        lease.rent_periods.append((new_start, new_rent))
    lease.renewed = True
    lease.term_months += months
    lease.lock_in_months = lock_in         # BR-40: resets to 0 unless specified
    lease.lock_in_start = new_start
    lease.offer_made = False
    lease.status = "ACTIVE"
    sync_invoices(lease)
    return f"renewal accepted, new term ends {lease.term_end()}, lock-in {lock_in} months"


def extend_term(lease, when, months) -> str:
    if lease.status not in ("ACTIVE", "RENEWAL_OFFERED"):
        raise RuleError(f"cannot extend while lease is {lease.status}")
    if months <= 0:
        raise RuleError("extension must be at least 1 month")
    lease.term_months += months
    sync_invoices(lease)
    return f"term extended by {months} months, now ends {lease.term_end()}"


def record_inspection(lease, when, area, painting, deep_clean, damages, wear) -> str:
    if lease.status == "SETTLED":
        raise RuleError("lease already settled")
    lease.inspection = {"area": area, "painting": painting, "deep_clean": deep_clean,
                        "damages": damages, "wear": wear}
    return f"inspection recorded ({len(damages)} damage item(s), {len(wear)} normal-wear item(s) excluded)"


def settle(lease, when):
    if lease.status == "SETTLED":
        raise RuleError("lease already settled")
    if lease.vacate_date is None:
        if lease.notice is None and lease.status != "DRAFT" and when >= lease.term_end():
            lease.vacate_date = lease.term_end()  # natural expiry
            lease.notice = {"date": lease.term_end(), "vacate": lease.term_end(),
                            "by": "EXPIRY", "shortfall_days": 0}
        else:
            raise RuleError("no vacation date yet; notice or expiry required before settlement")
    if when < lease.vacate_date:
        raise RuleError("cannot settle before the vacation date")
    statement = compute_settlement(lease, when)
    lease.settlement = statement
    lease.status = "SETTLED"
    return statement
