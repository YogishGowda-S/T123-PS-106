"""Payments, late fee, interest and DEFAULT (BR-11 to BR-18)."""
from datetime import timedelta
from decimal import Decimal

from src.models import Payment, ZERO

INTEREST_RATE_PER_MONTH = Decimal("0.02")  # BR-13
DEFAULT_DAYS = 60                          # BR-16


def accrue_invoice(inv, upto) -> None:
    """Charge late fee and interest on an invoice up to a date.

    Grace runs to the 10th inclusive (BR-11). From the 11th: flat late fee, once
    per invoice (BR-12), plus 2% a month simple interest on overdue rent,
    computed daily as rent x 2% x days / 30 (BR-13, A-02).
    """
    if upto <= inv.grace_end:
        return
    if inv.outstanding > 0 and not inv.late_fee_charged:
        inv.late_fee_charged = True
    start = inv.last_accrual or inv.grace_end
    days = (upto - start).days
    if days > 0:
        if inv.outstanding > 0:
            inv.interest_accrued += inv.outstanding * INTEREST_RATE_PER_MONTH * days / 30
        inv.last_accrual = upto


def accrue_all(lease, upto) -> None:
    for inv in lease.invoices:
        accrue_invoice(inv, upto)


def apply_payment(lease, when, amount) -> dict:
    """Apply a payment: interest, then late fee, then oldest rent (BR-14).

    Interest and late fees are cleared across all invoices before any rent is
    reduced, so a payment that covers only interest and late fee leaves rent
    unchanged (BR-15).
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    accrue_all(lease, when)
    remaining = amount
    applied = {"interest": ZERO, "late_fee": ZERO, "rent": ZERO, "credit": ZERO}

    for inv in lease.invoices:                       # 1. interest
        part = min(remaining, inv.interest_due)
        inv.interest_paid += part
        applied["interest"] += part
        remaining -= part
    for inv in lease.invoices:                       # 2. late fee
        part = min(remaining, inv.late_fee_due)
        inv.late_fee_paid += part
        applied["late_fee"] += part
        remaining -= part
    for inv in lease.invoices:                       # 3. oldest rent first
        part = min(remaining, inv.outstanding)
        inv.rent_paid += part
        applied["rent"] += part
        remaining -= part
    if remaining > 0:                                # overpayment kept as credit
        lease.credit += remaining
        applied["credit"] = remaining
    lease.payment_log.append(Payment(when, amount, applied))
    return applied


def check_default(lease, as_of) -> bool:
    """Raise the DEFAULT flag if any invoice has been unpaid 60+ days (BR-16).

    Days are counted from the invoice due date (A-04). Returns True only when
    the flag is newly raised.
    """
    if "DEFAULT" in lease.flags or lease.status in ("DRAFT", "SETTLED"):
        return False
    for inv in lease.invoices:
        if inv.outstanding > 0 and (as_of - inv.due_date).days >= DEFAULT_DAYS:
            lease.flags.add("DEFAULT")
            return True
    return False
