"""End-to-end tests on the 10 SECONDS sample pack in data/."""
import csv
import tempfile
from pathlib import Path

from main import read_commands, run
from src.outputs import FILES
from src.parser import parse_timestamp, truthy
from tests.helpers import D

DATA = Path(__file__).resolve().parent.parent / "data"
_cache = {}


def result():
    """Run the sample pack once and return (engine, {file name: rows})."""
    if not _cache:
        with tempfile.TemporaryDirectory() as out:
            engine = run(str(DATA), out)
            _cache["engine"] = engine
            _cache["files"] = {name: list(csv.DictReader(open(Path(out) / name)))
                               for name in FILES}
            _cache["headers"] = {name: open(Path(out) / name).readline().strip()
                                 for name in FILES}
    return _cache["engine"], _cache["files"]


def ledger_line(n):
    return next(r for r in result()[1]["ledger.csv"] if r["line_no"] == str(n))


def settlement(lease_id):
    return next(r for r in result()[1]["settlements.csv"] if r["lease_id"] == lease_id)


def invoice(lease_id, month):
    return next(r for r in result()[1]["invoices.csv"]
                if r["lease_id"] == lease_id and r["month"] == month)


def state(lease_id):
    return next(r for r in result()[1]["lease_state.csv"] if r["lease_id"] == lease_id)


def test_output_files_have_the_expected_columns():
    result()
    for name, columns in FILES.items():
        assert _cache["headers"][name] == ",".join(columns)


def test_one_ledger_row_per_payment_line_in_file_order():
    payment_lines = [n for n, text in read_commands(DATA / "commands.txt")
                     if text.startswith("PAYMENT")]
    assert [int(r["line_no"]) for r in result()[1]["ledger.csv"]] == payment_lines


def test_one_settlement_row_per_settle_command():
    settles = [n for n, text in read_commands(DATA / "commands.txt") if text.startswith("SETTLE")]
    assert len(result()[1]["settlements.csv"]) == len(settles)


def test_one_state_row_per_statement():
    statements = [t for _, t in read_commands(DATA / "commands.txt") if t.startswith("STATEMENT")]
    assert len(result()[1]["lease_state.csv"]) == len(statements)


def test_lease_starting_on_the_31st_prorated_one_day():  # EC-01
    assert invoice("LSE-001", "2025-03")["rent"] == "774.19"
    assert invoice("LSE-001", "2025-04")["rent"] == "24000.00"
    assert ledger_line(16)["applied_rent"] == "774.19"


def test_payment_on_the_10th_has_no_late_fee():  # EC-02
    row = ledger_line(25)
    assert row["applied_late_fee"] == "0.00" and row["applied_interest"] == "0.00"
    assert row["applied_rent"] == "20000.00"


def test_partial_payment_covering_interest_and_late_fee_only():  # EC-08
    row = ledger_line(37)
    assert (row["applied_interest"], row["applied_late_fee"], row["applied_rent"]) == \
        ("200.00", "500.00", "0.00")


def test_break_at_exactly_3_months_forfeits_two_months():  # EC-03
    assert settlement("LSE-003")["lock_in_forfeiture"] == "60000.00"     # 2 x 30000


def test_notice_29_days_before_vacating_charges_one_day():  # EC-04
    row = settlement("LSE-004")
    assert row["notice_shortfall"] == "806.45"                           # 25000 / 31
    assert D(row["late_refund_interest"]) > 0                            # BR-38


def test_deposit_exactly_3_months_earns_no_interest():  # EC-05
    assert settlement("LSE-002")["deposit_interest"] == "0.00"


def test_renewal_at_exactly_10_percent_accepted():  # EC-07
    assert invoice("LSE-006", "2026-01")["rent"] == "30800.00"


def test_landlord_notice_waives_lock_in_forfeiture():  # BR-25, planted trap
    assert settlement("LSE-009")["lock_in_forfeiture"] == "0.00"


def test_short_landlord_notice_is_rejected_then_60_days_accepted():  # BR-24
    log = "\n".join(result()[0].log)
    assert "REJECTED line 17" in log and "got 45" in log
    assert "line 19" in log and "landlord notice accepted" in log


def test_duplicate_and_unknown_lease_payments_are_rejected():
    assert ledger_line(22)["status"] == "REJECTED_DUPLICATE"
    assert ledger_line(30)["status"] == "REJECTED_UNKNOWN_LEASE"
    assert ledger_line(30)["applied_rent"] == "0.00"


def test_default_blocks_renewal_in_the_sample():  # BR-16, BR-17
    assert "REJECTED line 172" in "\n".join(result()[0].log)
    assert state("LSE-007")["default_flag"] == "true"


def test_renewal_above_10_percent_needs_the_negotiated_flag():  # BR-41
    log = "\n".join(result()[0].log)
    assert "REJECTED line 104" in log
    assert invoice("LSE-008", "2026-02")["rent"] == "45000.00"


def test_maintenance_capped_unless_uncapped():  # BR-28
    assert invoice("LSE-004", "2025-11")["maintenance"] == "2500.00"     # actual 3000
    assert D(invoice("LSE-008", "2025-12")["maintenance"]) > D("4000")   # UNCAPPED lease


def test_every_statement_has_a_valid_state():
    assert {r["state"] for r in result()[1]["lease_state.csv"]} <= \
        {"ACTIVE", "EXPIRED", "NOTICE_GIVEN", "TERMINATED", "SETTLED", "DRAFT"}


def test_parse_timestamp_keeps_only_the_date():
    assert str(parse_timestamp("2025-04-10 11:00:00")) == "2025-04-10"
    assert truthy("true") and not truthy("false")


def test_bad_commands_do_not_crash_the_engine():
    from src.engine import Engine
    engine = Engine()
    engine.run([(1, "PAYMENT|not-a-time|LSE-1|10"), (2, "NOTICE|2026-01-01 10:00:00|NOPE|TENANT|2026-02-01"),
                (3, "WHATEVER|2026-01-01 10:00:00|X")])
    text = "\n".join(engine.log)
    assert "no valid timestamp" in text and text.count("unknown lease") == 2
