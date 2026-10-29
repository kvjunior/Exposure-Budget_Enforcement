# Research-readiness report (P3D)

## Status classification (per the brief)

PROVEN (model-level, conditional on closure soundness PO1):
- Corrected Theorem 1: impossibility for PRODUCTION-BLIND public-log controllers in the
  already-reconstructible + tight-budget + delayed-report regime.
- Sufficiency of each of M1 (fencing), M2 (admission refusal), M3 (budget absorption).
- Corrected Theorem 2: feasibility under the ONGOING fencing invariant (P-fence + A-fence).

MODEL-CHECKED (executable on the real simulator, this session):
- CE-RETRO (retroactive collateral disclosure via scope-key-opens-everything + observability gap),
  CE-NEC and CE-REFUSE (fencing not necessary) -> the old Theorem 2 and the old "iff" are refuted.
- The concrete fence prevents the breach (actual disclosed weight 0), REJECTS production when the
  owner is offline, no-ops when safe; the admission-side retroactive check is correct.
- The timed oracle optima replay feasibly and match the single-demand independent reference.

TESTED (regression, this session): 21 PROD non-crypto suites pass; both Umbral crypto suites pass in
the legacy venv; all 7 experiments pass including the real HPKE smoke. No regressions.

ASSUMED (not proven): closure soundness (retained shares => scope key => plaintext); independent
fresh-scope keys; the abstract cfrag-usability backend stands in for real timed PRE; the approval
receipt is process-local, not cryptographically verified.

EXPERIMENTALLY OBSERVED (not a theorem): greedy == exact timed optimum on three tiny single-demand
instances; fenced vs unfenced behaviour on the documented parameter sweep.

STILL OPEN (required before an IEEE TNSM submission):
1. A GENERAL multi-demand optimum / regime characterization (the independent reference is
   single-demand; greedy optimality is not proven in general).
2. A MEASURED arrival/reservation workload at scale (the current fence realizes safe traces by
   planning; a full stochastic arrival/queue/outage generator with many seeds is not implemented).
3. REAL timed PRE backend + cryptographically verified receipts (backend is abstract).
4. SUBMISSION-GRADE proofs of the corrected theorems (currently model-level arguments).
5. NOVELTY: evidence only. The TNSM sweep (2022-2026) and TOPS 2022 / SACMAT 2025 full-text reads
   found no matching prior work, but SDAC-BBPP (TNSM 2024) is unread in full and the adjacent
   online-admission / privacy-budget literature is unsearched. The gate is NOT closed.
6. A full systematic TNSM table-of-contents sweep (search-engine coverage is not the issue list).

## Consequence for the paper
The scientific content is now HONEST and NARROWER than the earlier universal claim, as the brief
preferred. The defensible contribution is a CHARACTERIZATION: online exposure-budget enforcement is
impossible for production-blind controllers in a precise regime, and is recoverable by an ONGOING
fencing invariant co-designed across the admission gate and a concrete production fence -- one of
several sufficient mechanisms, not a necessary one, and requiring an admission-side rule to close the
retroactive-disclosure hole. This is model-level and conditional on closure soundness; no
cryptographic security or performance superiority is claimed.

## NOT camera-ready
Items 1-6 above are genuine scientific/experimental obligations that are not yet satisfied. This is a
verified milestone with corrected theory, a concrete fence, and first evaluation numbers -- not a
finished paper.

## What remains for P3E and submission
- P3E: a stochastic arrival/queue/outage workload generator with multiple seeds and variance
  reporting; a multi-demand oracle + a genuinely general independent reference (or a proof of greedy
  optimality within a stated regime); the admission-side ongoing-invariant enforcement wired into the
  manager (not only exposed as a check); and a real (or clearly-bounded) PRE backend.
- Submission: submission-grade proofs; the full-text SDAC-BBPP read and the adjacent-literature
  search; a complete TNSM ToC sweep; and only then an evaluation section written from measured runs.
