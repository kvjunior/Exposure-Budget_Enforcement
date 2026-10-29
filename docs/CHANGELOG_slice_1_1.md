# Change log: slice 1.1 (corrections to slice 1)

Slice 1 is preserved unchanged (archive sha256 a900985e...; frozen as the reviewed baseline).
Slice 1.1 reproduces the independent review's R1-R8 against the frozen slice first (all eight
reproduced), then corrects them. Each change below names the finding, the files touched, and
whether it is a program-defect repair or a semantic/witness-contract revision.

## R1 (program defect) - closure under-approximated a mixed-fragment capability
- delegation_model/closure.py: replaced the separate R3 cfrag rule with R3', which unions
  received-cfrag share indices with locally-derivable indices from held raw kfrags (local
  transformation of the public capsule), counting each SHARE once. A raw kfrag and a cfrag at
  the same index are one share; cfrags from a different grant do not combine.
- python/reference/knowledge_closure.py: same fix, independently (F3'). Both implementations
  were updated: agreement when both omit a capability is insufficient.
- tests/adversarial/mixed_fragments.py: grounds R3' in real Umbral (received + locally-made
  cfrag opens the capsule), with no-double-count and incompatible-grant guards.

## R2 (program defect) - budget aggregation picked one lexicographic coalition
- delegation_manager/exposure_check.py: evaluate every budget dimension for every coalition;
  take COORDINATE-WISE maxima with separate witness coalitions (future_witness, past_witness).
- tests/differential/checked_action_test.py (R2 part): different coalitions witness different
  breached dimensions; order-independent.

## R3 (implementation gap) - exposure was not gated on the action path
- delegation_manager/manager.py: a single checked-action path now evaluates an ADMIT's declared
  capability-delivery effects (authorized_kfrag_indices) BEFORE execution, over a declared
  coalition family, and VETOES budget-breaching admissions. An ADMIT that declares delivery with
  no budget/family supplied is REFUSED (never silently skipped). A pre-execution veto installs no
  material.
- tests/differential/checked_action_test.py (R3 part): actual veto, nothing installed.

## R4 (research-witness revision, documented) - the pair differed only in hidden corruption
- The original safe/exposed pair is KEPT as a NON-INTERFERENCE test (identical observations =>
  identical decisions). A NEW online-policy witness (history_lowobs/highobs in
  python/reference/witness.py) has the same current ACL but DIFFERENT observable installation
  history, distinguishable from observable history alone.
- delegation_model/possible.py: conservative POSSIBLE-knowledge from observable history + a
  public coalition reach (no realized corruption), used by the controller.
- tests/differential/online_witness_test.py.
  This is a deliberate research-witness revision, not a program-defect repair.

## R5 (program defect) - stream ownership was not checked on admission
- delegation_manager/manager.py: OwnerRegistry binds stream->owner from StreamAuthorized;
  check_action rejects a grant whose issuer is not the registered owner, and rejects grants on
  unregistered streams. PreAuth now carries a `verified` flag distinguishing an ABSTRACT token
  set from actual signature verification (surfaced as an assumption; real verification is a
  service-boundary task, not implemented here).

## R6 (program defect) - fresh-scope action accepted the already-active scope
- delegation_manager/manager.py: ACTIVATE_SCOPE requires a scope not already active, a fresh
  (unused) scope_key_id, and a start_seq that does not reassign already-produced records.

## R7 (program defect) - expiry used last event time, not the requested cutoff
- delegation_model/authorization.py: the validity clock is the REQUESTED observation time; it
  advances across idle intervals. A grant expiring at t=5 is not live at cutoff 10.

## R8 (semantic-contract revision, documented) - post-revocation data was silently exempted
- delegation_model/closure.py (authorized_records_of): a record counts as authorized to C iff
  produced on/before the grant's end of authorization (revocation time, or valid_to if earlier).
  Retained old plaintext stays authorized; data first produced after revocation is collateral.
  This fixes the slice-1 behaviour that counted any in-range record regardless of production
  time. Documented as a semantic contract in docs/exposure_semantics.md, not a silent change.

## Claim/novelty status
- Novelty gate downgraded from "provisionally passed" to "provisional, pending full-text JNCA
  2025 and the TOPS extension" (the author PDF is reachable; see novelty_matrix). Reading the
  2022 construction cannot establish what the 2025 extension adds.
- C10 (controller usefulness) and C11 (conditional exposure bound) remain hypotheses; C11 needs
  a mathematical argument, not measurements.
- The proposed controller stays explicitly UNSUPPORTED until the history-aware baselines and the
  exact small-instance oracle exist.
