# Corrected spine (P3D): conditions for feasibility/impossibility of online exposure-budget enforcement

This supersedes the headline claims of docs/dichotomy_spine.md. The audit (Task 1) found the earlier
Theorem 1 overstated (it is NOT a universal impossibility), the earlier "iff" FALSE (fencing is
sufficient but not necessary), and the earlier Theorem 2 FALSE as stated (it ignored retroactive
disclosure by future grants). Each correction is backed by an executable counterexample against the
real simulator (tests/differential/p3d_counterexamples.py). We state a narrower, valid
characterization in place of the earlier universal claim, per the brief's preference.

Label key used throughout: PROVEN (model-level argument), MODEL-CHECKED (executable witness on the
simulator), ASSUMED (a stated assumption, e.g. closure soundness), OBSERVED (empirical on tiny
instances), OPEN.

## Precise setting (Task 1.4)

- Discrete service ticks. A stream g with key scopes sigma=(g,epoch); a scope is ACTIVE iff no
  higher epoch on g exists. Records r=(g,seq) are produced at ticks and bound to the active scope at
  production (service_simulator binds to the highest-epoch truth scope at the production tick).
- A declared PUBLIC coalition family F (set of (recipients, proxies) reaches). A scope sigma is
  RECONSTRUCTIBLE by a case in F iff that case holds >= threshold raw shares of SOME grant on sigma
  to proxies it reaches (timed_capabilities.openability). Reconstructibility of a scope opens EVERY
  record under it (scope key opens the whole scope), while AUTHORIZATION is range-limited
  (timed_capabilities.authorized_ever). COLLATERAL = opened minus authorized.
- DISCLOSURE ledger L(t): the monotone weighted set of records first opened-while-unauthorized by
  time t (evaluator truth; report()['actual_exposure']). L is irreversible. BUDGET B = a cap on
  L(t) (disclosed_weight) for ALL t (a whole-run bound).
- The ONLINE CONTROLLER observes only the PUBLIC view (public reports arrive at available_at >=
  occurred_at; private production does not advance the public prefix). It controls admission
  (install/transform/activate/revoke/defer/reject). The ADVERSARY/ENVIRONMENT controls owner
  availability and -- UNLESS a fence mediates -- the timing and scope-binding of production. Between
  a controller observation and its enforcement, production and report-arrival events can occur.
- Confidentiality that a reconstructible scope's key opens its records is ASSUMED (closure
  soundness, PO1); it is computational, not information-theoretic.

## Corrected Theorem 1 (impossibility for a RESTRICTED controller class) [PROVEN, conditional; MODEL-CHECKED]

Let a controller be PRODUCTION-BLIND if it does not control the timing or scope-binding of
production (it cannot fence). Suppose a reachable state in which (i) some scope sigma is
reconstructible by a case in F (a consequence of a prior admitted threshold delivery the controller
allowed), (ii) an unauthorized record r may be produced under sigma at a tick t_p with report delay
delta>=1, and (iii) the budget B < w_min. Then no PRODUCTION-BLIND online controller restricted to
the public log can guarantee L(t) <= B.

Argument. r is disclosed to the case at t_p (it holds sigma's key, r unauthorized), so L(t_p) >=
w_min > B. The controller's first information about r is its report at t_p+delta; L is irreversible,
so no post-report action repairs it; and before t_p the public view does not distinguish the
breaching run. QED, conditional on closure soundness (ASSUMED). MODEL-CHECKED by
p3d_counterexamples.py (the unfenced breach reaches actual disclosed weight 1 while the public ledger
lags).

WHAT THIS DOES NOT SAY (corrections to the earlier universal claim):
- It is NOT impossibility for EVERY online controller. A controller that is NOT production-blind
  (fences production, Thm 2), or that REFUSES the admission so no scope becomes reconstructible
  (CE-REFUSE), or that runs with B >= producible unauthorized weight (CE-NEC), is not covered and
  can meet the budget. Impossibility is specific to: production-blind + already-reconstructible +
  tight budget + delayed reports.
- The limit is the controller's inability to FENCE (act at production time) combined with ledger
  irreversibility -- not public observation per se.

## Feasibility is achievable by several mechanisms; fencing is SUFFICIENT, NOT NECESSARY [PROVEN; MODEL-CHECKED]

The earlier "L(t)<=B for all t IFF fencing" is FALSE. L(t)<=B for all t holds under ANY of:

(M1) PRODUCTION FENCING (Thm 2 below): never bind an unauthorized record to a scope that is
     reconstructible at its production tick.
(M2) ADMISSION REFUSAL keeping scopes non-reconstructible: never deliver a threshold of raw shares
     on a scope to a reached case. Then no scope is ever exposed; L stays 0. [CE-REFUSE, MODEL-CHECKED]
(M3) BUDGET ABSORPTION: B >= total weight of records producible-while-unauthorized under
     reconstructible scopes over the run. Then the breach is within budget. [CE-NEC, MODEL-CHECKED]

So fencing is one SUFFICIENT mechanism, not a necessary condition. The honest headline is a
CHARACTERIZATION, not an iff: WITHOUT some feasibility mechanism (M1/M2/M3), a production-blind
controller in the Theorem-1 regime cannot meet a tight whole-run budget; WITH any of them it can.

## Corrected Theorem 2 (feasibility under an ONGOING fencing invariant) [PROVEN; MODEL-CHECKED]

The earlier Theorem 2 claimed a record produced under a fresh scope "contributes 0 to L forever."
This is FALSE: a LATER grant on that scope makes it reconstructible, and the scope key opens the
record retroactively, even if the grant's range excludes it. [CE-RETRO, MODEL-CHECKED: a grant on
(g,0) with range [1,2) collaterally discloses g:0; and an observability gap lets it past the public
gate.]

Corrected statement. Define the ONGOING FENCING INVARIANT over the whole run: for every record r
under scope sigma and every tick t, IF sigma is reconstructible at t by a case in F, THEN r is
authorized to that case at t (r in the delivering grant's range). Equivalently, two obligations:
  (P-fence)  no unauthorized record is bound to a scope reconstructible at production time;
  (A-fence)  no grant delivery makes a scope reconstructible while it still carries records the
             delivering grant does not authorize (the admission-side check
             production_fence.admission_would_retroactively_disclose must return empty, or the
             collateral must be rotated away first / admitted into the budget).
If the ongoing invariant holds for all t (plus fresh scopes have independent keys, ASSUMED), then
every record contributes 0 collateral, so L(t)=0 for all t (or L(t)<=B_0 for pre-invariant records).

Argument. By (P-fence) no record is opened-while-unauthorized at its production tick. By (A-fence) no
later delivery opens a previously-safe record while unauthorized. Since opening-while-unauthorized is
the only source of ledger growth, L does not grow beyond pre-invariant records. QED, conditional on
closure soundness and independent fresh keys (ASSUMED). MODEL-CHECKED: p3d_fencing_test.py (the
fenced run binds the at-risk record to a fresh scope, actual disclosed weight stays 0; and the
offline case REJECTS production rather than binding under an exposed scope).

Cost/timing (MODEL-CHECKED): fencing consumes rotation ticks and may DEFER/REJECT production when the
owner is offline with no preauthorization; production_fence records rotations, deferrals, rejections
and rotation ticks. The whole-run bound is thus bought with service-availability and latency cost,
not for free.

## Greedy optimality [OBSERVED only; NOT a theorem]

P3C observed greedy == the exact timed optimum on three tiny single-demand instances. This is an
EMPIRICAL OBSERVATION, not a theorem; no general optimality is claimed, and a multi-demand regime
where greedy is sub-optimal is plausible and untested. The independent timed reference establishes
exact optima ONLY for single-demand instances; it is NOT a general multi-demand optimum (Task 4
honesty requirement).

## Consequence for the paper

The contribution is a CHARACTERIZATION: online exposure-budget enforcement for delegated encrypted
data with intermittent owners is impossible for a production-blind controller in the tight-budget,
delayed-report, already-reconstructible regime (Thm 1), and is recoverable by an ongoing fencing
invariant (Thm 2) -- which must be co-designed across the management plane (admission gate) and the
data plane (production fence), and which is one of several sufficient mechanisms, not a necessary
one. The retroactive-disclosure counterexample shows the invariant must be ongoing, spanning future
grants, not a one-time barrier. All of this is model-level and conditional on closure soundness; no
byte-level cryptographic security is claimed (the backend is an abstract usability model).

## Status ledger

- PROVEN (model, conditional on closure soundness): Thm 1 (restricted class); the M1/M2/M3
  sufficiency; Thm 2 under the ongoing invariant.
- MODEL-CHECKED: all three counterexamples; the fence prevents the breach; offline REJECT; the
  admission-side retroactive check.
- ASSUMED: closure soundness (PO1); independent fresh-scope keys; abstract cfrag backend.
- OBSERVED: greedy == optimum on tiny single-demand instances only.
- OPEN: a general multi-demand optimum/regime characterization; a measured (not scripted) arrival/
  reservation workload at scale; real timed PRE backend + verified receipts; full-text SDAC-BBPP and
  adjacent online-admission/privacy-budget literature; submission-grade (vs model-level) proofs.
