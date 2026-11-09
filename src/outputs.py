"""Write the four evaluation CSV files (formats from the sample-pack README)."""
import csv
import os
from decimal import Decimal

from src.money import to_money

FILES = {
    "invoices.csv": ["lease_id", "month", "rent", "maintenance", "total_due", "due_date"],
    "ledger.csv": ["line_no", "lease_id", "amount", "applied_interest", "applied_late_fee",
                   "applied_rent", "unapplied", "status"],
    "settlements.csv": ["lease_id", "vacated_date", "settlement_date", "unpaid_rent_interest",
                        "notice_shortfall", "lock_in_forfeiture", "inspection_deductions",
                        "deposit_interest", "late_refund_interest", "net_refund"],
    "lease_state.csv": ["lease_id", "state", "current_rent", "default_flag", "dues_outstanding"],
}


def _cell(value):
    if isinstance(value, bool):
        return "true" if value else "false"      # booleans are true/false
    if isinstance(value, Decimal):
        return f"{to_money(value):.2f}"          # money has 2 decimal places
    return str(value)


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(row[c]) for c in columns])


def write_all(engine, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows = {"invoices.csv": engine.invoice_rows(), "ledger.csv": engine.ledger_rows,
            "settlements.csv": engine.settlement_rows, "lease_state.csv": engine.state_rows}
    for name, columns in FILES.items():
        write_csv(os.path.join(out_dir, name), columns, rows[name])
