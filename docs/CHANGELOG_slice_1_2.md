# Separate correction branch 1.2 — 25 October 2026

Based on the unmodified uploaded slice 1.1. Changes are bounded repairs, not a new research
contribution or a security proof. Five independent counterexamples are in `tests/review_slice11.py`.

| Finding | Observed in 1.1 | Repair |
|---|---|---|
| S11-01 | Candidate-only hypothetical corruption ignores previous parties in the same public coalition; budget 1 accepts a transition from 1 to 2 exposed active scopes. | `check_action` takes nonempty, unique `CoalitionSpec` objects, uses possible knowledge over the whole observable history plus declared effects, and takes separate maxima for each budget dimension. Label-only families fail closed. |
| S11-02 | A future grant revoked before valid_from exempts known data despite never having been live. | Historical authorization requires an actual possible read time by the cutoff, after issue/valid_from/production and before revocation and no later than inclusive valid_to. Earlier records may still be read once a later grant actually becomes live. |
| S11-03 | Activation at seq 100 hides old-key future exposure for next seq 1. | This slice supports immediate activation only: `start_seq == produced_next`. Scheduled future activation is refused. The standalone fold still requires validated histories. |
| S11-04 | One global availability boolean allows P's online event to authorize O's grant while O is offline. | Per-owner connectivity map used by the checker and baseline. A stream cannot silently change owner. The compatibility display boolean is not an authorization decision input. |
| S11-05 | Negative/out-of-range share indices accepted; fallback proxy identifiers fabricated. | Validate unique integer indices in `[0, shares)` before evaluating an action. No fallback proxy identities. |

Also refuse reused grant ids in a new ADMIT, reject invalid budget/weight values, use portable
Makefile interpreter defaults, and label smoke resource assumptions honestly. Exact dependency
versions remain unchanged. Existing tests were migrated from labels to explicit coalition reach;
new controls ensure that narrow-reach feasible grants are still accepted, broad-reach ones are
vetoed, separate dimension witnesses work on the action path, and hidden/future events do not
change a decision.

Not fixed or claimed: cryptographic preauth verification, atomic commit/persistence, full input
validation, a cumulative disclosure ledger, controller usefulness, or a security theorem. These
are separate next-stage obligations, not regressions silently declared solved.
