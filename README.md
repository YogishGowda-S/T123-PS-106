# T123-PS-106: Rental Agreement, Escalation, Deposit and Move-out Settlement Engine

Capstone project, 10 SECONDS placement training.
Team T123: Yashwanth K S (1AT24IS224), Yogish Gowda S (1AT24IS225), ISE D.

A command-file driven engine that creates leases, bills monthly rent with escalation and maintenance, handles payments, late fees and DEFAULT, processes notice, break, renewal and extension events, and prints the move-out settlement from the security deposit.

## Requirements

- Python 3.10 or newer
- pytest (`pip install -r requirements.txt`)

## How to run

```
python main.py data/sample_leases.csv data/sample_payments.csv data/sample_events.csv
```

The engine processes payments and events in date order (payments first on the same day) and prints a log of every command, rejected commands with the reason, and any `PRINT_*` output. If the events file has no `PRINT_*` command, it prints every lease's state, invoices and ledger at the end.

## How to run the tests

```
pip install -r requirements.txt
pytest
```

Every test is tagged with the business rule (BR-xx) or edge case (EC-xx) it checks.

## Input files (CSV)

**leases.csv**: `lease_id, tenant, start_date, term_months, base_rent, deposit, lock_in_months, notice_days, escalation_pct, maintenance, uncapped`
Dates are `YYYY-MM-DD`. `uncapped` is `Y` for the UNCAPPED flag. Blank cells use defaults (11 months, 30 days, 5%).

**payments.csv**: `date, lease_id, amount`

**events.csv**: `date, type, lease_id, params` (params are `key=value` pairs separated by `;`)

| type | params |
|---|---|
| NOTICE | `by=TENANT or LANDLORD; vacate=YYYY-MM-DD` |
| BREAK | none (tenant vacates that day) |
| RENEW_OFFER | none |
| RENEW_ACCEPT | optional `new_rent; negotiated=Y; lock_in; months` |
| EXTEND | `months` |
| INSPECTION | `area; painting=Y; deep_clean=Y; damage=Description:Amount (repeatable); wear=Description (repeatable)` |
| SETTLE | none |
| PRINT_LEASE, PRINT_INVOICES, PRINT_LEDGER, PRINT_SETTLEMENT | none |

## Project structure

```
src/dates.py        month and date helpers
src/money.py        Decimal rounding (half-up) and formatting
src/models.py       Lease, Invoice, Payment (BR-01, BR-02)
src/billing.py      pro-rating, escalation, maintenance, invoices
src/payments.py     late fee, interest, payment order, DEFAULT
src/events.py       notice, break, renewal, extension, inspection, settle
src/settlement.py   move-out settlement and precedence (BR-43)
src/engine.py       command runner
src/printer.py      lease state, invoices, ledger, settlement statement
tests/              pytest suite
data/               sample input files
docs/               design document (PDF)
decision_log.md
```

## Status

| Week | Status |
|---|---|
| 1. Design document | Done (see docs/) |
| 2. Core flows | Done |
| 3. Full rules and edge cases | Done, all 44 rules and 8 edge cases tested |
| 4. Final documentation and demo | In progress |
