# Submission-readiness (end of P3F)

## Status: manuscript DRAFTED and compiles; CONDITIONAL on clearing the blockers below before submission.

PROVEN (model-level, conditional on closure soundness A1): Thm 1 (restricted impossibility),
Cor 1 (sufficiency; fencing not necessary), Thm 2 (ongoing-invariant feasibility), Thm 3 retroactive.
MODEL-CHECKED / code invariant: Prop (enforcement realizes A-fence) + all adversarial tests; the
production fence (rotate/drop) and admission boundary across all commit paths.
TESTED: 23 PROD suites + 2 real-Umbral suites + real-HPKE smoke; full reproduce pipeline.
EXPERIMENTALLY OBSERVED: neither single mechanism suffices; combined mechanism holds the budget; cost
of safety; budget/outage/delay effects; greedy==optimum on tested instances with a counterexample to
universality.
ASSUMED: closure soundness; independent fresh keys; abstract cfrag backend; process-local receipts.

## Genuine remaining blockers before submission
B1. SDAC-BBPP full text + a COMPLETE systematic TNSM 2022-2026 ToC sweep (novelty safety). Currently
    SDAC-BBPP abstract-level; sweep partial.
B2. A stochastic inter-arrival/queue workload (current generator uses staggered releases, not a full
    arrival process) OR state it as a limitation (currently stated in Sec. Limitations).
B3. (Recommended) integrated real-library crypto overhead timing to connect model units to HPKE/PRE
    costs, OR keep the explicit "model units only" scoping.
B4. A second independent reviewer pass on the corrected evaluation and proofs.

## NOT blockers (stated as limitations in the manuscript)
General multi-demand optimality; a real timed PRE backend; machine-checked proofs.

## Verdict
The science is corrected and the manuscript is drafted from verified evidence. This is a defensible
IEEE TNSM submission AFTER B1 (and ideally B2-B4). It is NOT yet camera-ready.
