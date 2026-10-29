> OBSOLETE (P3B). SUPERSEDED by docs/dichotomy_spine_p3d.md (corrected in P3D) and
> docs/proofs_p3e.md (P3E). Retained only for history. Do NOT cite its Theorem 1/2 or the "iff".

# The exposure-budget dichotomy (paper spine)

This is the central theoretical statement the paper is built around. It characterizes EXACTLY
when an online exposure gate can and cannot guarantee a whole-run cumulative-disclosure budget in
an encrypted delegated-data service with intermittent owners. Both sides are witnessed by
executable model traces already in the codebase (the P3B pilot), so the claim is grounded, not
asserted. Theorems are stated as reviewable arguments over the finite model, not machine-checked
proofs; cryptographic closure soundness is ASSUMED (PO1), as elsewhere.

## Why this is the spine (not a controller)

Three results stand from the review history, and this statement turns all three from liabilities
into a single characterization:

1. The proposed controller (EARP) is provably equal to greedy under positive rollover cost — there
   is no clever-controller contribution to claim.
2. Greedy already achieves the exact offline optimum on the tested instances — so "our controller
   beats baselines" is false by construction.
3. The P3B pilot implements a counterexample in which the online gate CANNOT bound cumulative
   disclosure when production is delayed/unbounded.

Rather than hide (1)-(3), the paper's contribution is the DICHOTOMY they jointly imply: an online
admission gate is necessary but NOT sufficient for a whole-run disclosure bound; sufficiency
requires a data-plane production-fencing primitive. Greedy's optimality and EARP's collapse then
become positive statements about the feasible regime. This is a service-management argument (the
management plane needs a data-plane barrier), which fits TNSM, not a new primitive or a pure
impossibility result.

## Model (finite, as implemented)

- Discrete logical time (ticks). A stream g with key scopes sigma = (g, epoch). Records r = (g, seq)
  are PRODUCED at ticks; production time t_p(r) is a data-plane event.
- Owner O (intermittently online); a PUBLIC declared coalition family F. A coalition C in F may
  retain cryptographic material (threshold-PRE raw shares, cfrags, recipient keys).
- Reconstructibility: C RECONSTRUCTS scope sigma at tick t if, from material retained by t, the
  conservative closure recovers sigma's key (e.g., t raw shares of a grant on sigma + the recipient
  key). "sigma is reconstructible at t" means some C in F reconstructs it at t.
- Disclosure: record r is DISCLOSED to C at the first tick at which C can open r while r is NOT
  authorized to C. The cumulative disclosure ledger L(t) is the weighted set of records disclosed by
  t. L is MONOTONE non-decreasing and irreversible (established as T3 in p3b_proof_obligations.md):
  later grants, revocation or rotation never remove a ledger entry.
- Budget: a bound B on cumulative disclosure weight. The guarantee of interest is L(t) <= B for ALL
  t (a WHOLE-RUN bound), not merely at the observation cutoff.

## Information model (the crux)

The ONLINE GATE (the management-plane controller) chooses actions (ADMIT / DEFER / ROTATE) as a
function of the PUBLIC OBSERVATION only: the public log prefix available at the current tick. A
record produced at tick t_p has its PUBLIC REPORT available only at tick t_r(r) >= t_p. The
production-to-report delay delta(r) = t_r(r) - t_p(r) is a data-plane property; the gate does not
learn of r before t_r(r), and delta is not bounded by anything the gate knows at t_p. Private
production does not advance the public revision (established as T4, causal public prefix).

This is the whole game: the gate acts on DELAYED, PUBLIC information, while disclosure is
INSTANTANEOUS and IRREVERSIBLE at production time under an exposed scope.

## Theorem 1 (impossibility under delayed/unbounded production)

Suppose at some tick t* a scope sigma is reconstructible by some C in F (C holds enough retained
material). Suppose the data plane may produce a new record r under sigma at any tick t_p >= t*,
with public report delay delta(r) >= 1, and r is not authorized to C. Then NO online gate
restricted to the public log can guarantee L(t) <= B for any B < w_min, where w_min is the minimum
record weight.

Argument. C reconstructs sigma at t* and r is produced under sigma at t_p; since C holds sigma's
key and r is unauthorized to C, r is DISCLOSED to C at t_p, so L(t_p) >= w_min. The gate's first
information about r is its public report at t_r = t_p + delta > t_p. Any gate action at or after
t_r (rotation, revocation) cannot reduce L because L is irreversible. The gate has no public signal
distinguishing the breaching run from a non-breaching one before t_p, so no public-log policy can
act in time. Hence L exceeds B = w_min - epsilon on this run, for every online gate. QED (model).

EXECUTABLE WITNESS: P3B pilot trace `delayed_production_breach_then_mitigation`. A threshold-2
grant on scope (g,0) is installed; its two raw shares make (g,0) reconstructible. Record g:1 is
produced under (g,0) at tick 4; its public report is available only at tick 8. The run asserts
`max actual disclosed_weight == 1` while the observable ledger stays 0 until tick 8. Rotation after
tick 8 retires the scope but cannot repair the disclosure.

Interpretation. The limit is INFORMATION-STRUCTURAL (observability + irreversibility), not
computational. An online admission/rotation gate, however clever, is INSUFFICIENT for a whole-run
disclosure bound when production under an exposed scope can precede its public report.

## Theorem 2 (feasibility under production fencing)

Define the FENCING condition: for every production of a record r under a scope sigma at tick t_p, if
sigma is reconstructible by some C in F at t_p, then the data plane interposes a ROTATION to a fresh
scope sigma' before t_p, binding r to sigma' instead, where sigma' is reconstructible by no C in F
at t_p (fresh independent key, no retained share). Equivalently: no record is produced under a
reconstructible scope; a rotation barrier precedes any such production.

Under the fencing condition (plus A1's independent fresh-key assumption), the online rotate-before-
produce gate maintains L(t) <= B_0 for all t, where B_0 is the disclosure already incurred by
records that were authorized-or-produced before fencing began. In particular, if fencing holds from
the start, L(t) = 0 for all t (no collateral disclosure).

Argument. Consider any record r produced after fencing begins. By the condition, r is bound to a
fresh sigma' reconstructible by no C in F at t_p(r); no C can open r at t_p(r), and (fresh key, no
new retained share for sigma') no C reconstructs sigma' at any later tick without a NEW grant, which
the gate gates. Hence r is never disclosed to any C in F, and contributes 0 to L. Records before
fencing contribute at most B_0 (fixed). L is monotone, so L(t) <= B_0 for all t. QED (model).

EXECUTABLE WITNESS: P3B pilot trace `rotation_before_production_keeps_old_target_usable`. Rotation
is interposed before the tick-5 production of g:1, binding g:1 to a fresh scope; the run asserts
`max actual disclosed_weight == 0`, AND the originally requested target on the old scope remains
usable (demand is preserved across the rotation).

Interpretation. The whole-run bound is RECOVERABLE, but only by a DATA-PLANE primitive (a production
barrier / rotation interposition), not by the management gate alone. The gate decides WHEN to rotate;
the fence guarantees production cannot slip under an exposed scope between decision and effect.

## The dichotomy (paper's headline)

Online exposure-aware admission is NECESSARY but NOT SUFFICIENT for a whole-run cumulative-disclosure
bound. Sufficiency holds IFF the data plane provides production fencing (Theorem 2); without it, no
online gate suffices (Theorem 1). The management-plane controller and the data-plane fence must be
CO-DESIGNED. Inside the feasible (fenced) regime, the admission problem is well posed, and a simple
greedy admit/rotate policy attains the exact offline optimum on the studied instances (so no
elaborate controller is needed or claimed); outside it, the budget is unachievable by any online
policy.

## What is proven, assumed, open

- PROVEN (model-level arguments + executable witnesses): Theorems 1 and 2 over the finite model, each
  with a runnable trace that already passes.
- ASSUMED: PO1 cryptographic closure soundness; A1 independent fresh keys behind fresh scope IDs;
  the abstract cfrag-usability backend (not real PRE). These bound the claims to the model.
- PARTLY CLOSED by P3C: (i) the TIMED oracle + an independent replay reference now EXIST
  (delegation_manager/timed_oracle.py, tests/differential/timed_independent_reference.py) and produce
  gap-to-optimum evidence INSIDE the feasible regime (results/manifests/p3c_timed_oracle.json):
  greedy attains the optimum, blind rotation does not. See docs/CHANGELOG_p3c.md.
- STILL OPEN: (ii) a precise arrival/
  reservation model making "fencing" a concrete, measurable mechanism rather than a scripted barrier;
  (iii) whether greedy's optimality generalizes beyond the small instances (a regime characterization,
  not just examples); (iv) the full-text SDAC-BBPP (TNSM 2024) read and the adjacent online-admission/
  privacy-budget literature, to defend the framing against "this is just online admission control."

## Paper outline implied by this spine

1. Problem: exposure-aware delegation admission in an encrypted data service with intermittent owners.
2. Model and exposure semantics (closure, three distinct quantities, the disclosure ledger).
3. The DICHOTOMY (Theorems 1-2) — the contribution. Online gate necessary-not-sufficient; fencing
   is the exact feasibility condition. Co-design message.
4. Admission inside the feasible regime: exact offline oracle, greedy optimality, blind-rotation
   sub-optimality (characterization, honest about EARP = greedy).
5. Evaluation: timed pilot with gap-to-optimum INSIDE the feasible regime; fencing cost.
6. Limits and scope: outside the feasible regime; abstract backend; owner-root; novelty caveats.
