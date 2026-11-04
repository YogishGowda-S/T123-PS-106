from pathlib import Path

from main import read_rows
from src.engine import Engine
from src.parser import first, parse_params, truthy

DATA = Path(__file__).resolve().parent.parent / "data"


def run_sample():
    engine = Engine()
    engine.run(read_rows(DATA / "sample_leases.csv"),
               read_rows(DATA / "sample_payments.csv"),
               read_rows(DATA / "sample_events.csv"))
    return "\n".join(engine.out)


def test_sample_run_prints_settlement_statement():
    output = run_sample()
    assert "MOVE-OUT SETTLEMENT L101" in output
    assert "NET REFUND TO TENANT: Rs 41,499" in output


def test_invalid_lease_is_rejected_with_a_clear_message():  # BR-02
    assert "REJECTED lease L104: Deposit must be between 2 and 10 months' rent" in run_sample()


def test_short_landlord_notice_rejected_in_a_command_file():  # BR-24
    assert "REJECTED [2026-03-01] NOTICE L103: landlord notice must be at least 60 days" in run_sample()


def test_default_raises_flag_and_notice_in_a_command_file():  # BR-16, BR-18
    assert "DEFAULT L102: DEFAULT flag raised; termination notice issued" in run_sample()


def test_unknown_lease_and_bad_rows_do_not_crash():
    engine = Engine()
    engine.run([], [{"date": "2026-01-05", "lease_id": "NOPE", "amount": "100"},
                    {"date": "not-a-date", "lease_id": "NOPE", "amount": "1"}],
               [{"date": "2026-01-06", "type": "NOTICE", "lease_id": "NOPE", "params": ""}])
    text = "\n".join(engine.out)
    assert "unknown lease" in text and "REJECTED payment row 2" in text


def test_parse_params_supports_repeated_keys():
    params = parse_params("area=800;damage=Door:500;damage=Tap:300")
    assert first(params, "area") == "800"
    assert params["damage"] == ["Door:500", "Tap:300"]
    assert truthy("y") and not truthy("")
