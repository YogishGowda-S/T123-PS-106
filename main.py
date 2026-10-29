"""Entry point for the rental settlement engine.

Week 2 will add command-file processing. For now this prints usage.
"""
import sys


def main(argv):
    print("PS-106 Rental Settlement Engine")
    print("Usage: python main.py <leases.csv> <payments.csv> <events.csv>")
    print("(command-file processing will be added in Week 2)")


if __name__ == "__main__":
    main(sys.argv[1:])
