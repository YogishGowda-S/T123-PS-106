# Decision Log (Team T123, PS-106)

1. Language: Python 3.10+ (easier to explain and change live in the viva).
2. All money uses `Decimal`, never `float`, so outputs match exactly.
3. Money is rounded half-up to 2 decimals (the sample pack shows 774.19 for a 1/31 first month), BR-44.
4. Days in a month always come from the real calendar; partial months are billed by actual days (BR-06).
5. "First 3 months" and the lock-in period include their end date (A-01, A-21).
6. Late interest is overdue rent x 2% x days / 30, counted from the 11th, on rent only (A-02, A-11).
7. Deposit interest uses actual tenancy days / 365 on the excess over 3 months' rent (A-03).
8. DEFAULT: unpaid 60 days from the invoice due date, checked after every command; the flag and a termination notice are recorded but the lease keeps running (A-04, A-10).
9. Maintenance comes from maintenance_actuals.csv, capped at 10% of full-month rent unless UNCAPPED, then pro-rated; it is shown on the invoice but is not part of the payment waterfall (A-05).
10. The deposit-plus-one-month cap applies to inspection deductions only (A-07); the switch CAP_APPLIES_TO_ALL_DEDUCTIONS in settlement.py changes it to all deductions.
11. If a lease starts after the 5th, its first invoice is due on the start date and grace is 5 days.
12. A payment clears interest on all invoices first, then late fees, then rent oldest-first, including invoices not yet due (BR-14).
13. Commands run strictly in file order; the clock used for DEFAULT never moves backwards.
14. An identical PAYMENT line (same time, lease and amount) is applied only once; later copies are REJECTED_DUPLICATE.
15. A BREAK after a tenant NOTICE keeps the notice date, so notice shortfall is measured from the notice (A-14).
16. RENEW is an acceptance: no timing check; new rent applies from the month after the old term's last month; lock-in resets to the given value (A-19).
17. If the vacation date is after the term end, billing continues up to the vacation date.
18. Painting is charged on carpet_sqft from leases.csv; damage items come from the rate card by code.
19. Payments beyond all rent due stay "unapplied" and are refunded in the settlement.
20. lease_state: state is ACTIVE, EXPIRED, NOTICE_GIVEN, TERMINATED or SETTLED; dues_outstanding is rent, interest and late fees on invoices due by the statement date (0 once settled, unless the tenant owes).
