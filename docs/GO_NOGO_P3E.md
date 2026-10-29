# IEEE TNSM GO / NO-GO assessment (end of P3E)

Assessed on technical correctness, defensible novelty, adequacy of proofs, validity of experiments,
and reproducibility -- NOT merely passing unit tests.

## Verdict: CONDITIONAL GO for WRITING; NO-GO for immediate SUBMISSION.

Write the paper now around the verified characterization; do NOT submit until the specific
blockers below are cleared. Rationale per criterion:

### 1. Technical correctness -- STRONG
The P3D theory errors were found and corrected; the admission-side safety rule now GOVERNS
EXECUTION (enforcement boundary at every capability-changing commit, atomic, fail-safe), closing the
retroactive-disclosure hole while preserving the public/enforcement distinction. 23 PROD suites +
both real-crypto (Umbral) suites + HPKE smoke pass; full pipeline reproduces. GO.

### 2. Defensible novelty -- ADEQUATE but not fully closed
The focused check (SDAC-BBPP abstract+kw, TOPS/SACMAT/FairShare full text, adjacent areas) found no
prior work posing the online exposure-budget-enforcement-with-intermittent-owners problem or the
management/data-plane co-design characterization. The contribution is narrow and defensible. BLOCKER
(minor): SDAC-BBPP full text (paywalled) and a full systematic TNSM ToC sweep are still owed; do them
before submission to be safe. Conditional GO.

### 3. Proofs -- ADEQUATE at model level; NOT machine-checked
docs/proofs_p3e.md gives submission-quality statements and proofs (Thm 1 restricted impossibility,
Cor 1 sufficiency/non-necessity, Thm 2 ongoing-invariant feasibility, Thm 3 enforcement realizes
A-fence), all conditional on closure soundness (A1) and clearly labelled. They are model-level
arguments with executable witnesses, NOT machine-checked or cryptographic reductions. Adequate for a
systems/management paper that states this scope honestly. GO with explicit scoping.

### 4. Experiments -- VALID and reproducible; one documented simplification
30 seeds x 3 configs; six policies under comparable assumptions; actual disclosure, violations,
service, cost, overhead, owner-availability effects; CSV + JSON + four figures; deterministic.
Findings include unfavorable ones (cost of safety; production-only fencing insufficient). BLOCKER
(minor, documented): demands are released at t=0 (no staggered inter-arrival process) because the
action-driven clock makes precise inter-arrival advancement out of scope here; arrival realism is via
deadlines/report-delays/availability. State this as a limitation; a staggered-arrival generator is a
clean follow-up, not required for the core claims. Conditional GO.

### 5. Reproducibility -- STRONG
`make reproduce` runs the full pipeline from a clean extraction; SHA-256 manifest; pinned
requirements; two isolated crypto venvs; execution logs. GO.

## BLOCKERS to clear before SUBMISSION (precise)
B1. SDAC-BBPP full text + a systematic TNSM 2022-2026 ToC sweep (novelty safety).
B2. State the t=0-release simplification as an explicit limitation (or add a staggered-arrival
    generator) (experimental honesty).
B3. Scope every theorem as model-level, conditional on closure soundness; do not imply cryptographic
    security or a real PRE deployment (the backend is abstract) (claims honesty).
B4. (Recommended) one real-library crypto micro-benchmark, clearly labelled, to connect model
    "fragment/tick" costs to real HPKE/PRE operation costs -- OR state explicitly that costs are
    model units only.

## What is NOT a blocker (deliberately out of scope, state as limitations)
- A general multi-demand optimality theorem (we give a counterexample to universality; gap reported
  only where the exact oracle is established).
- A real timed PRE backend (abstract backend is sufficient for the characterization if scoped).
- Machine-checked proofs (model-level proofs with executable witnesses are adequate if scoped).

## Bottom line
The science is now honest, corrected, and narrower than earlier universal claims -- which is exactly
the defensible position. You can START WRITING the IEEE TNSM manuscript from the P3E evidence package.
Clear B1-B3 (and ideally B4) before submitting. This is the FINAL planned code milestone; remaining
items are writing + two targeted literature/benchmark tasks, not another development batch.
