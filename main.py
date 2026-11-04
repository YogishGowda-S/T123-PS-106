"""Entry point for the rental settlement engine.

Usage: python main.py <leases.csv> <payments.csv> <events.csv>
"""
import csv
import sys

from src.engine import Engine


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv):
    if len(argv) != 3:
        print("PS-106 Rental Settlement Engine")
        print("Usage: python main.py <leases.csv> <payments.csv> <events.csv>")
        return 1
    engine = Engine()
    engine.run(read_rows(argv[0]), read_rows(argv[1]), read_rows(argv[2]))
    print("\n".join(engine.out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
