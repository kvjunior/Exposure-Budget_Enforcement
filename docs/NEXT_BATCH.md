# Next batch P3C — bounded timed oracle and separate replay reference

P3B implements a causal abstract service, not a timed cryptographic service. The author is
ChatGPT/Codex; Claude review remains pending. Existing crypto witnesses are preserved separately.

Before optimizing, write the exact finite domain: single-grant/single-scope demands; positive
integer action durations; horizon and pending censoring; whether optimizing served count, failures,
waiting or a lexicographic tuple; complete legal Defer times; and what the offline oracle knows.
Do not retrofit a cost penalty to manufacture a controller win. Retain cases where simple methods
are optimal. No new controller follows automatically from this batch.

| Next file | Purpose |
|---|---|
| docs/timed_oracle_contract.md | Freeze domain, horizon objective, action completeness, information boundary and invalid-environment assumptions |
| delegation_manager/timed_candidates.py | Enumerate metadata, partial/full raw deliveries, transforms/retries, prospective activation, revocation, reject and legal defer points; precheck search bounds |
| delegation_manager/timed_oracle.py | Exact bounded search using only the frozen timed contract, returning replayable actions and full service/exposure outcomes |
| tests/reference/timed_service_reference.py | Separate state transitions and accounting; no import of the production simulator/checker/candidate generator for its decisions |
| tests/differential/timed_oracle_test.py | Exhaustive small-domain agreement, witness replay, partial/metadata/defer cases and explicit negative/zero-advantage results |
| python/experiments/timed_oracle_pilot.py | Labelled finite comparisons, no measured PRE throughput or publication-scale performance |

The delayed-production counterexample is now executable. P3C must state whether it treats
infeasibility as an evaluated outcome or adds justified production completeness/fencing. It must
not use unobserved actual records inside the online gate. A hard cumulative budget cannot be
claimed from an observable endpoint test alone. Keep endpoint, disclosure-ledger and active-scope
coordinates separate, and preserve prior disclosures even when later authorization reduces the
endpoint measure. A closed horizon cannot simply make requests after it disappear from denominators.

After semantic/reference validation, integrate a real isolated PRE backend with timed receipts,
provisioned tokens/material, original ciphertext binding and failure paths. That is a separate
implementation step; existing HPKE/Umbral smoke tests do not substitute for it. Real workload,
controller, theory/novelty gate and journal experiments remain later work.
