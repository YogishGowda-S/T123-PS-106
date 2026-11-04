# Decision Log (Team T123, PS-106)

1. Language: Python 3.10+ (easier to explain and change live in the viva).
2. All money uses `Decimal`, never `float`, so outputs match exactly.
3. Rounding: half-up to whole rupees on each computed charge (BR-44, A-08).
4. Days in month always come from the real calendar; a partial month is billed by actual days (BR-06).
5. The date exactly 3 months after start counts as inside the "first 3 months" for lock-in (A-01).
6. Late interest is overdue rent x 2% x days / 30, counted from the 11th (A-02).
7. Deposit interest uses actual tenancy days / 365 on the excess over 3 months' rent (A-03).
8. DEFAULT's 60 days are counted from the invoice due date and checked after every command (A-04).
9. Maintenance cap is 10% of full-month rent, then pro-rated for partial months (A-05).
10. The deposit-plus-one-month cap applies to inspection deductions only (A-07).
11. If a lease starts after the 5th, the first invoice is due on the start date and grace is 5 days.
12. Interest accrues on unpaid rent plus maintenance (the invoice total), not on interest or fees.
13. Payments clear interest on all invoices first, then late fees, then rent oldest-first (BR-14).
14. A DEFAULT termination notice is a 60-day landlord notice but does not waive lock-in forfeiture.
15. A BREAK command means the tenant vacates that same day, so the full notice period is short.
16. A renewal offer must be made at least 45 days before expiry; later offers are rejected.
17. Escalation counts 12-month anniversaries from the start of each rent period (original or renewal).
18. Overpayments are held as credit and refunded in the settlement statement.
19. Unpaid rent and interest are accrued to the vacation date for settlement.
20. Late-refund interest is net refund x 1% x late days / 30 (A-13), only on a positive refund.
