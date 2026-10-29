# T123-PS-106: Rental Agreement, Escalation, Deposit and Move-out Settlement Engine

Capstone project, 10 SECONDS placement training.
Team T123: Yashwanth K S (1AT24IS224), Yogish Gowda S (1AT24IS225), ISE D.

A command-file driven engine that creates leases, bills monthly rent with escalation and maintenance, handles payments and late fees, processes notice, break and renewal events, and computes the move-out settlement from the security deposit.

## Requirements

- Python 3.10 or newer
- pytest (`pip install -r requirements.txt`)

## How to run

```
python main.py <leases.csv> <payments.csv> <events.csv>
```

Command-file processing is being added in Week 2.

## How to run the tests

```
pip install -r requirements.txt
pytest
```

## Project structure

```
src/        engine code (money, models, billing, ...)
tests/      pytest tests, each tagged with the BR-ID it checks
data/       sample input files
docs/       design document (PDF)
decision_log.md
```

## Status

| Week | Status |
|---|---|
| 1. Design document | Done (see docs/) |
| 2. Core flows | In progress |
| 3. Full rules and edge cases | Not started |
| 4. Final documentation and demo | Not started |

## Business rules

Every rule is listed with an ID (BR-01 to BR-44) in the design document in `docs/`. Tests name the rule they cover.
