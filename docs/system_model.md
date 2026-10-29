# System model

Entities: Owner O (authorization authority per stream), Producer D (emits signed records),
Proxies p0..p_{N-1} (hold kfrags, perform transforms), Recipients R (delegatees), Manager
(online controller; proposes admit/defer/reject/activate), Storage (holds envelopes).

State objects (kept strictly separate; see delegation_model):
- Authorization state: live grants, ranges, recipients, validity, revocations, scope spans.
- Key-scope state: stream -> ordered (stream,epoch) spans with concrete scope_key_id and
  half-open seq ranges; one owner key per scope; epoch roll = new scope, old records keep
  their old scope.
- Retained knowledge K_t(C): kfrags, cfrags, data keys, scope keys, recipient keys,
  plaintext a coalition could hold. Monotone in t; revocation does not shrink it.
- Operational state: owner connectivity, proxy availability, preauth tokens, queues.
- Controller observations: observable events up to a cutoff only (no compromise, no future).

Time: logical integer per event = position; service layer linearizes concurrent events.
