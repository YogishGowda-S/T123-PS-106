"""Domain models: Lease, Invoice, Payment.

Lease creation rules live here (BR-01, BR-02).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from src.dates import add_months
from src.money import to_rupees

ZERO = Decimal("0")
LATE_FEE = Decimal("500")  # BR-12


@dataclass
class Invoice:
    lease_id: str
    year: int
    month: int
    days: int
    due_date: date
    grace_end: date
    base_due: Decimal
    maint_due: Decimal
    rent_paid: Decimal = ZERO
    interest_accrued: Decimal = ZERO
    interest_paid: Decimal = ZERO
    late_fee_charged: bool = False
    late_fee_paid: Decimal = ZERO
    last_accrual: Optional[date] = None

    @property
    def total_due(self) -> Decimal:
        return self.base_due + self.maint_due

    @property
    def outstanding(self) -> Decimal:
        return max(ZERO, self.total_due - self.rent_paid)

    @property
    def interest_due(self) -> Decimal:
        return max(ZERO, to_rupees(self.interest_accrued) - self.interest_paid)

    @property
    def late_fee_due(self) -> Decimal:
        charged = LATE_FEE if self.late_fee_charged else ZERO
        return max(ZERO, charged - self.late_fee_paid)


@dataclass
class Payment:
    date: date
    amount: Decimal
    applied: dict


@dataclass
class Lease:
    lease_id: str
    tenant: str
    start_date: date
    base_rent: Decimal
    deposit: Decimal
    term_months: int = 11              # BR-01: standard term is 11 months
    lock_in_months: int = 0
    notice_days: int = 30              # 30 or 60 per lease (BR-22)
    escalation_pct: Decimal = Decimal("5")   # BR-07 / BR-08
    uncapped: bool = False             # UNCAPPED flag (BR-28)
    status: str = "DRAFT"
    flags: set = field(default_factory=set)  # e.g. {"DEFAULT"}
    maintenance: Decimal = ZERO        # society maintenance at actuals (BR-26)

    # Runtime state, set up in __post_init__
    initial_rent: Decimal = field(init=False)
    rent_periods: list = field(init=False)     # [(from_date, base_rent)]
    lock_in_start: date = field(init=False)
    renewed: bool = field(init=False, default=False)
    vacate_date: Optional[date] = field(init=False, default=None)
    notice: Optional[dict] = field(init=False, default=None)
    offer_made: bool = field(init=False, default=False)
    inspection: Optional[dict] = field(init=False, default=None)
    credit: Decimal = field(init=False, default=ZERO)
    invoices: list = field(init=False, default_factory=list)
    payment_log: list = field(init=False, default_factory=list)
    settlement: object = field(init=False, default=None)

    def __post_init__(self):
        self.base_rent = Decimal(str(self.base_rent))
        self.deposit = Decimal(str(self.deposit))
        self.escalation_pct = Decimal(str(self.escalation_pct))
        self.maintenance = Decimal(str(self.maintenance))
        if self.base_rent <= 0:
            raise ValueError("Base rent must be positive")
        if self.term_months <= 0:
            raise ValueError("Term must be at least 1 month")
        if self.lock_in_months < 0 or self.maintenance < 0 or self.escalation_pct < 0:
            raise ValueError("Lock-in, maintenance and escalation cannot be negative")
        # BR-02: deposit must be 2 to 10 months' base rent
        if not (2 * self.base_rent <= self.deposit <= 10 * self.base_rent):
            raise ValueError("Deposit must be between 2 and 10 months' rent")
        if self.notice_days not in (30, 60):
            raise ValueError("Notice period must be 30 or 60 days")
        self.initial_rent = self.base_rent
        self.rent_periods = [(self.start_date, self.base_rent)]
        self.lock_in_start = self.start_date

    def term_end(self) -> date:
        """Last day of the current term."""
        return add_months(self.start_date, self.term_months) - timedelta(days=1)

    def effective_end(self) -> date:
        """Last billable day: term end, or the vacation date if earlier (BR-05)."""
        end = self.term_end()
        if self.vacate_date and self.vacate_date < end:
            end = self.vacate_date
        return end
