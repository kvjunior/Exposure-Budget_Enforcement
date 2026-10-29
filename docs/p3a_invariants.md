# P3A invariants and remaining obligations

These are ordinary model arguments for the pure APIs, not mechanically checked proofs or
cryptographic reductions. Assume valid immutable inputs, ordinary API use without malicious
reflection, and an honestly minted USABLE receipt from a trusted backend. P3A does not implement
or authenticate that backend.

## I1: service time and append order remain distinct

Constructors admit only nonnegative integer fields of their own runtime types. advance_to checks
monotonic time and preserves last_sequence; record adds one sequence and preserves now. Induction
gives monotonic independent coordinates. Same-time appends and idle time without appends are valid.

## I2: demand identity and targets survive waiting and rotation

A unique-ID queue entry retains a frozen Demand. All queue transitions reuse that same Demand and
replace status/terminal fields only. No operation substitutes a scope or new record target.
Completion matches the full ID/owner/recipient/targets. A notice in another immutable log cannot
mutate the queue. Thus demand identity is preserved by the public queue APIs.

## I3: terminal service is credited once and before deadline

Only pending entries can complete, reject or defer. Advancing to/past a deadline expires pending
entries and never changes terminal states. A completion needs current-time USABLE evidence; queue
validity requires pending now < deadline. Therefore completion is eligible, and a terminal state
cannot be revived or completed again. Unique receipt IDs prevent double credit across demands.
This is bookkeeping under a trusted-receipt assumption, not proof of cryptographic completion.

## I4: waiting/failure accounting retains unfinished work

Each demand contributes terminal_time-release or now-release. Expiry fixes terminal_time=deadline,
including late offers. Values are nonnegative. Time advancement increases waiting only until
termination/deadline; terminal times remain fixed. Pending is exposed separately from failures
and success. A finite observation horizon does not turn unfinished work into successful service.

## I5: log integrity, failure atomicity and prefix noninterference

A new immutable log validates contiguous sequences, monotonic logged times, availability <= logged
instant, canonical same-time ordering, and unique IDs/facts. A batch is built locally before a
new log is returned. A rejection cannot mutate its original immutable log.

Fix cutoff t and an optional known sequence frontier. If an extension appends only entries logged
strictly after t, its filtered prefix equals the original. The view reports that prefix's version,
not total future length. Hence old views are equal under such extensions. At the same tick new
information can legitimately change the version; an explicit through_sequence bound reconstructs
an earlier frontier. Time alone does not order simultaneous observations.

This is input-prefix noninterference, not proof that a simulator drains all ready reports, gives
policies only that view, or aligns a queue snapshot to the same time. Those are P3B obligations.

## Executable evidence

29 contract tests include 24 batch permutations and 1,296 four-operation tapes / 5,184 transitions
against a separate dictionary queue reference. The reference does not call production queue APIs,
but is written by the implementer. It is not independent laboratory review and its finite tape
alphabet does not prove all possible histories.

## P3B obligations

- Align service clocks and visible log versions when constructing joint queue/log observations.
- Process due public events and expiry before decisions; keep environment/oracle future truth
  separate from online inputs. A view alone does not certify a drained input frontier.
- Introduce typed service-time authorization/windows with an explicit legacy migration. Never
  silently treat old inclusive Event.t validity as half-open service time.
- Preserve original target-to-ciphertext/scope identity and verify catalogue consistency. Delayed
  effective-time reports must not blindly overwrite newer effective owner state.
- Gate each actual capability delivery using fresh owner/token authority and exposure context.
  Define interrupted partial delivery without rolling back retained material.
- Mint USABLE receipts only after verified authorized usable completion.
- Specify waiting, terminal failure and horizon censoring before a scalar objective is frozen.

PO1 closure soundness, full-run/cumulative/adaptive guarantees, deployed-service security and the
literature/novelty gate are still open. P3A closes none of those obligations.
