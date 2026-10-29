# 0004 Disclosure ledger semantics

Decision: keep the endpoint exposure measure X_t(C) (closure.py) as a DIAGNOSTIC of current
collateral, and add a SEPARATE irreversible first-unauthorized-disclosure ledger
(delegation_model/disclosure_ledger.py) for cumulative leakage claims.

Rationale: X_t is an endpoint quantity — a later authorizing grant can reduce it, which is wrong
for "what has leaked by now". The ledger records, per (coalition, record), the FIRST time the
record was both openable by the coalition's conservative closure AND not authorized to it; later
authorization never erases that entry. Legitimate delayed reading is preserved: a record that
becomes openable only when it is already authorized (e.g., the coalition holds a live covering
grant) is never recorded. An independent step-scan reference cross-checks the ledger
(tests/differential/p2_model_test.py: ledger_ref_agree).

Consequence for claims: cumulative-leakage statements cite the ledger; momentary-collateral
statements cite X_t. They are not interchangeable.
