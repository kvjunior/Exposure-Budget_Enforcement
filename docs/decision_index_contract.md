# Active service-plan contract — Slice 2.2.1

This file is authoritative for the bounded oracle/comparison. Earlier release dispositions are
historical. It specifies a small model, not a timed deployment.

## Inputs and information

A valid observable prefix, its explicit logical cutoff, registered owner/availability, the offered
immutable Grant, authentic-assumed preauthorization, fixed public coalition reach, nonnegative
record weights and exposure budgets. The checker sees no realized corruption or future truth.
The service harness orders requests by their supplied sequence; Request.t is not an arrival clock.

## Actions and plans

Every request gets one plan. K is exactly 1 or 2. Permitted shapes are a singleton ADMIT, DEFER,
REJECT or ACTIVATE; when K=2, also ACTIVATE followed by ADMIT. At most one admission occurs.
An ADMIT must equal the entire offered Grant. Its distinct valid delivery indices are represented
in sorted order. Every subset of the grant's shares, including the empty set and supersets of its
threshold, is enumerated. There is no unsupported dominance pruning of unserved admissions.
A rollover is restricted to the request stream's canonical next epoch, key identifier
`stream.e<epoch>.k0`, and next produced sequence. These restrictions are enforced by replay.
The lower-level checker/executor may validate actions outside this canonical planning domain;
no oracle optimum over arbitrary low-level commands is claimed.

A plan with at least threshold distinct compatible installed indices usably completes its grant.
A metadata/partial admission still creates historical authority but remains unserved for this
request's decision. Grant IDs cannot be reused. Partial backend delivery over a network and later
retries require a separate future execution model, not an implied extra operation in this grammar.

## Unchanged cost arithmetic, centralized

Let M be miss/opportunity cost, R rollover cost and C fragment cost, all finite and nonnegative.
For a pending request: DEFER/REJECT cost M; ROTATE costs M+R; an admission with k indices costs kC
plus M if k is below threshold. Plan costs add. Previously the partial-admission M was added in
oracle/replay; it is now in action_cost so policies score the same operation correctly. No second
completion miss is added. Thus full rotate/admit costs M+R+tC even though its final service count
is one. Metadata alone costs M, not zero. These are declared units, not CPU/byte measurements.

This waiting/opportunity objective can prefer a cheaper plan serving fewer requests. The corrected
metadata fixture costs 24 serving one; the 25 witness serves two. Neither count is hidden. A future
timed model must distinguish actual waiting from terminal deadline failure before publication.

## Executor

An action's event plan begins at observation.cutoff+1, including after a logically idle prefix.
An explicit different t0 is refused before approval; commit-time mismatch returns no delivery.
The receipt binds log digest/version, cutoff, complete action, preauthorization context, exposure
configuration and planned events/effects. The executor rebuilds derived state from the observable
prefix, compares all bindings, reruns the checker and commits the same events. Passing the same
preauth context is required at execute() for offline approvals. No signatures/durable atomic I/O
or concurrent network transaction protocol is claimed.

## Bounded exactness and independent reference

The oracle enumerates this entire canonical grammar with all 2^shares delivery subsets. The subset
count is checked before allocation; too-large instances raise rather than return an incomplete
optimum. max_branches caps delivery-subset count; max_steps caps request count. K outside 1/2 is
unsupported. Replay may verify a trace without performing an optimality search.
The separate reference generates its own choices and implements its own authority/token, plan,
service and cost logic. It shares immutable inputs, transition folding, coalition expansion and
possible exposure. Agreement is bounded validation, not a cryptographic/whole-system proof.

## Security scope

The guard bounds endpoint collateral weight and exposed active-scope count at admission. It does
not bound the irreversible disclosure ledger or promise preservation across unchecked production,
owner-root compromise, arbitrary disclosure or adaptive coalition histories. The family expansion
has 2^recipient_count cases per entry; scalability is not established. PO1 remains assumed.
