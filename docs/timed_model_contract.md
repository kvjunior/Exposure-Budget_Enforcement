# P3A timed-input contract — service time, immutable demand, observed public log

This layer supplies pure inputs/state for the later simulator. It does not yet
change legacy Event.t, grant/token validity, the checker, PRE delivery, the
decision-index oracle, or any paper result. Slice 2.2.1 remains the old baseline.

## Two independent coordinates

ServiceTime(ticks) is a nonnegative integer count of declared model ticks, not
wall-clock time or measured latency. LogSequence(value) is a nonnegative append
counter, with 0 denoting an empty log. They are separate runtime types, reject
bool/float/negative values, and have no implicit integer conversion. A clock may
advance while the sequence stays unchanged. Several log entries may have the
same service time while their sequence values remain strictly increasing.

Windows are half-open [start,end). Demand release must precede its finite
deadline. Completion at release is eligible; completion at the deadline is late.
New service windows are NOT the old inclusive integer valid_to fields. P3B must
define a typed authorization migration instead of feeding service ticks to an
order-index authorization routine. No implicit legacy event adapter exists here.

## Immutable demand and completion

A demand names one owner, one recipient and a nonempty exact set of concrete
(stream,sequence) record targets, plus release/deadline and an immutable demand
ID. Targets are canonicalized into a sorted immutable tuple; duplicates and
malformed record identities are rejected. No key scope is substituted for a
record target. The future backend must resolve each target to its authentic
original ciphertext/scope. Open-ended subscriptions need a separate future
contract and are not silently expanded into this finite-record demand.

The queue contains only observed/offered demands released by its current time.
It is immutable: each update returns a new queue. Duplicate demand IDs are
rejected. A release already past deadline can be offered late, but immediately
becomes EXPIRED rather than eligible pending work.

Statuses: PENDING -> SERVED, REJECTED or EXPIRED. Terminal states cannot return
to pending or complete twice. advance_to(t) advances monotonically and expires
pending demands at their deadlines, including across idle intervals. A defer
operation explicitly supplies until; it advances time while retaining demand
identity/targets, or expires the demand if its deadline is crossed. It does not
deliver material or append a fictitious log event. The later simulator must
process intervening external events instead of skipping them during a delay.

Completion requires a typed, trusted-backend CompletionReceipt for this exact
ID, owner, recipient and set of targets, stamped at the queue's current time.
METADATA/PARTIAL receipts do not complete a demand; only USABLE does. A receipt
ID cannot be credited to another completed demand. This is a contract assertion
from a trusted adapter, NOT a cryptographic proof or a verifier implemented in
P3A. P3B must issue it only after actual authorized usable service. The receipt
lists targets satisfied for the demand, not every record a recovered key could
open; extra retained capability belongs to the separate exposure model.

## Waiting and terminal service metrics

The layer reports served, rejected, expired and pending counts separately.
Waiting is summed in request-ticks from release to service/rejection/deadline,
or to now for pending demands. It stops at the deadline even for a late offer.
Terminal nonservice is rejected+expired, credited once. Pending is explicitly
censored, not silently counted served or erased. A closed evaluation must drain
through deadlines or disclose censored pending demand. No scalar objective or
new penalty coefficient is chosen here. This prevents silently inheriting the
old cost-24/served-one versus cost-25/served-two interpretation.

## Public log and delayed reports

Whitelisted frozen payloads are owner availability notices, scope notices,
record-production notices (including the original scope), and demand arrivals.
An envelope records occurred_at and available_at; require occurred_at <=
available_at. A demand arrival's occurrence equals its release. No legacy event
with an ambiguous t, realized corruption/disclosure, arbitrary dict or unknown
payload is accepted. P3A validates shape/identity, not signatures/catalog truth.

Appending a batch requires every report to be available by the clock's now.
Each committed entry gets a distinct contiguous sequence and logged_at=now.
An already committed ID/fact cannot be appended again. Fact identity is the
record ID, scope ID, demand ID, or (owner,occurred_at) for availability. Conflicting
same-instant owner notices are rejected rather than resolved by arbitrary IDs.

Within a logging instant, ordering is by available_at, payload phase (owner,
scope, record, demand), occurred_at, domain identity, then event ID. Record ties
use stream and record sequence. A later batch at the same logging time must not
precede the existing tail under this order. Appends never reorder committed
entries. Batch failure leaves the previous immutable log unchanged.

Logged time records when information entered this log, so an earlier occurrence
or availability does not retroactively make a delayed report visible. A public
view at cutoff contains only entries logged by that cutoff and carries only
that prefix's sequence/version. It does not reveal total future log length.
Policies must receive this observation, not an environment's full trace/log.
A view is not a certificate that all external ready reports have been drained.
The simulator owns that completeness obligation. A late backdated owner report
must not blindly overwrite a newer effective owner state in P3B.

## Required simulator ordering (P3B, not implemented here)

At service time t: advance clocks/expire existing deadlines; drain/apply all
public reports ready at t in canonical order; offer newly observed demands
(late ones expire immediately); then perform decisions/backend completion at t.
An owner-down notice at t precedes a new service decision at t; expiry precedes
completion at the deadline. Authority and retained-capability exposure must be
checked at actual delivery time. The queue alone does not authorize a grant.

## Worked trace

Demand D targets an already-existing record g:0, released at 0 with deadline 6. Offer it at time 0.
At 1 the owner-down notice is logged and D is deferred to 3: D remains pending,
unchanged, with 3 waiting ticks. A record g:1 is produced under its own declared
scope at 2, but its report becomes available at 4; it is absent from views at 3.
At 4 log that report and an owner-up notice, before the service decision. A
trusted USABLE receipt for D's original g:0 at 4 serves it once with 4 waiting
ticks. Its target is never replaced by g:1 or a new epoch. Alternatively, with
no completion, advance to 6: D expires, terminal failure=1, waiting=6, pending=0.
No authorization/cryptographic permission for these hypothetical completions is
asserted by this input-layer example; that is P3B's backend gate obligation.

## Scope

P3A proves no PRE security, whole-run exposure bound, controller superiority,
novelty or journal readiness. The typed input invariants and executable examples
support the next causal simulator; all existing cryptographic assumptions and
literature obligations remain open.

An optional known through_sequence frontier reconstructs earlier same-tick snapshots. P3B must align queue and public-log times when forming joint policy observations.
