# Implementation batch 2.2.1 — 25 October 2026

Parent: uploaded Slice 2.2, SHA256
`2c4a14e669b8efc4edb96ba3575979ad93cff66bc781b16f01d9d11af561ad7e`.
Author of this batch: ChatGPT/Codex. Claude has not independently reviewed this implementation.

- R22-01: approval enforces canonical cutoff+1 timestamps; noncanonical t0 raises before delivery.
  Commit compares cutoff and preauth-inclusive context, rebuilds observation from the valid prefix,
  reruns the complete checker, and compares the exact event/effect plan. Invalid/refused grants do
  not get indexed while planning. Idle logical cutoffs use cutoff rather than the last event time.
- R22-02: enumerate every raw-fragment subset, including metadata, partial and supersets; refuse
  excessive domains before allocation. Metadata operations remain legal. A common plan evaluator
  validates the full immutable demand, canonical scope/index representation, K, authority at each
  evolved prefix, transitions, service and cost. Oracle and replay use that evaluator.
- R22-03: the separate reference independently enforces per-step scope/grant authority, validity and
  K, includes all subsets, and returns service counts and replayable traces. It shares exposure
  and transition primitives as disclosed, not production checker/generator/plan/cost functions.
- Partial-completion miss charging moved from duplicated callers into action_cost. Plan totals are
  unchanged; no objective coefficient was adjusted. Negative/nonfinite costs are rejected because
  exhaustive-search pruning assumes nonnegative costs.
- The rolling comparison receives only the remaining forecast suffix. Complete action traces,
  reference trace replay and service counts accompany comparison costs. EARP remains retired.
- Old contradictory active docs have been consolidated; historical releases are frozen.

## Observed correction of an expectation

The old review established a feasible cost-25 trace, not an optimum. Complete search finds cost 24
(served 1, unserved 2); its cost-25 trace remains valid (served 2, unserved 1). The first draft of the
new test incorrectly expected the feasible witness to be optimal. That expectation was corrected
without changing constraints, objective or the preserved witness. Both oracle and separate
reference return 24 and their traces replay. This objective/service distinction is an open
modeling question for the timed batch, not a manufactured controller improvement.

See the batch evidence for the original three failures and the repaired contract regressions.
