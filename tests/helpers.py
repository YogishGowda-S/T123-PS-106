"""Small builders shared by the tests."""
from datetime import date
from decimal import Decimal

from src.billing import sync_invoices
from src.models import Lease
from src.payments import apply_payment

D = Decimal


def make_lease(start=date(2026, 1, 1), rent="10000", deposit="30000", **kw):
    lease = Lease("L1", "Asha", start, D(rent), D(deposit), **kw)
    sync_invoices(lease)
    lease.status = "ACTIVE"
    return lease


def pay_all_on_due_dates(lease):
    """Pay every invoice in full on its due date (no late charges)."""
    for inv in list(lease.invoices):
        apply_payment(lease, inv.due_date, inv.total_due)
