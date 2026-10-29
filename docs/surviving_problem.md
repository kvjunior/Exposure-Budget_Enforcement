# The surviving management problem, against SACMAT 2025 under aligned assumptions

This document isolates what, if anything, our problem decides that the closest published approach
(SACMAT 2025, Brunello et al., "Relying on Trust to Balance Protection and Performance in CAC")
does not, under assumptions aligned as closely as the two mechanisms allow. It is deliberately
conservative: where SACMAT already covers something, we say so.

## What SACMAT 2025 decides (closest prior art)

- Trigger: an administrator's state change (revoke user from role, revoke permission, delete user).
- Decision: for that state change, whether to execute or SKIP each expensive cryptographic
  procedure — role-key rotation, resource-key rotation, resource re-encryption — and whether
  re-encryption is eager or lazy, according to a tunable trust model (predicates like `untrusted(u)`,
  `eager(f)`).
- Cached-capability state: a four-status partition (incomplete / operational / revoked-**hide** /
  deleted); `hide` explicitly tracks keys a revoked user MAY HAVE CACHED. A `canUserBeCache(u,r)`
  query asks whether u could still assume r with cached keys.
- Soundness: a Prolog consistency check verifies RBAC correctness and safety invariants after each
  state change, e.g. rotate r's keys iff the user is still authorized OR could still assume r with
  cached keys.
- Objective: reduce superfluous cryptographic computations while preserving RBAC correctness/safety.
- Not present: a request ARRIVAL PROCESS; online admission/DEFERRAL of pending delegation requests;
  INTERMITTENT administrator availability or preauthorization; a QUANTITATIVE forward exposure
  budget over a declared adversary coalition; threshold/fragment-structured capability.

## Our decision problem (as specified in slice 2)

- Trigger: a stream of delegation REQUESTS arriving over logical time.
- Decision variables: per request, ADMIT (install t kfrags) / DEFER / REJECT, and separately
  whether to ACTIVATE a fresh key scope now (immediate rollover).
- Information constraint: the controller consumes only OBSERVABLE history up to the cutoff plus a
  PUBLIC declared coalition family; never realized corruption or future ground truth
  (delegation_model/possible.py; tests online_witness_test.py).
- Exposure semantics: a conservative closure over retained material (threshold PRE: t kfrags +
  recipient key -> scope key; mixed fragments), a forward EXPOSURE BUDGET over the declared family
  (coordinate-wise future-scope count and past weight), and an irreversible disclosure ledger for
  cumulative leakage (delegation_model/disclosure_ledger.py).
- Owner-authority restriction: a new grant needs the owner online; offline scope activation needs an
  authentic preauthorization token (per-owner connectivity; manager.py).
- Objective: serve delegation demand at least cost (miss/rollover/fragment units) subject to the
  exposure budget.

## Aligned small instance (what SACMAT's decision does not resolve)

We align assumptions as far as the mechanisms allow: a single resource/scope, a single
untrusted coalition with cloud collusion, whole-key exposure (we deliberately set threshold t=1 so
a single installed fragment already exposes the scope — this removes our threshold advantage and
matches SACMAT's whole-key cached model, to avoid an unfair comparison).

Timeline (one stream g, scope A active, record g:0 produced):
  t: request Q1 = delegate read of scope A to recipient R1 (owner online).
  t+1: owner GOES OFFLINE.
  t+2: request Q2 = delegate read of scope A to recipient R2.
  t+3: request Q3 = delegate read of scope A to recipient R3.
The declared coalition C may corrupt the cloud proxy and any of R1..R3.
Exposure budget: at most ONE simultaneously-exposed active scope (max_future_scopes = 1).

Under SACMAT's model, there is no request queue and no owner-availability notion: an administrator
simply issues or revokes assignments, always available, and the system decides whether to rotate.
SACMAT's consistency check would keep RBAC correct, but it has no decision for:
  (a) WHETHER TO DEFER Q2/Q3 because admitting a second delegation on scope A would push the declared
      coalition over the exposure budget (two exposed recipients on one un-rotated scope), vs
  (b) ROLL a fresh scope first so the new recipient is on a clean scope, vs
  (c) DEFER because the OWNER IS OFFLINE and no preauthorization exists for a fresh scope.
These are online, arrival-driven, availability-constrained, budget-constrained decisions. SACMAT's
execute/skip-rotation decision is reactive to an admin action and assumes the admin is present; it
does not sequence or defer incoming delegations, and it has no forward budget to trade against.

The executable demonstration `python/experiments/surviving_instance.py` runs this instance through
our checked-action path and the exact oracle, and shows:
  - Q1 admitted (within budget);
  - with the owner offline at Q2/Q3, a new grant is REFUSED by the authority check (no online owner),
    and a fresh-scope rollover is REFUSED without preauthorization — so the only budget-and-authority
    feasible action is DEFER;
  - with a preauthorization token present, the controller can instead roll a fresh scope and admit
    the next recipient on it, staying within the exposure budget;
  - the offline optimum over the request sequence differs from the naive always-admit and from a
    fixed-period scheduler.
None of (defer-on-budget, defer-on-offline-authority, preauth-gated rollover) is expressible as a
SACMAT execute/skip-rotation decision.

## Honest nontriviality caveats

- With whole-key exposure (t=1, as aligned above), "a delegation exists on scope A" is close to a
  per-scope exposed flag — so under SACMAT's whole-key model the per-scope STATE is simpler. Our
  threshold/fragment nontriviality result (exposure depends on installed indices vs threshold and
  coalition reach) is a genuine difference ONLY in the threshold-PRE regime, and must be claimed only
  there, not for the whole-key regime.
- What survives even in the whole-key regime is the ONLINE + ARRIVAL + INTERMITTENT-OWNER + FORWARD-
  BUDGET structure, not the cached-key insight itself (which SACMAT has).
- Therefore the defensible contribution is the online, availability-constrained, budget-constrained
  SEQUENCING of delegation admission and scope rollover — a network/service MANAGEMENT problem — with
  the cached-capability accounting adapted (not invented) from the SACMAT-style cached-key insight.
  This is narrower than "we account for retained capability"; that insight is prior art.

## Does the state reduce to a flag / does ordinary scheduling suffice?

- Threshold-PRE regime: state does not reduce to a flag (sufficient_state_test.py).
- Whole-key regime (aligned with SACMAT): per-scope exposure is closer to a flag, but the MANAGEMENT
  problem (defer vs roll vs admit under arrivals, budget, and intermittent authority) is not solved
  by ordinary periodic rotation: the baselines experiment shows fixed-period rollover is strictly
  worse than the exposure-aware policies and the offline optimum on the small instances
  (baselines_vs_oracle.json). Ordinary scheduling does not account for the forward budget or owner
  availability.
- Conclusion: keep the novelty claim narrow and provisional — the ONLINE MANAGEMENT problem under
  arrivals + intermittent owner + forward exposure budget, with cached-capability accounting adapted
  from prior art — pending the TOPS 2022 read and a recent-TNSM scan.
