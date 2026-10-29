# Status after P3C

## Done in P3C (this build)
- Bounded EXACT timed oracle over the real ServiceSimulator (delegation_manager/timed_oracle.py).
- A genuinely independent timed replay reference (tests/differential/timed_independent_reference.py)
  that does not import the simulator or the oracle's generator.
- Tests (tests/differential/timed_oracle_test.py): all pass (0 failures).
- Gap-to-optimum evidence (python/experiments/timed_oracle_pilot.py ->
  results/manifests/p3c_timed_oracle.json): greedy attains the timed optimum inside the feasible
  regime; blind rotation and fragment-wasting are sub-optimal; no policy beats the optimum; the
  independent reference agrees on every instance.
- `make timed-oracle` target; docs/CHANGELOG_p3c.md; spine "open" section updated.

## Verified by independent rerun (2026-10-28, this environment)
- p3b base: all non-crypto suites, HPKE smoke, and Umbral suites pass (see
  docs/INDEPENDENT_VERIFICATION_2026-10-28.md).
- P3C additions: timed_oracle_test (0 failures), timed_oracle_pilot (0 violations), and no
  regression in timed_inputs/timed_service/p2_model/slice21/slice221/foundation suites.

## Still NOT a camera-ready paper
The spine now has its first real evaluation numbers, but the gaps to a submission remain:
- The dichotomy theorems are model-level arguments, not submission-grade proofs.
- "Fencing" is still a scripted barrier, not a measured arrival/reservation mechanism.
- Greedy's optimality is shown on tiny instances only, not characterized as a regime.
- The crypto backend is abstract, not real timed PRE; receipts are process-local.
- Novelty is evidence (TNSM sweep + TOPS/SACMAT full-text), not a closed gate; SDAC-BBPP and the
  adjacent online-admission/privacy-budget literature are still to be read.

## Honest one-line summary
P3C delivers the timed evaluation infrastructure and its first gap-to-optimum numbers, grounding the
paper's central claim in the timed model. It is a verified milestone, not a finished paper.
