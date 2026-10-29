# P3B service-time authorization and causal execution contract

Status: implemented finite, single-threaded MODEL service. No timed cryptographic backend,
controller, optimality theorem, measured network latency, or publication workload is supplied.
P3A's typed input contract remains in force. Legacy Event.t/Grant.valid_to are not cast to service
time. Existing legacy code and proof claims are not silently upgraded by this batch.

## Trust and supported service

All scope/owner notices and provisioned tokens are authentic environment assertions. TimedGrant
records are issued only through the simulator's authority path. IDs stand for genuinely distinct
fresh scope keys as an ASSUMPTION; validating different labels does not prove key independence.
Owner-root compromise, token forgery, dishonest report content and arbitrary backend claims are
outside this model. Reports may be delayed. Actual owner availability is environment-only.

The default ModelBackend attests abstract usability from matching cfrag indices. It handles no
ciphertexts or key bytes. Completion requires a correctly bound UsableResult after sufficient
fragments and a final time/window check. A future real adapter must actually decrypt the authentic
record bytes, check their identity and scope, and satisfy the same result contract. The existing
historical Umbral witnesses and HPKE smoke do not implement that timed adapter.

A demand names a finite exact record tuple. This batch can serve a demand when ONE timed grant
covers all targets in ONE scope and owner. Other demands remain pending/rejected/expired; they
are never rebound to a new record or credited with partial coverage. Multi-grant/multi-scope
completion is future work. An owner may be offline while a producer device continues emitting.
Proxies can transform installed shares for a live grant while the owner is offline.

## Coordinates, reports and within-tick order

ServiceTime is integer model ticks. LogSequence orders public input appends. Manager revision
orders public action outcomes/effects separately. Durations are fixed positive model ticks;
they are not measured costs. They represent waiting until an atomic step's delivery endpoint,
not continuous transport connectivity. Availability is required at each endpoint; an outage that
recovers within a step does not cancel that step. No wall-clock/thread scheduling is modeled.

At each reached tick the runner:

1. Advances time and expires queued demands whose half-open deadline has been reached.
2. Processes actual owner transitions, scope activation notices, record productions and arrivals
   by their occurrence time (owner, scope, production, arrival order). Production binds to the
   authentic scope active at that source sequence. Actual production/availability remain private
   until reported. Source sequences strictly increase per stream.
3. Appends all available public reports in P3A canonical order; offers newly reported demands,
   including immediately expired late arrivals. Projection selects the owner report with the
   greatest OCCURRENCE time, not the last append. An older delayed report cannot overwrite it.
4. Refreshes observable and evaluator-only exposure accounting. Then the pending service step
   can be checked and committed. A same-tick owner-down precedes raw delivery; deadline expiry
   precedes completion. Actual production at a rotation endpoint uses the old scope first.

advance_to visits every intervening occurrence, availability and pending deadline. Defer uses
this runner, not the queue's bare jump. Queue/log clocks remain aligned. A reporting horizon is
censored: pending demands stay pending, waiting accumulates until that horizon, and no synthetic
rejection is inserted. Closed-horizon admission/service objectives remain to be frozen before
optimization. Rejected and expired counts remain separate; terminal_failures is their sum.

## Authority and action effects

Tokens are immutable authentic pre-provisioning assumptions, not implemented signatures or
owner-secret generation. GrantToken binds the ENTIRE TimedGrant, allowed raw indices, and its
own half-open time window. ActivationToken binds the exact owner/scope/key-ID/start-sequence
activation and a window. They are reusable only for those idempotently guarded effects while
valid. They do not authorize each other's effect type. No token revocation is implemented yet.

InstallGrant requires a pending matching demand, observed authentic target catalogue and current
grant validity. For metadata issuance and EACH raw-share endpoint, public owner authority or
an exact unexpired grant token is required; the authoritative backend additionally requires the
owner actually online or that token. Tokens model precomputed material available offline. A
stale public up-report cannot manufacture owner participation. The initial scope owner must match.
An issued grant's metadata may legitimately authorize records even before usable service exists.
The declared grant's raw indices are installed sequentially; already installed indices are refused.
An unchanged issued grant can later install its remaining indices without a second issuance.

Transform requires an issued unrevoked grant, live service window, pending matching demand,
known original record scopes/ranges, and installed raw shares at each requested index. It does
NOT need the owner online: proxies already have authority/material. It delivers per-record cfrags
one by one with per-endpoint rechecks. Then it waits open_ticks and rechecks the window/deadline
before accepting a correctly bound backend usability result. Partial cfrags, metadata, backend
exceptions, wrong recipient/target results, and completion exactly at expiry do not count as service.
Existing retained cfrags can later be retried without duplicate delivery credit.

ActivateScope is prospective only. It requires the same observed owner, exact next epoch, fresh
key ID, and start_seq = next observed source sequence, strictly above existing scope starts.
The backend checks actual next sequence and authentic scope uniqueness again at completion.
Unobserved intervening production can therefore refuse activation. Empty-scope rollover with
an unchanged start is outside this batch's bounded grammar. Old records keep their original scope;
new production chooses the scope applicable at its actual production endpoint. A fresh activation
adds no retained capability and cannot increase any modeled exposure coordinate; it may mitigate
an existing active-scope breach without erasing a permanent ledger breach.

RevokeGrant requires the owner observed and actually online at its endpoint. It stops new service
under that grant, but does not delete fragments, ever-authorized record permissions or disclosures.
Defer preserves the same demand and processes events. Reject is terminal without service credit.

Every request supplies the FULL frozen PolicyView returned by view(). Equality binds the visible
history, time, queue, grants, deliveries, provisioned authority, family, budgets and manager revision.
A stale/mismatched view is refused before any clock advance or effect. A refused operation delivers
no NEW material. If an operation has already issued metadata or delivered a prefix before a later
veto, its status is interrupted; the issued metadata and fragments remain. It is never rolled back.
A later failure does not invalidate an authentic prior delivery or a first disclosure it caused.

## Capability and exposure accounting

The family is declared public reach, not realized corruption. Each reach expands ALL recipient
subsets (including empty), keeping its proxy reach. Because coalition authorization changes with
recipient membership, checking only the full recipient superset is unsound. P3B bounds candidate
recipients to eight per declared reach; this remains exponential finite enumeration, not a scalable
controller. No claim is made for omitted coalitions or owner-root compromise.

For each exact-recipient case, raw fragments routed to its reachable proxies and cfrags delivered
to its recipients are retained. A recipient key plus threshold raw shares of ONE grant exposes
that grant's scope key. For one capsule, raw and received cfrag indices form a UNION, so a repeated
index counts once; shares from different grants do not mix. Scope keys open all produced records
in their original scope, including outside grant ranges. The algebra is assumed to model the
backend conservatively (PO1); the separate finite reference checks implementation arithmetic,
not cryptographic soundness.

A produced record is ever authorized if a grant to a case's recipient covered its original scope
and range during some phase after both issuance and production and before revocation/expiry.
Production at a manager-revocation tick precedes that revocation and remains ever authorized;
production at a window-expiry tick follows expiry and is not newly authorized. This phase distinction
is explicit in authorized_ever, including when the production report arrives later.
Old records can be intentionally authorized later. Records already authorized do not become
collateral merely because a reader keeps their plaintext after expiry. Authorization is monotone
per produced record, but a FUTURE record produced after a grant expired is not authorized by it.

Three metrics stay separate per case:

- endpoint collateral weight: currently openable produced records outside ever authorization;
- irreversible disclosure weight and first service tick: each record first openable while
  unauthorized, never removed by later permission, expiry, revocation or rotation;
- exposed ACTIVE scopes: exposed scope keys still used by a stream's current scope.

Grant issuance and each raw/cfrag delivery are previewed against all three OBSERVABLE budgets
for EVERY case. Existing ledger breaches conservatively block new such effects until the model's
constraints can be met; this batch does not promise recovery from an irreversible breach.
Activation is a non-increasing mitigation and remains available if authorized.

Weight sums/comparisons use exact rational arithmetic on the supplied integer or IEEE float
values, so adding a tiny positive weight cannot round it away at the gate. Non-integral JSON pilot
weights are serialized as numerator/denominator pairs; this does not recover a decimal quantity
that was already rounded by a caller before input. All pilot record weights are unit weights.

"Actual exposure" means modeled potential exposure for the declared possible coalition cases
over actual production, not observed corruption or measured successful decryption. No realized
compromise channel is supplied to the policy.

This is an observational gate, NOT a whole-run hard disclosure guarantee. Evaluator accounting
uses actual production at occurrence, whereas the policy/checker sees only reported records.
Even if a delivery passes the observable gate, an exposed active scope can open an unreported
record immediately at production. Exogenous production can also breach a previously satisfied
budget without any new management action. The evaluator logs those breaches, including the
external-production cause and first tick. Later reporting records public detection at its own
later time; this is deliberately separate from the actual disclosure time. report() is evaluation
output and MUST NOT be passed to a policy. Python API conventions are not process isolation.
A complete/fenced production catalogue or a justified worst-case arrival envelope and reservations
would be needed before claiming a hard whole-run budget; none is assumed implicitly.

## Input validity and unresolved boundaries

Environment traces are immutable and causally typed, with unique facts/IDs; conflicting owner
facts at one occurrence are rejected at construction. External scope notices must remain
consistent with managed scope activations along a chosen run. Contradictory scope keys, source
sequence regressions or production without an authentic scope are fatal invalid-environment
errors, not refused manager actions. This simulator is not a transactional recovery system for
invalid traces. The scripted pilot uses initial scope provisioning plus action-dependent dynamic
production, avoiding a fictitious fixed future scope for every branch.

The environment owns the full trace/backend. Policies receive only PolicyView and can choose an
action; future schedules and evaluator metrics are excluded. A malicious Python closure could
still capture the environment object; preventing that requires a separate deployment boundary.
No future-dependent oracle, multi-grant completion, network failure distribution, timed PRE
adapter, objective or publication figures are included. The next batch must use precisely this
bounded contract and address the producer-observation limit rather than silently giving an
online policy the evaluator's hidden records.
