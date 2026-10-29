> Historical release disposition, superseded by CHANGELOG_slice_2_2_1.md and decision_index_contract.md.

# Slice 2.2 disposition of the Slice 2.1 review (F01-F05 + consolidation)

All five findings reproduced against the frozen slice-2.1 archive
(sha256 e6125ae3...; input hash matched) BEFORE any change: 7 PASS, 5 FAIL. Classification:
CODE DEFECT, EVALUATION-CONTRACT DEFECT, or DOCUMENTED SCOPE CHANGE. The old counterexamples are
retained against the frozen input; where a test contract changed, the replacement is documented.

| ID | Classification | Disposition in slice 2.2 |
|---|---|---|
| F01 approval not bound to checked state/verdict | CODE DEFECT | Fixed. approve() now RUNS the checker (authority + exposure over the family) itself; it does not accept a caller authority_ok=True. The receipt binds the checked observable-LOG digest (full event history), version, cutoff, full action, preauth context, budget/family/weights config, and planned events/effects. execute() RECHECKS at commit against the current log; a receipt from one history does NOT commit on a different history (log digest differs), and an exposure-failing state cannot be approved. The structural substitution test is kept. |
| F02 oracle omits non-prefix usable delivery | EVALUATION-CONTRACT DEFECT | Fixed. candidate_actions enumerates ALL permitted compatible threshold delivery choices (every size-threshold subset of share indices), not just range(threshold). A bounded limit refuses explicitly if branching is too large. Token-authorized non-prefix choices are included. |
| F03 replay counts incomplete/changed demand as served | CODE DEFECT | Fixed. replay_schedule binds the COMPLETE offered grant (grant_id, recipient, scope, range, threshold, shares, proxies, owner, validity) and defines USABLE COMPLETION from the backend capability state: an ADMIT counts as served only if it installs a compatible threshold (so zero/one-fragment of a threshold-2 request is NOT served; a changed threshold is rejected). Partial/metadata-only actions remain unserved. |
| F04 methods use different plan spaces | EVALUATION-CONTRACT DEFECT | Fixed via one common bounded PLAN contract: every method (including the oracle and replay) may emit a PLAN of up to K actions per request (K=2: an optional rotation then an admit). Replay validates plans, not one-action-per-request. Every method's actual trace, service count and cost are returned and replayed. |
| F05 equal-demand instance still changes records | CODE DEFECT (test) | Fixed. Both branches now serve the SAME offered grant (G1 on scope (g,0), range [0,inf)); the roll branch rolls THEN admits the ORIGINAL grant on its old (now-closed) scope, charging both actions. g:0 authorization is preserved in both branches. Future-scope count is 0 (roll) vs 1 (admit) for R1; costs 14 vs 1. Stated as a model tradeoff, not a controller or novelty. |
| Consolidation | DOC REWRITE | The active README, claims, disposition, semantics and PO2 docs are rewritten into one consistent account. The false recipient-domination A2 and its old proof are REMOVED from the active text (kept only in frozen archives/changelog) and replaced with a self-contained conditional endpoint statement over the expanded exact-recipient cases + the fixed-recipient/proxy-monotonicity argument, closure soundness visibly assumed. Contradictory "arrival/exogenous implemented" statements removed. The 2^|R| coverage cost is stated; the linear-in-family prose withdrawn. ref_optimum no longer shares enumerate_actions (F02 blind spot removed); ref_ledger relabeled a cross-check. |

Frozen slice 2.1 preserved under frozen_slice_2_1/ with its SHA256.
Deferred (explicitly, not claimed done): a genuine timed arrival/queue/deadline/outage model;
a separate independent temporal-knowledge ledger reference; the TOPS 2022 full-text comparison and a
systematic TNSM sweep. Novelty stays PROVISIONAL; no controller is proposed.

## Consolidation reconciliation (slice 2.2)

- S2-05 time model: the AUTHORITATIVE statement is docs/slice_2_1_semantics.md -> a DECISION-INDEX
  model over a request sequence. Arrival time, queue/deadline, interleaved outage/production are
  DEFERRED, not implemented. Any earlier disposition row implying they were implemented is withdrawn;
  only immediate_rotation retried a request before, and in slice 2.2 the common plan contract gives
  every method the same up-to-2-action plan per request (no per-method demand-preservation asymmetry).
- Ledger reference: tests/differential/p2_model_test.py::ref_ledger shares production closure/
  authorization/accumulation; it is a CROSS-CHECK of the scan, NOT an independent temporal-knowledge
  reference. A genuinely separate temporal reference is DEFERRED. (The oracle/plan reference IS now
  independent of enumerate_actions; that is a separate, completed item.)
- Coverage cost: expand_family enumerates 2^|R| cases per declared entry (disclosed in coverage.py
  and docs/c11_po2_argument.md). The earlier linear-in-family complexity prose is WITHDRAWN.
- C11/PO2: the false recipient-domination A2 and its proof are REMOVED from the active
  docs/c11_po2_argument.md (kept only in frozen archives). The active doc states the coverage
  condition, the fixed-recipient/proxy-monotonicity lemma, closure soundness ASSUMED, the three
  distinct quantities, and the ADMIT-only non-extensions.
- Novelty: still PROVISIONAL AND NARROWED. TOPS 2022 full-text comparison and a systematic TNSM sweep
  remain OPEN. No controller is proposed; EARP stays retired.
