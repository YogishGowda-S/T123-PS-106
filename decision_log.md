# Decision Log (Team T123, PS-106)

1. Language: Python 3.10+ (easier to explain and change live in the viva).
2. All money uses `Decimal`, never `float`, so outputs match exactly.
3. Rounding: half-up to whole rupees on each computed charge (BR-44, A-08).
4. Days in month always come from the real calendar (BR-06).
5. Lock-in break window counts the date exactly 3 months after start as inside (A-01).
6. Late interest is overdue rent x 2% x days / 30 (A-02).
7. Deposit interest uses actual tenancy days / 365 (A-03).
8. DEFAULT 60 days are counted from the invoice due date, the 5th (A-04).
9. Maintenance cap is 10% of full-month rent, then pro-rated (A-05).
10. The deposit plus one month cap applies to inspection deductions only (A-07).
