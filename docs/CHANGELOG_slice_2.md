# Change log: slice 2 (P2 model/baseline stage, on the corrected 1.2 base)

Base: the independently corrected branch 1.2 (adopted after reproducing before/after evidence for
findings S11-01..S11-05: all five FAIL on frozen 1.1, PASS on 1.2, with three positive controls
passing in both). The input 1.1 archive hash was confirmed:
0813510c46fb794a3725af02917aa663afe78635ad5a08239d51fdc194c27093.

## New model layer (P2)
- delegation_model/coalitions.py: canonical immutable coalition specs + family validation.
- delegation_model/effects.py: typed backend-specific capability effects (THRESHOLD_PRE raw
  kfrags; OWNER_HPKE_REWRAP per-record data key; SCOPE_KEY_HANDOVER whole scope key). Decision
  0005.
- delegation_model/disclosure_ledger.py: irreversible first-unauthorized-disclosure ledger,
  monotone, with legitimate-delayed-reading preserved, plus an independent step-scan reference.
  Decision 0004.
- delegation_model/validation.py: strict history validation (ordering, contiguous seq, immediate
  activation, owner conflicts, index ranges).
- delegation_model/transitions.py: one pure validated transition (apply_event/fold_state) shared by
  the executor and planners; covers production, expiry/revocation, partial delivery.

## New manager layer (P2)
- delegation_manager/executor.py: versioned reference executor; checked effects must equal
  delivered effects; stale/refused actions deliver nothing. Decision 0005, PO3.
- delegation_manager/candidate_actions.py: authority-feasible action enumeration (shared set).
- delegation_manager/cost_model.py: explicit operation/miss/rollover cost units (no durations).
- delegation_manager/decision_log.py: JSON decision records.
- delegation_manager/baselines/{fixed_period,greedy_history,rolling_horizon}.py: an actual
  periodic scheduler, a deterministic causal exposure-aware greedy, and a causal-forecast
  receding-horizon policy.
- delegation_manager/offline_oracle.py: bounded exact offline optimum over tiny instances, with an
  independent schedule replay.

## Evidence
- tests/differential/{p2_model_test, p2_baselines_oracle_test, sufficient_state_test}.py.
- python/experiments/baselines_vs_oracle.py -> results/manifests/baselines_vs_oracle.json
  (model simulation; greedy/rolling match the offline optimum, fixed-period does not; no online
  policy beats the optimum).

## Findings recorded
- Nontriviality (Decision 0006, RQ1): exposure does NOT collapse to a per-scope delegated flag; it
  depends on installed indices vs threshold, coalition reach, and recipient possession.
- Ordinary rotation is not automatically sufficient (RQ2): fixed-period over-rolls vs the
  exposure-aware policies on the tiny instances. Needs a frozen workload suite to generalize.

## Novelty (full-text grounded, still provisional)
- JNCA 2025 read in full: it optimizes deployment ARCHITECTURE (entity->domain, 65,536
  architectures, design-time) and handles cached keys by renew-and-redistribute with key versions
  (Sec 6.3). It is NOT online history-dependent admission/rollover under an exposure budget with
  intermittent owners. See docs/related_work_reading_log.md. TOPS 2022 and SACMAT 2025 full-text
  comparisons still owed before the gate is closed.

## Unchanged honest limits
- No controller is implemented (UNSUPPORTED). C-usefulness is empirical and pending a frozen suite.
- No service atomicity/network measurement (P3). No signed preauth verification yet. HPKE smoke and
  Umbral witnesses remain separate mechanism contracts; effects are not conflated.
- 1-vCPU container; no constrained-device claims.
