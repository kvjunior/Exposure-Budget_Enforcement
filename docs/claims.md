# Active claims ledger — Slice 2.2.1

Historical ledgers are preserved in frozen archives. This is the current authoritative status.

| Claim | Status and boundary | Evidence |
|---|---|---|
| Historical retained material survives revocation; mixed fragments can open records | Implemented model, grounded witnesses; closure soundness assumed | closure.py; retained/mixed Umbral tests |
| Exact-recipient coverage avoids recipient-domination error | Implemented endpoint guard; exponential recipient subsets | coverage.py; S2-01 regression |
| Checked action vetoes model endpoint breaches | Implemented with authentic observable-prefix/family assumptions | manager.py; historical regressions |
| Executable effects use the same canonical timestamps and context as checking | Implemented process-local contract; no deployed atomicity/signature claim | executor.py; slice221_contract_test.py |
| Unserved metadata/partial admissions remain legal and can affect later feasibility | Implemented, fully enumerated in the bounded domain | candidate_actions.py; metadata fixture |
| Oracle/replay share grammar, complete offered grant, service and cost | Implemented canonical next-epoch/sorted-subset domain, K=1/2 | plan_contract.py; offline_oracle.py |
| Separate reference validates choice-space/authority/cost | Implemented; exposure/transition primitives shared | independent_reference.py; 24-cell matrix and trace replay |
| Current objective optimum in metadata fixture is 24 serving one; 25 witness serves two | Observed bounded enumeration, not controller improvement | slice221_contracts.json |
| Immutable ledger cannot erase earlier disclosure | Implemented/tested; reference is a shared-primitive cross-check | disclosure_ledger.py; foundation tests |
| Five baseline traces are valid under common replay | Diagnostic evidence; no principal publication evaluation | controller_comparison.json |
| Proposed controller/novel algorithm | No such completed claim; EARP retired | controller.py |
| Timed intermittent-owner service model | Implemented P3B abstract single-grant service; real timed crypto/opening not implemented | timed_authorization_contract.md; timed_service_test.py |
| Cryptographic security theorem/full-run cumulative guarantee | Open, not established by tests | PO1/PO2 |
| Novelty/TNSM suitability demonstrated | Provisional; full-text and systematic comparison open | related_work_reading_log.md |

All timing in this archive is smoke evidence; all optimization costs are declared synthetic units.

## P3A input-layer additions

Implemented/tested: independent service/log coordinates, immutable target-preserving queue,
current-time half-open eligibility, at-most-once trusted completion accounting, deterministic public
log and causal prefix version. See timed_model_contract.md and p3a_invariants.md. These are pure
input/bookkeeping properties, not timed authorization, PRE completion verification, cryptographic
proofs or a new controller. Legacy optimization results retain their old semantics.

## P3B timed-model additions

Implemented: service-time authority, exact offline effect tokens, public/effective-time projection,
causal delays, endpoint rechecks and partial-effect retention, exact abstract usable completion,
separate endpoint/disclosure/active-scope coordinates and actual-vs-observable accounting.
44 integration tests plus five scripted traces are implementer verification, not independent review.

The timed ModelBackend handles abstract share usability, not ciphertexts. T1–T4 in
p3b_proof_obligations.md are conditional model arguments, not new cryptographic proofs. The
implemented delayed-production counterexample refutes an unconditional whole-run disclosure
budget from the observable gate alone. P3C oracle/reference, real timed PRE, controller, objective,
workload and publication evidence remain planned. Legacy claims retain their original limits.
