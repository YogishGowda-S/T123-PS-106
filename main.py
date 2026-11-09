"""Entry point for the PS-106 rental settlement engine.

Usage: python main.py <input_dir> [output_dir]

<input_dir> holds leases.csv, maintenance_actuals.csv, damage_rate_card.csv and
commands.txt. The engine writes invoices.csv, ledger.csv, settlements.csv and
lease_state.csv to <output_dir> (default: ./output).
"""
import csv
import os
import sys

from src.engine import Engine
from src.outputs import write_all


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_commands(path):
    """(line_no, text) for each command line; comments and blank lines are skipped."""
    commands = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if text and not text.startswith("#"):
                commands.append((line_no, text))
    return commands


def run(input_dir, output_dir):
    engine = Engine()
    engine.load_damage_card(read_rows(os.path.join(input_dir, "damage_rate_card.csv")))
    engine.load_leases(read_rows(os.path.join(input_dir, "leases.csv")),
                       read_rows(os.path.join(input_dir, "maintenance_actuals.csv")))
    engine.run(read_commands(os.path.join(input_dir, "commands.txt")))
    write_all(engine, output_dir)
    return engine


def main(argv):
    if not 1 <= len(argv) <= 2:
        print("PS-106 Rental Settlement Engine")
        print("Usage: python main.py <input_dir> [output_dir]")
        return 1
    output_dir = argv[1] if len(argv) == 2 else "output"
    engine = run(argv[0], output_dir)
    print("\n".join(engine.log))
    print(f"\nWrote invoices.csv, ledger.csv, settlements.csv, lease_state.csv to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
