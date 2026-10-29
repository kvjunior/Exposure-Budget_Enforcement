# P3B conditional arguments and remaining proof obligations

These are reviewable mathematical arguments about the finite model, not machine-checked proofs
or cryptographic reductions. Tests cannot establish universal security. The legacy PO2 remains
an ADMIT endpoint statement in the old decision-index model.

## Preconditions

A1: valid authentic environment reports, immutable scopes/records, distinct independently sampled
scope keys behind fresh IDs, authentic correctly provisioned tokens; no owner-root compromise.
A2: declared family covers the adversary reach; exact-recipient cases are enumerated; proxy
reach is an upper bound. No unsupported direct-secret disclosure channel is introduced.
A3: valid finite histories and single-threaded execution through ServiceSimulator, not arbitrary
mutation of its private fields. Policies receive only PolicyView. Backend checks actual owner
participation or exact provisioned token and binds its usability result to authentic record bytes
when a real cryptographic implementation is eventually attached.
A4: raw/cfrag union and scope-key recovery closure soundly upper-bound the chosen primitive (PO1).
The current ModelBackend supplies only abstract usability; A3's byte-level obligation is OPEN.

## T1 — checked delivery preservation (conditional local statement)

For a valid run, each new raw delivery is appended only after a current-time demand/target check,
a current grant check, exact index authority and a passing observable-family gate. Each new cfrag
is appended only after current-time pending/grant/target/raw-installation checks and that gate.
A stale initial PolicyView adds no material and advances no time. Refused actions add no material;
an interrupted multi-step action may leave a previously committed prefix, which remains checked.

Argument: execute first compares the full frozen view. Each InstallGrant/Transform loop advances
through the event scheduler and recomputes checks at its endpoint; only _commit appends material.
Raw delivery additionally checks actual owner participation or a valid exact grant token. Transform
uses installed authority without requiring the owner anew. No rollback branch removes material.
This argument does NOT assert continuous transport availability within a step's duration.

T1 is about individual OBSERVABLE endpoints. It does not imply every actual record was observed,
that future exogenous production is bounded, or that later cumulative disclosure stays under budget.

## T2 — immutable completion and queue accounting

A demand is served at most once and only with a matching UsableResult after threshold distinct
cfrags for every original target, before the service and grant windows end. Deadline/arrival
processing happens before completion at a tick. Otherwise the demand stays pending or becomes
an absorbing rejected/expired state. Its waiting is release-to-terminal/current time, never
past its deadline after expiry. No defer replaces the request or skips intervening inputs.

Argument: P3A's queue constructors and complete reject non-pending/mismatched/late receipts.
Transform checks enough distinct indices and validates the exact result then supplies the queue
with an exact current-time USABLE receipt. The scheduler advances through occurrence/availability/
deadline endpoints before returning to any delivery. The receipt is still a TRUSTED adapter
assertion; real decryption and cryptographic identity verification remain A3 obligations.

## T3 — retained knowledge and first disclosure are irreversible

Fix one declared exact-recipient case and valid reachable history. The retained delivery set
is monotone, and each ledger's record set and first tick are monotone/preserved. Later authority,
revocation or fresh activation cannot erase an entry. Fresh activation changes no old record's
scope and introduces no new retained capability; hence it cannot increase endpoint collateral,
ledger weight or exposed-active-scope count (under A1's independent fresh-key assumption).

Argument: _commit only extends deliveries; revocation changes metadata but not deliveries.
assess starts from the previous ledger, uses setdefault for new collateral and never deletes an
entry. Record weights/identities are immutable, so cumulative weight cannot decrease. Activation
adds a scope without an issued grant or retained share for it; all old records remain bound to
their prior scope. The old active scope is retired or the active exposed set is unchanged.
This does not cryptographically prove independent keys from unequal IDs.

## T4 — causal public prefix (limited information statement)

For two valid runs with equal initial public configuration and equal visible input/action-feedback
prefixes at a service frontier, PolicyView is equal regardless of unobserved future trace suffixes.
Therefore a deterministic policy supplied only that view chooses the same action. This does NOT
mean equal actions always yield equal future outcomes if actual owner availability/production
differs during execution: observed backend refusal is legitimate new feedback.

Argument: view uses only the public log prefix, aligned queue, managed public effects, provisioned
tokens/family/budget, public ledger and revision. Projection chooses owner notice by occurrence,
not append order. The full schedule, actual owner state and actual exposure are omitted. Private
production does not advance public revision. The scheduler eventually reports facts at availability.
This is API-level separation, not a malicious-code isolation proof or timing side-channel theorem.

## Counterexample to a stronger claim (implemented)

Issue a grant for record g:0, threshold two, to a recipient potentially colluding with both proxies.
Two raw shares recover scope g:0's key. Endpoint and disclosed weights are zero at tick 3 and the
exposed active-scope cap is one. An unauthorized g:1 produced at tick 4 under that still-active
scope leaks immediately; its public report is available at tick 8. The observable ledger remains
zero until 8; the actual ledger is one starting at 4. Rotation after 8 retires the active scope but
cannot repair the disclosure. Rotation at tick 4 BEFORE a production at tick 5 binds that new
record to a fresh scope and avoids that particular disclosure. The pilot includes both traces.

Thus A1–A4 do NOT yield a whole-run zero-disclosure theorem with delayed/unbounded production.
A publication claim needs explicit production completeness/fencing or an arrival envelope and
reservation model, not extra tests or use of hidden evaluator state in an online gate.

## Still open

- PO1 cryptographic closure soundness and independently justified family coverage.
- Real timed backend byte-level binding, signature/token verification, material provisioning,
  interrupted physical delivery and the precise endpoint used to credit service.
- A stable horizon/service objective and bounded action grammar for a timed oracle/reference.
- Producer-observation assumptions or a proved impossibility/feasibility result under delays.
- Multi-grant/multi-source completion, token revocation and recovery after irreversible breaches.
- Literature comparison and novelty gate. No new controller or security theorem is claimed here.

Verification: 44 integration tests, 54 deferral tapes/162 arithmetic checkpoints, 384 separate
mixed-capability bit-mask cases, 24 simultaneous-input permutations, and five scripted model traces.
These are all implementer-authored/run; Claude's independent review is pending.
