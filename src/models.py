"""Domain models. Lease creation rules live here (BR-01, BR-02)."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


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

    def __post_init__(self):
        self.base_rent = Decimal(str(self.base_rent))
        self.deposit = Decimal(str(self.deposit))
        self.escalation_pct = Decimal(str(self.escalation_pct))
        if self.base_rent <= 0:
            raise ValueError("Base rent must be positive")
        # BR-02: deposit must be 2 to 10 months' base rent
        if not (2 * self.base_rent <= self.deposit <= 10 * self.base_rent):
            raise ValueError("Deposit must be between 2 and 10 months' rent")
        if self.notice_days not in (30, 60):
            raise ValueError("Notice period must be 30 or 60 days")
