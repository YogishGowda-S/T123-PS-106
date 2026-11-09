"""Plain-text statements: lease state, invoices, ledger, settlement."""
from datetime import timedelta
from decimal import Decimal

from src.billing import rent_for_month
from src.money import rs, to_money


def format_lease(lease, as_of) -> str:
    rent = rent_for_month(lease, as_of.year, as_of.month)
    lines = [
        f"LEASE {lease.lease_id} | tenant: {lease.tenant} | status: {lease.status} | as of {as_of}",
        f"  term: {lease.start_date} to {lease.term_end()} ({lease.term_months} months)"
        f" | rent {rs(rent)} | deposit {rs(lease.deposit)}",
        f"  lock-in: {lease.lock_in_months} months from {lease.lock_in_start}"
        f" | notice period: {lease.notice_days} days | escalation: {lease.escalation_pct}%"
        f" | maintenance: {rs(lease.maintenance)}{' (uncapped)' if lease.uncapped else ''}",
        f"  flags: {', '.join(sorted(lease.flags)) or 'none'}"
        f" | renewed: {'yes' if lease.renewed else 'no'}"
        f" | advance credit: {rs(lease.credit)}",
    ]
    if lease.notice:
        n = lease.notice
        lines.append(f"  notice: {n['by']} on {n['date']}, vacate {n['vacate']},"
                     f" shortfall {n['shortfall_days']} day(s)")
    return "\n".join(lines)


def format_invoices(lease) -> str:
    head = (f"INVOICES {lease.lease_id}\n"
            f"  {'Period':8}{'Due':12}{'Rent':>10}{'Maint':>8}{'Total':>10}"
            f"{'Paid':>10}{'Balance':>10}{'LateFee':>9}{'Interest':>10}")
    rows = [head]
    for i in lease.invoices:
        rows.append(f"  {i.year}-{i.month:02d}  {str(i.due_date):12}{i.base_due:>10,.0f}"
                    f"{i.maint_due:>8,.0f}{i.total_due:>10,.0f}{i.rent_paid:>10,.0f}"
                    f"{i.outstanding:>10,.0f}{i.late_fee_due:>9,.0f}{i.interest_due:>10,.0f}")
    return "\n".join(rows)


def build_ledger(lease, as_of):
    rows = []  # (date, order, description, debit, credit)
    one_day = timedelta(days=1)
    for i in lease.invoices:
        tag = f"{i.year}-{i.month:02d}"
        if i.due_date <= as_of:
            rows.append((i.due_date, 0, f"Rent {tag}", i.base_due, Decimal(0)))
            if i.maint_due:
                rows.append((i.due_date, 0, f"Maintenance {tag}", i.maint_due, Decimal(0)))
        if i.late_fee_charged and i.grace_end + one_day <= as_of:
            rows.append((i.grace_end + one_day, 1, f"Late fee {tag}", Decimal(500), Decimal(0)))
        interest = to_money(i.interest_accrued)
        if interest > 0 and i.last_accrual and i.last_accrual <= as_of:
            rows.append((i.last_accrual, 1, f"Late interest {tag}", interest, Decimal(0)))
    for p in lease.payment_log:
        if p.date <= as_of:
            rows.append((p.date, 2, "Payment received", Decimal(0), p.amount))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def format_ledger(lease, as_of) -> str:
    lines = [f"LEDGER {lease.lease_id} as of {as_of}",
             f"  {'Date':12}{'Description':26}{'Debit':>10}{'Credit':>10}{'Balance':>11}"]
    balance = Decimal(0)
    for when, _, desc, debit, credit in build_ledger(lease, as_of):
        balance += debit - credit
        lines.append(f"  {str(when):12}{desc:26}{debit:>10,.0f}{credit:>10,.0f}{balance:>11,.0f}")
    lines.append(f"  Closing balance (tenant owes): {rs(balance)}")
    return "\n".join(lines)


def format_settlement(lease, s) -> str:
    out = [f"=== MOVE-OUT SETTLEMENT {s.lease_id} ({lease.tenant}) ===",
           f"Vacation date: {s.vacate_date} | Settlement date: {s.settle_date}",
           f"{'Security deposit held':62}{rs(s.deposit):>14}",
           f"{'Deductions in order of precedence':50}{'Amount':>12}{'Deposit left':>14}"]
    for n, (label, amount, balance) in enumerate(s.lines, 1):
        out.append(f"{n:>2}. {label[:56]:56}{rs(amount):>12}{rs(balance):>14}")
    out.append(f"{'Deposit interest credit':59}{rs(s.deposit_interest):>15}")
    if s.advance_credit:
        out.append(f"{'Advance credit held':59}{rs(s.advance_credit):>15}")
    if s.late_interest or s.late_days:
        out.append(f"{'Late-refund interest (' + str(s.late_days) + ' days late)':59}{rs(s.late_interest):>15}")
    for note in s.notes:
        out.append(f"Note: {note}")
    if s.net_refund >= 0:
        out.append(f"NET REFUND TO TENANT: {rs(s.net_refund)}")
    else:
        out.append(f"NET PAYABLE BY TENANT: {rs(-s.net_refund)}")
    return "\n".join(out)
