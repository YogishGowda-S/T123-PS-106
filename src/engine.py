"""Command engine for the PS-106 sample-pack formats.

Reads leases.csv, maintenance_actuals.csv, damage_rate_card.csv and
commands.txt (COMMAND|arg|arg lines, processed strictly in file order) and
collects the rows for invoices.csv, ledger.csv, settlements.csv and
lease_state.csv.
"""
from dataclasses import replace
from decimal import Decimal

from src import events as ev
from src.billing import rent_for_month, sync_invoices
from src.models import Lease, ZERO
from src.parser import parse_date, parse_timestamp, truthy
from src.payments import accrue_all, accrue_invoice, apply_payment, check_default
from src.printer import format_settlement
from src.dates import add_months  # noqa: F401  (kept for readers of the viva)

REJECT_DUPLICATE_PAYMENTS = True  # an identical PAYMENT line is applied only once (A-20)


class Engine:
    def __init__(self):
        self.leases = {}
        self.damage_card = {}          # item_code -> (description, amount)
        self.log = []
        self.clock = None              # latest command date seen so far
        self.ledger_rows = []
        self.settlement_rows = []
        self.state_rows = []
        self._seen_payments = set()

    # ---- loading ----
    def load_damage_card(self, rows):
        for row in rows:
            self.damage_card[row["item_code"].strip()] = (
                row["description"].strip(), Decimal(row["amount"]))

    def load_leases(self, lease_rows, maintenance_rows):
        actuals = {}
        for row in maintenance_rows:
            year, month = row["month"].strip().split("-")
            actuals.setdefault(row["lease_id"].strip(), {})[(int(year), int(month))] = \
                Decimal(row["society_maintenance"])
        for row in lease_rows:
            try:
                lease = Lease(
                    lease_id=row["lease_id"].strip(),
                    tenant=row["tenant_name"].strip(),
                    start_date=parse_date(row["start_date"]),
                    base_rent=Decimal(row["monthly_rent"]),
                    deposit=Decimal(row["deposit"]),
                    term_months=int(row.get("term_months") or 11),
                    lock_in_months=int(row.get("lock_in_months") or 0),
                    notice_days=int(row.get("notice_days") or 30),
                    escalation_pct=Decimal(row.get("escalation_pct") or 5),
                    uncapped=truthy(row.get("maintenance_uncapped")),
                    carpet_sqft=int(row.get("carpet_sqft") or 0),
                    maintenance_actuals=actuals.get(row["lease_id"].strip(), {}),
                )
                if lease.lease_id in self.leases:
                    raise ValueError("duplicate lease id")
            except (ValueError, KeyError, ArithmeticError) as err:
                self.log.append(f"REJECTED lease {row.get('lease_id', '?')}: {err}")
                continue
            sync_invoices(lease)
            self.leases[lease.lease_id] = lease

    # ---- upkeep ----
    def _tick(self, when):
        """Advance the clock (never backwards) and update lease statuses."""
        if self.clock is None or when > self.clock:
            self.clock = when
        for lease in self.leases.values():
            if lease.status == "DRAFT" and self.clock >= lease.start_date:
                lease.status = "ACTIVE"
            if lease.status == "NOTICE_GIVEN" and lease.vacate_date and self.clock >= lease.vacate_date:
                lease.status = "TERMINATED"

    def _assess_defaults(self):
        for lease in self.leases.values():
            if check_default(lease, self.clock):
                lease.default_notice_date = self.clock  # BR-18: termination notice raised
                self.log.append(f"[{self.clock}] DEFAULT {lease.lease_id}: flag raised, "
                                f"termination notice recorded")

    # ---- running ----
    def run(self, commands):
        """commands: list of (line_no, text) in file order."""
        for line_no, text in commands:
            parts = [p.strip() for p in text.split("|")]
            name = parts[0].upper()
            try:
                when = parse_timestamp(parts[1])
            except (IndexError, ValueError):
                self.log.append(f"REJECTED line {line_no}: {name} has no valid timestamp")
                if name == "PAYMENT":
                    self._ledger(line_no, parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "0",
                                 {}, "REJECTED_INVALID")
                continue
            self._tick(when)
            try:
                self._dispatch(line_no, name, when, parts)
            except ev.RuleError as err:
                self.log.append(f"REJECTED line {line_no} [{when}] {name} {parts[2] if len(parts) > 2 else ''}: {err}")
            except (ValueError, IndexError, KeyError, ArithmeticError) as err:
                self.log.append(f"REJECTED line {line_no} [{when}] {name}: invalid command ({err})")
            self._assess_defaults()

    def _dispatch(self, line_no, name, when, parts):
        lease_id = parts[2] if len(parts) > 2 else ""
        if name == "PAYMENT":
            return self._payment(line_no, when, lease_id, parts)
        lease = self.leases.get(lease_id)
        if lease is None:
            raise ev.RuleError("unknown lease")
        if name == "NOTICE":
            msg = ev.give_notice(lease, when, parts[3].upper(), parse_date(parts[4]))
        elif name == "BREAK":
            msg = ev.break_lease(lease, when, parse_date(parts[3]))
        elif name == "RENEW":
            msg = ev.accept_renewal(lease, when, Decimal(parts[3]), truthy(parts[4]), int(parts[5] or 0))
        elif name == "INSPECTION":
            msg = self._inspection(lease, when, parts)
        elif name == "SETTLE":
            statement = ev.settle(lease, parse_date(parts[3]))
            self._settlement_row(lease, statement)
            self.log.append(format_settlement(lease, statement))
            return
        elif name == "STATEMENT":
            self._statement(lease, when)
            return
        else:
            raise ev.RuleError(f"unknown command {name}")
        self.log.append(f"line {line_no} [{when}] {name} {lease_id}: {msg}")

    # ---- PAYMENT ----
    def _ledger(self, line_no, lease_id, amount, applied, status):
        amount = Decimal(str(amount or 0))
        rejected = status.startswith("REJECTED")
        self.ledger_rows.append({
            "line_no": line_no, "lease_id": lease_id, "amount": amount,
            "applied_interest": applied.get("interest", ZERO),
            "applied_late_fee": applied.get("late_fee", ZERO),
            "applied_rent": applied.get("rent", ZERO),
            "unapplied": amount if rejected else applied.get("credit", ZERO),
            "status": status})

    def _payment(self, line_no, when, lease_id, parts):
        try:
            amount = Decimal(parts[3])
            if amount <= 0:
                raise ValueError("amount must be positive")
        except (IndexError, ArithmeticError, ValueError):
            self._ledger(line_no, lease_id, "0", {}, "REJECTED_INVALID")
            raise ev.RuleError("invalid payment amount")
        lease = self.leases.get(lease_id)
        if lease is None:
            self._ledger(line_no, lease_id, amount, {}, "REJECTED_UNKNOWN_LEASE")
            raise ev.RuleError("unknown lease")
        key = (parts[1], lease_id, amount)
        if REJECT_DUPLICATE_PAYMENTS and key in self._seen_payments:
            self._ledger(line_no, lease_id, amount, {}, "REJECTED_DUPLICATE")
            raise ev.RuleError("duplicate payment ignored")
        if lease.status == "SETTLED":
            self._ledger(line_no, lease_id, amount, {}, "REJECTED_SETTLED")
            raise ev.RuleError("lease already settled")
        self._seen_payments.add(key)
        applied = apply_payment(lease, when, amount)
        unapplied = applied["credit"]
        status = "APPLIED" if unapplied == 0 else ("UNAPPLIED" if unapplied == amount else "PARTIALLY_APPLIED")
        self._ledger(line_no, lease_id, amount, applied, status)
        self.log.append(f"line {line_no} [{when}] PAYMENT {lease_id}: {amount} -> "
                        f"interest {applied['interest']}, late fee {applied['late_fee']}, "
                        f"rent {applied['rent']}, unapplied {unapplied}")

    # ---- INSPECTION ----
    def _inspection(self, lease, when, parts):
        sqft, deep, items, vacated = parts[3], parts[4], parts[5], parts[6]
        damages = []
        if items.upper() != "NONE" and items:
            for code in items.split(";"):
                code = code.strip()
                if code not in self.damage_card:
                    raise ev.RuleError(f"unknown damage item {code}")
                desc, amount = self.damage_card[code]
                damages.append((f"{code} {desc}", amount))
        painting = Decimal(sqft or 0) > 0
        area = Decimal(lease.carpet_sqft)  # painting is charged on carpet area
        return ev.record_inspection(lease, when, area, painting, truthy(deep), damages,
                                    vacated=parse_date(vacated))

    # ---- STATEMENT and settlement rows ----
    def dues(self, lease, as_of):
        """Rent, interest and late fees outstanding on invoices due by as_of (no side effects)."""
        total = ZERO
        for inv in lease.invoices:
            if inv.due_date > as_of:
                continue
            copy = replace(inv)
            accrue_invoice(copy, as_of)
            total += copy.outstanding + copy.interest_due + copy.late_fee_due
        return total

    def state(self, lease, as_of):
        if lease.status == "SETTLED":
            return "SETTLED"
        if lease.status == "NOTICE_GIVEN":
            return "TERMINATED" if as_of >= lease.vacate_date else "NOTICE_GIVEN"
        if lease.status == "DRAFT" or as_of < lease.start_date:
            return "DRAFT"
        return "EXPIRED" if as_of > lease.term_end() else "ACTIVE"

    def _statement(self, lease, as_of):
        ended = lease.status in ("SETTLED", "NOTICE_GIVEN") and lease.vacate_date
        rent_day = lease.vacate_date if ended and as_of >= lease.vacate_date else as_of
        dues = self.dues(lease, as_of)
        if lease.status == "SETTLED":      # dues were taken from the deposit at settlement
            dues = max(ZERO, -lease.settlement.net_refund)
        self.state_rows.append({
            "lease_id": lease.lease_id, "state": self.state(lease, as_of),
            "current_rent": rent_for_month(lease, rent_day.year, rent_day.month),
            "default_flag": "DEFAULT" in lease.flags, "dues_outstanding": dues})

    def _settlement_row(self, lease, s):
        self.settlement_rows.append({
            "lease_id": lease.lease_id, "vacated_date": s.vacate_date,
            "settlement_date": s.settle_date, "unpaid_rent_interest": s.unpaid,
            "notice_shortfall": s.shortfall, "lock_in_forfeiture": s.forfeiture,
            "inspection_deductions": s.inspection_total, "deposit_interest": s.deposit_interest,
            "late_refund_interest": s.late_interest, "net_refund": s.net_refund})

    def invoice_rows(self):
        rows = []
        for lease_id in sorted(self.leases):
            for inv in self.leases[lease_id].invoices:
                rows.append({"lease_id": lease_id, "month": f"{inv.year}-{inv.month:02d}",
                             "rent": inv.base_due, "maintenance": inv.maint_due,
                             "total_due": inv.total_due, "due_date": inv.due_date})
        return rows
