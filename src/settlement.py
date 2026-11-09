"""Move-out settlement (BR-29 to BR-38, BR-43).

Charges are applied against the deposit in the BR-43 order:
unpaid rent and interest -> notice shortfall -> lock-in forfeiture ->
inspection deductions (capped) -> deposit interest credit -> late-refund interest.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from src.billing import rent_for_month
from src.dates import add_months, days_in_month, months_between
from src.models import ZERO
from src.money import to_money
from src.payments import accrue_invoice

PAINTING_RATE = Decimal("15")      # BR-29, per sq ft
LONG_STAY_FACTOR = Decimal("0.5")  # BR-30
LONG_STAY_MONTHS = 24
DEEP_CLEANING = Decimal("3000")    # BR-31
DEPOSIT_FREE_MONTHS = 3            # BR-35
DEPOSIT_INTEREST_RATE = Decimal("0.06")
REFUND_DAYS = 15                   # BR-37
LATE_REFUND_RATE = Decimal("0.01")  # BR-38, per month


@dataclass
class Settlement:
    lease_id: str
    vacate_date: object
    settle_date: object
    deposit: Decimal
    lines: list = field(default_factory=list)   # (label, charge, deposit balance after)
    deposit_interest: Decimal = ZERO
    advance_credit: Decimal = ZERO
    late_days: int = 0
    late_interest: Decimal = ZERO
    net_before_late: Decimal = ZERO
    net_refund: Decimal = ZERO                   # negative means tenant owes
    notes: list = field(default_factory=list)
    unpaid: Decimal = ZERO                       # step 1 amount
    shortfall: Decimal = ZERO                    # step 2 amount
    forfeiture: Decimal = ZERO                   # step 3 amount
    inspection_total: Decimal = ZERO             # step 4 amount, after the cap


def compute_settlement(lease, settle_date) -> Settlement:
    vacate = lease.actual_vacated or lease.vacate_date
    notice = lease.notice or {}
    by = notice.get("by", "EXPIRY")
    rent_v = rent_for_month(lease, vacate.year, vacate.month)
    result = Settlement(lease.lease_id, vacate, settle_date, lease.deposit)
    charges = []  # (label, amount)

    # 1. Unpaid rent, interest and late fees (accrued to the vacation date, A-12)
    for inv in lease.invoices:
        accrue_invoice(inv, vacate)
    unpaid = sum((i.outstanding + i.interest_due + i.late_fee_due for i in lease.invoices), ZERO)
    charges.append(("Unpaid rent, interest and late fees", unpaid))

    # 2. Notice shortfall: rent for the missing days (BR-23, A-06)
    shortfall_days = notice.get("shortfall_days", 0) if by == "TENANT" else 0
    shortfall = ZERO
    if shortfall_days > 0:
        shortfall = to_money(rent_v * shortfall_days / days_in_month(vacate.year, vacate.month))
    label = f"Notice shortfall ({shortfall_days} days)" if shortfall_days else "Notice shortfall"
    charges.append((label, shortfall))

    # 3. Lock-in forfeiture (BR-19 to BR-21, BR-25)
    forfeit, label = ZERO, "Lock-in forfeiture"
    lock_end = add_months(lease.lock_in_start, lease.lock_in_months)
    if lease.lock_in_months > 0 and vacate <= lock_end:  # lock-in end date is inside the period (A-21)
        if by == "LANDLORD":
            label = "Lock-in forfeiture (waived: landlord notice)"
        elif by in ("TENANT", "LANDLORD-DEFAULT"):
            early = vacate <= add_months(lease.lock_in_start, 3)  # A-01: inclusive
            months = 2 if (lease.lock_in_months >= 6 and early) else 1
            forfeit = to_money(rent_v * months)
            label = f"Lock-in forfeiture ({months} month{'s' if months > 1 else ''} rent)"
    charges.append((label, forfeit))

    # 4. Inspection deductions, capped at deposit + 1 month's rent (BR-29 to BR-34)
    insp = lease.inspection
    items = []
    if insp:
        stay = months_between(lease.start_date, vacate)
        if insp["painting"]:
            rate = PAINTING_RATE if stay < LONG_STAY_MONTHS else PAINTING_RATE * LONG_STAY_FACTOR
            items.append((f"Painting ({insp['area']} sq ft)", to_money(insp["area"] * rate)))
        if insp["deep_clean"]:
            items.append(("Deep cleaning", DEEP_CLEANING))
        for desc, amount in insp["damages"]:
            items.append((f"Damage: {desc}", amount))
        if insp["wear"]:
            result.notes.append("Normal wear excluded: " + ", ".join(insp["wear"]))
    else:
        items.append(("Inspection deductions (none reported)", ZERO))
    charges.extend(items)
    total = sum((a for _, a in items), ZERO)
    cap = lease.deposit + rent_v
    if total > cap:
        charges.append(("Cap adjustment (deductions limited to deposit + 1 month rent)", cap - total))

    # Apply charges against the deposit in order
    balance = lease.deposit
    for label, amount in charges:
        balance -= amount
        result.lines.append((label, amount, balance))

    # 5. Deposit interest credit (BR-35, BR-36, A-03)
    excess = lease.deposit - DEPOSIT_FREE_MONTHS * lease.initial_rent
    if excess > 0:
        days = (vacate - lease.start_date).days
        result.deposit_interest = to_money(excess * DEPOSIT_INTEREST_RATE * days / 365)
    result.advance_credit = lease.credit
    net = balance + result.deposit_interest + lease.credit
    result.net_before_late = net
    result.unpaid = charges[0][1]
    result.shortfall = charges[1][1]
    result.forfeiture = charges[2][1]
    result.inspection_total = sum((a for _, a in charges[3:]), ZERO)

    # 6. Late-refund interest (BR-37, BR-38, A-13)
    result.late_days = max(0, (settle_date - vacate).days - REFUND_DAYS)
    if result.late_days > 0 and net > 0:
        result.late_interest = to_money(net * LATE_REFUND_RATE * result.late_days / 30)
    result.net_refund = net + result.late_interest
    return result
