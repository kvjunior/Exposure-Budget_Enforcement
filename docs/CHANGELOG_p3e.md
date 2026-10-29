# P3E changelog — enforcement integration, evaluation, multi-demand oracle, finalized theory

- Task 1: admission-side enforcement boundary (_enforce) wired into ALL capability-changing commits
  (grant-metadata, raw-delivery, cfrag-delivery); atomic, fail-safe; closes the retroactive-disclosure
  hole on ACTUAL state while the public gate preserves the observability distinction. Tests:
  p3e_enforcement_test (8 cases). CE-RETRO updated: the hole is now PREVENTED by execution.
- Task 2: p3e_workload_eval.py (30 seeds x 3 configs, 6 policies) + p3e_make_figures.py; JSON+CSV+PNG.
  Findings: cost of safety (greedy_full serves less, 0 violations); production-only fencing violates
  like unfenced (insufficient without admission enforcement).
- Task 3: multi-demand oracle verified (2-demand, replay) + counterexample to universal greedy
  optimality (MD-GREEDY-CE). No general optimality claimed.
- Task 4: docs/proofs_p3e.md (authoritative): Thm 1/Cor 1/Thm 2/Thm 3/Prop 4, scoped + labelled.
- Task 5: docs/novelty_p3e.md; SDAC-BBPP read (abstract+kw) -> does not subsume us.
- Task 6: `make reproduce` runs the full pipeline; obsolete P3B spine retired
  (OBSOLETE_dichotomy_spine_p3b.md). Full regression: 23 PROD suites + 2 Umbral suites + HPKE smoke.
- Task 7: docs/GO_NOGO_P3E.md (CONDITIONAL GO to write; NO-GO to submit until B1-B3),
  docs/MANUSCRIPT_EVIDENCE_P3E.md.
