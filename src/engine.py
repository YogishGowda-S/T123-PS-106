"""Command-file engine: loads leases, payments and events and runs them by date."""
from decimal import Decimal

from src import events as ev
from src.billing import sync_invoices
from src.models import Lease
from src.parser import first, parse_date, parse_params, truthy
from src.payments import accrue_all, apply_payment, check_default
from src.printer import format_invoices, format_lease, format_ledger, format_settlement
from src.money import rs

PRINT_COMMANDS = ("PRINT_LEASE", "PRINT_INVOICES", "PRINT_LEDGER", "PRINT_SETTLEMENT")


class Engine:
    def __init__(self):
        self.leases = {}
        self.out = []
        self.last_date = None
        self.print_commands = 0

    def log(self, text):
        self.out.append(text)

    # ---- leases ----
    def add_lease(self, row):
        try:
            lease = Lease(
                lease_id=row["lease_id"].strip(),
                tenant=row["tenant"].strip(),
                start_date=parse_date(row["start_date"]),
                base_rent=Decimal(row["base_rent"]),
                deposit=Decimal(row["deposit"]),
                term_months=int(row.get("term_months") or 11),
                lock_in_months=int(row.get("lock_in_months") or 0),
                notice_days=int(row.get("notice_days") or 30),
                escalation_pct=Decimal(row.get("escalation_pct") or 5),
                uncapped=truthy(row.get("uncapped")),
                maintenance=Decimal(row.get("maintenance") or 0),
            )
            if lease.lease_id in self.leases:
                raise ValueError("duplicate lease id")
        except (ValueError, KeyError, ArithmeticError) as err:
            self.log(f"REJECTED lease {row.get('lease_id', '?')}: {err}")
            return
        sync_invoices(lease)
        self.leases[lease.lease_id] = lease

    # ---- state upkeep ----
    def refresh(self, when):
        for lease in self.leases.values():
            if lease.status == "DRAFT" and when >= lease.start_date:
                lease.status = "ACTIVE"
            if lease.status == "NOTICE_GIVEN" and lease.vacate_date and when >= lease.vacate_date:
                lease.status = "TERMINATED"
            if lease.status in ("ACTIVE", "RENEWAL_OFFERED") and when > lease.term_end():
                lease.status = "TERMINATED"  # expired without renewal

    def assess_defaults(self, when):
        for lease in self.leases.values():
            if check_default(lease, when):
                message = ev.default_notice(lease, when) or "DEFAULT flag raised"
                self.log(f"[{when}] DEFAULT {lease.lease_id}: {message}")

    # ---- commands ----
    def pay(self, when, lease_id, amount):
        lease = self.leases.get(lease_id)
        if lease is None:
            self.log(f"REJECTED [{when}] PAYMENT {lease_id}: unknown lease")
            return
        try:
            applied = apply_payment(lease, when, amount)
        except ValueError as err:
            self.log(f"REJECTED [{when}] PAYMENT {lease_id}: {err}")
            return
        parts = ", ".join(f"{k} {rs(v)}" for k, v in applied.items() if v)
        self.log(f"[{when}] PAYMENT {lease_id}: {rs(amount)} applied -> {parts}")

    def event(self, when, etype, lease_id, params):
        kind = etype.strip().upper()
        lease = self.leases.get(lease_id)
        if lease is None:
            self.log(f"REJECTED [{when}] {kind} {lease_id}: unknown lease")
            return
        try:
            message = self._dispatch(lease, when, kind, params)
        except ev.RuleError as err:
            self.log(f"REJECTED [{when}] {kind} {lease_id}: {err}")
            return
        except (ValueError, KeyError, ArithmeticError) as err:
            self.log(f"REJECTED [{when}] {kind} {lease_id}: invalid command ({err})")
            return
        if message:
            self.log(f"[{when}] {kind} {lease_id}: {message}")

    def _dispatch(self, lease, when, kind, params):
        if kind == "NOTICE":
            by = first(params, "by", "TENANT").upper()
            return ev.give_notice(lease, when, by, parse_date(first(params, "vacate", "")))
        if kind == "BREAK":
            return ev.break_lease(lease, when)
        if kind == "RENEW_OFFER":
            return ev.make_offer(lease, when)
        if kind == "RENEW_ACCEPT":
            new_rent = first(params, "new_rent")
            return ev.accept_renewal(
                lease, when,
                new_rent=Decimal(new_rent) if new_rent else None,
                negotiated=truthy(first(params, "negotiated")),
                lock_in=int(first(params, "lock_in", 0)),
                months=int(first(params, "months", 11)))
        if kind == "EXTEND":
            return ev.extend_term(lease, when, int(first(params, "months", 0)))
        if kind == "INSPECTION":
            damages = []
            for item in params.get("damage", []):
                desc, _, amount = item.rpartition(":")
                damages.append((desc.strip(), Decimal(amount)))
            return ev.record_inspection(
                lease, when, Decimal(first(params, "area", 0)),
                truthy(first(params, "painting")), truthy(first(params, "deep_clean")),
                damages, params.get("wear", []))
        if kind == "SETTLE":
            statement = ev.settle(lease, when)
            self.log(format_settlement(lease, statement))
            return None
        if kind in PRINT_COMMANDS:
            self.print_commands += 1
            accrue_all(lease, when)
            if kind == "PRINT_LEASE":
                self.log(format_lease(lease, when))
            elif kind == "PRINT_INVOICES":
                self.log(format_invoices(lease))
            elif kind == "PRINT_LEDGER":
                self.log(format_ledger(lease, when))
            elif lease.settlement:
                self.log(format_settlement(lease, lease.settlement))
            else:
                raise ev.RuleError("lease is not settled yet")
            return None
        raise ev.RuleError(f"unknown command type {kind}")

    # ---- run ----
    def run(self, lease_rows, payment_rows, event_rows):
        for row in lease_rows:
            self.add_lease(row)
        items = []
        for n, row in enumerate(payment_rows):
            try:
                items.append((parse_date(row["date"]), 0, n, "PAY", row))
            except (ValueError, KeyError) as err:
                self.log(f"REJECTED payment row {n + 1}: {err}")
        for n, row in enumerate(event_rows):
            try:
                items.append((parse_date(row["date"]), 1, n, "EVT", row))
            except (ValueError, KeyError) as err:
                self.log(f"REJECTED event row {n + 1}: {err}")
        items.sort(key=lambda item: item[:3])  # by date, payments before events
        for when, _, _, kind, row in items:
            self.last_date = when
            self.refresh(when)
            if kind == "PAY":
                try:
                    amount = Decimal(row["amount"])
                except (ArithmeticError, KeyError):
                    self.log(f"REJECTED [{when}] PAYMENT {row.get('lease_id', '?')}: invalid amount")
                    continue
                self.pay(when, row.get("lease_id", "").strip(), amount)
            else:
                self.event(when, row.get("type", ""), row.get("lease_id", "").strip(),
                           parse_params(row.get("params", "")))
            self.assess_defaults(when)
        self.finish()

    def finish(self):
        """With no PRINT commands, print every lease's final state."""
        if self.print_commands or self.last_date is None:
            return
        for lease in self.leases.values():
            accrue_all(lease, self.last_date)
            self.log(format_lease(lease, self.last_date))
            self.log(format_invoices(lease))
            self.log(format_ledger(lease, self.last_date))
            if lease.settlement:
                self.log(format_settlement(lease, lease.settlement))
