# Research questions (falsifiable)

RQ1 (nontriviality). Does exposure collapse to a per-scope "delegated?" flag under the conservative
threat model? Expected counterexample: a completed grant that is non-exposing because coalition
reach < threshold. STATUS: answered NO (sufficient_state_test.py). The management state is
substantive.

RQ2 (does ordinary rotation suffice?). Can a fixed-period rollover schedule match an exposure-aware
policy on cost under an exposure budget? Expected counterexample: a workload where fixed-period
either over-rolls (wasted cost) or under-rolls (budget breach) relative to greedy. STATUS: partial
evidence (p2_baselines_oracle_test.py): on the tiny instance, fixed-period costs 15 vs greedy/
rolling 4 (= offline optimum), because it rolls when admission was feasible. Needs a frozen
workload suite to generalize.

RQ3 (gap to optimum). How close are online policies to the matched-model offline optimum across
workloads? Metric: cost gap to offline_oracle.solve. An online policy can never be below 0. STATUS:
harness exists; greedy achieves 0 gap on the tiny feasible instance; systematic study is P2/P3.

RQ4 (cumulative vs endpoint leakage). Do later grants erase earlier unauthorized disclosures under
the endpoint measure, and does the ledger fix it? STATUS: answered (ledger monotone; endpoint
drops). Cumulative claims use the ledger.

RQ5 (conditional safety). Under the stated backend/authority/observation/execution/transition
assumptions, does the checked-action path never admit an action that breaches the exposure budget
over the declared family? STATUS: executable evidence (checked_action + oracle replay); a written
conditional argument is an open proof obligation (docs/proof_obligations.md).
