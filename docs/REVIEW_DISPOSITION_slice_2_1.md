> Historical release disposition, superseded by CHANGELOG_slice_2_2_1.md and decision_index_contract.md.

# Slice 2.1 disposition of the independent review (S2-01..S2-07 + observations)

All seven counterexamples were reproduced against the frozen slice-2 archive
(sha256 8fc60cb6...; input hash matched what we shipped) BEFORE any change, with the three
positive controls passing. Classification per the request: CODE DEFECT (a program bug),
PROOF-SCOPE ERROR (the theorem was over-extended), or SEMANTIC REVISION (a deliberate change of
the model's contract, documented).

| ID | Classification | Disposition in slice 2.1 |
|---|---|---|
| S2-01 domination does not bound collateral | PROOF-SCOPE ERROR | Corrected. The A2 "recipient-set domination" implication is false (exemptions grow with recipients). New coverage contract: fix the recipient set EXACTLY, over-approximate ONLY proxy reach, per FAMILY_BOUND_REPAIR. The checker now expands a family to its exact-recipient-subset cases before taking maxima. Fixed-recipient proxy-monotonicity lemma written. |
| S2-02 effect equality does not bind execution | CODE DEFECT | Fixed. The executor now requires a signed-in-process ApprovalReceipt binding the full action (incl. recipient), authority, cutoff, state version, budget/family/weights config hash, and planned events/effects; it rechecks at commit. A substituted recipient is rejected. |
| S2-03 oracle omits preauthorized offline admit | CODE DEFECT | Fixed. enumerate_actions now offers a token-authorized offline ADMIT; the oracle searches the full checker-permitted action set. |
| S2-04 rolling horizon uses unchanged state | CODE DEFECT | Fixed. Rolling horizon now forks the state, executes each candidate, and advances the fork through forecast actions. The supplied 14-vs-20 regression is retained and now passes (14). Forecast information is labeled. |
| S2-05 action precedes request arrival | SEMANTIC REVISION | Corrected + scoped. Separated event-order/state-version from SERVICE TIME. The decision cutoff now respects Request.t; exogenous events are processed up to arrival; DEFER preserves pending demand (re-queued). Where we keep a decision-index model we say so and withdraw the arrival claim for that path. |
| S2-06 replay accepts incomplete schedule | CODE DEFECT | Fixed. replay_schedule now validates schedule length == number of requests, action-to-demand binding (an ADMIT serves the offered request), causal timing, and accounts for every unserved request. An independent small feasible-set reference checks tiny optima. |
| S2-07 production breaks the run invariant | PROOF-SCOPE ERROR + SEMANTIC REVISION | Corrected. PO2 is explicitly an ADMIT-only single-step lemma; it does NOT extend across unmediated production. We now define THREE separate quantities (endpoint collateral, irreversible cumulative disclosure, future-scope risk), state which transitions each budget controls, and state the limitation that an unpausable production stream can make a finite past budget infeasible without timely rotation. |
| Obs: GrantToken validity | SEMANTIC REVISION | Split issuance-window from delegated-access-window; both are checked explicitly. |
| Obs: strengthened comparison changes demand | CODE DEFECT | Fixed. Both branches now serve the SAME requested records; delivery is charged in both; the exposure difference is reported honestly (names differ, magnitude equal under equal served demand) and the misleading "different exposure" claim is withdrawn. |
| Obs: threshold nontriviality overstated | PROOF-SCOPE ERROR | Narrowed. Reframed as a property of the CAPABILITY MODEL (exposure depends on threshold/reach/recipient), NOT evidence of scheduling nontriviality. A fixed-family compact-state question is left open. |
| Obs: SACMAT adaptation unfaithful | SEMANTIC REVISION | The adaptation is RENAMED to "risk_rotation_heuristic" (our own heuristic) and all conclusions about the published SACMAT method are withdrawn. A faithful mapping is left as future work. |
| Obs: immediate rotation starves | CODE DEFECT | Fixed. Immediate rotation now rolls THEN admits in one costed plan; it no longer starves. |
| Obs: ledger reference not independent | SEMANTIC REVISION | Renamed to a cross-check; a genuinely independent small temporal-knowledge reference is added. |
| S2-08/Sec 8 EARP is provably greedy | ACCEPTED (negative result) | EARP RETIRED as a proposed algorithm. The proof (ROLL costs M+R>M so its tie-break is unreachable; EARP==greedy) is preserved in docs/controller_findings.md. No controller is proposed in 2.1. |
| Obs: hash manifest self-hash + coverage | PACKAGING | Fixed. The manifest is excluded from its own digest; coverage is defined to include all regular files. |

Nothing in slice 2 is deleted; the frozen slice-2 archive is preserved under frozen_slice_2/.
