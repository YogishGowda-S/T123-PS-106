# T123-PS-106: Rental Agreement, Escalation, Deposit and Move-out Settlement Engine

Capstone project, 10 SECONDS placement training.
Team T123: Yashwanth K S (1AT24IS224), Yogish Gowda S (1AT24IS225), ISE D.

A command-file driven engine that creates leases, bills monthly rent with escalation and maintenance, applies payments through the interest -> late fee -> rent waterfall, handles notice, break and renewal commands, flags DEFAULT, and computes the move-out settlement from the security deposit.

## Requirements

- Python 3.10 or newer
- pytest (`pip install -r requirements.txt`)

## How to run

```
python main.py data output
```

`data/` holds the input files; the four result files are written to `output/`:

| Input (in `data/`) | Content |
|---|---|
| leases.csv | lease agreements |
| maintenance_actuals.csv | society maintenance per lease-month |
| damage_rate_card.csv | damage item codes and amounts |
| commands.txt | `COMMAND\|arg\|arg` lines, processed in file order |

| Output (in `output/`) | Content |
|---|---|
| invoices.csv | one row per tenancy month per lease |
| ledger.csv | one row per PAYMENT line, with the interest / late fee / rent split |
| settlements.csv | one row per SETTLE |
| lease_state.csv | one row per STATEMENT |

The program also prints a log of every command, including each rejected command and its reason.

## Commands (commands.txt)

| Command | Arguments |
|---|---|
| PAYMENT | ts \| lease_id \| amount |
| NOTICE | ts \| lease_id \| TENANT or LANDLORD \| vacate_date |
| BREAK | ts \| lease_id \| vacate_date |
| RENEW | ts \| lease_id \| new_rent \| negotiated \| lock_in_months |
| INSPECTION | ts \| lease_id \| painting_sqft \| deep_cleaning \| damage_items \| vacated_date |
| SETTLE | ts \| lease_id \| settlement_date |
| STATEMENT | ts \| lease_id |

## How to run the tests

```
pip install -r requirements.txt
pytest
```

Every test is tagged with the business rule (BR-xx) or edge case (EC-xx) it checks. `tests/test_engine.py` runs the whole sample pack end to end.

## Project structure

```
main.py             entry point
src/dates.py        month and date helpers
src/money.py        Decimal rounding (half-up, 2 places)
src/models.py       Lease, Invoice, Payment (BR-01, BR-02)
src/billing.py      pro-rating, escalation, maintenance, invoices
src/payments.py     late fee, interest, payment waterfall, DEFAULT
src/events.py       notice, break, renewal, inspection, settle
src/settlement.py   move-out settlement and precedence (BR-43)
src/engine.py       command runner and output rows
src/outputs.py      writes the four CSV files
src/printer.py      readable settlement statement for the log
tests/              pytest suite
data/               sample input pack
docs/               design document (PDF)
decision_log.md
```

## Status

| Week | Status |
|---|---|
| 1. Design document | Done (see docs/) |
| 2. Core flows | Done |
| 3. Full rules and edge cases | Done, all rules and planted edge cases tested |
| 4. Final documentation and demo | In progress |
