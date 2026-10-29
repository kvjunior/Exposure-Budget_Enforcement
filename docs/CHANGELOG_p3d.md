# P3D changelog — formal corrections, concrete fencing, integrated verification

Built on verified P3C. Corrects the theoretical spine (the audit found real errors), implements a
concrete production fence, and adds adversarial + differential tests. All additions independently
reran this session.

## Theory corrected (Task 1) — errors found and fixed, not defended
- Theorem 1 was OVERSTATED as universal impossibility. CORRECTED to a RESTRICTED class
  (production-blind controllers, already-reconstructible scope, tight budget, delayed reports).
- The "iff" was FALSE. CORRECTED: fencing is SUFFICIENT, NOT NECESSARY. Admission refusal (CE-REFUSE)
  and budget absorption (CE-NEC) are alternative sufficient mechanisms.
- Theorem 2 was FALSE ("fresh-scope record safe forever"). CORRECTED to an ONGOING fencing invariant
  spanning future grants, because a later grant retroactively discloses earlier records via
  scope-key-opens-everything + an observability gap (CE-RETRO).
- Impossibility is MODEL-LEVEL conditional on closure soundness (computational), NOT
  information-theoretic. Greedy optimality is OBSERVED on tiny single-demand instances only, not a
  theorem; the independent reference is single-demand, not a general multi-demand optimum.
- New authoritative document: docs/dichotomy_spine_p3d.md (supersedes the headline of
  dichotomy_spine.md). Executable counterexamples: tests/differential/p3d_counterexamples.py.

## Concrete fencing (Task 2)
- delegation_manager/production_fence.py: an enforced reservation mechanism. decide_fence checks
  ACTUAL reconstructibility of the active scope at production time and returns PRODUCE_CURRENT /
  ROTATE_THEN_PRODUCE / DEFER / REJECT; no unauthorized record is ever bound to a reconstructible
  scope. Ordering is reserve -> check -> rotate-or-deny -> bind -> produce (no TOCTOU: the fence
  performs the rotation before binding). Costs/timing (rotation ticks, deferrals, rejections) are
  recorded. The admission-side counterpart admission_would_retroactively_disclose exposes the
  CE-RETRO collateral so the manager can refuse future retroactively-disclosing grants.
- HONEST SCOPE: the fence prevents PRODUCTION-TIME disclosure; the ongoing whole-run invariant also
  requires the admission-side check on every grant. Confidentiality is ASSUMED (closure soundness);
  no byte-level crypto security is claimed (abstract backend preserved).

## Tests (Task 3)
- tests/differential/p3d_counterexamples.py: CE-RETRO, CE-NEC, CE-REFUSE (all check the ACTUAL
  ledger, not just the public one).
- tests/differential/p3d_fencing_test.py: fence prevents the breach (actual disclosed 0); offline
  REJECT; no-op when safe; admission-side retroactive check positive/negative/sub-threshold.

## Oracle integration (Task 4)
- The P3C timed oracle and its independent reference are preserved and still pass. The oracle's cost
  model already counts rotations (the fencing overhead). The independent reference is EXPLICITLY
  single-demand and is not described as a general multi-demand optimum.

## Evaluation (Task 5)
- python/experiments/p3d_fencing_pilot.py: fenced vs unfenced across a documented parameter sweep
  (report delay x owner availability), reporting actual cumulative disclosure, public-observation
  lag, budget violations, served/expired, rotation overhead, and total cost. Deterministic model
  (parameters swept, not RNG). Results: unfenced always violates the tight budget (disclosed 1.0,
  public lag 1.0); fenced stays at 0 at a rotation cost (online) or by rejecting unsafe production
  (offline) while still serving the actual demand.

## Integration (Task 6)
- `make p3d` and a real `make reproduce` (deterministic pilot chain). Full regression this session:
  21 PROD suites pass, both Umbral crypto suites pass (legacy venv), all 7 experiments pass
  (incl. real HPKE smoke). No regressions.
