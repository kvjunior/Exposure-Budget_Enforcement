# Independent current-turn execution ledger, 2026-10-28

- Ran `tests/differential/p3f_full_horizon_test.py`: **3 tests PASS**; original heavy seeds 0/1/4, all 3 regimes/2 budgets and baseline differentiation.
- Ran `tests/differential/timed_service_test.py`: **44 tests PASS**.
- Ran and observed PASS output from differential modules: authority_rollover, checked_action,
  exposure_check, foundation_verification, online_witness, p2_baselines_oracle, p2_model,
  p3d_counterexamples, p3d_fencing, p3e_enforcement, p3e_multidemand_oracle,
  rust_python_closure, slice21_regression, slice221_contract, sufficient_state,
  surviving_strengthened, temporal_authorization, timed_inputs, timed_oracle.
  The main combined `make check` crypto-dependent flow was not verified in this environment.
- Ran `p3e_workload_eval.py` to completion, twice; output JSON SHA-256 reproduced
  byte-identically: `f876b162398a37119081577aa1efe5c8781c9508cc375dd88b45654861d552fd`.
- Verified **900/900** run-level invariants on the CSV; aggregate mean values correspond exactly
  to the CSV (`scripts/verify_full_horizon_results.py` PASS).
- Regenerated figure PNGs, LaTeX result tables, and compiled the 8-page PDF with two LaTeX passes.
- Attempted real-library checks in the provided current environment:
  `python python/experiments/smoke_lifecycle.py` -> **NOT RUN: missing `hpke`**;
  `python tests/adversarial/mixed_fragments.py` -> **NOT RUN: missing `umbral`**.
  This is an environment/dependency limitation, not a passing crypto check or a code defect claim.
  The older archive documents crypto tests in separate pinned environments, but those results were
  not independently rerun here. Do not represent them as new/current passes.
- No wall-clock PRE measurements have been generated or claimed.

**Verdict:** internally reproduced full-horizon abstract simulation and revised IEEE manuscript;
external deployment/cryptographic guarantees, operational calibration, and exhaustive novelty
verification are out of scope and remain disclosed limitations.
