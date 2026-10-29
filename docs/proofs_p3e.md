> HISTORICAL: This P3E proof draft predates the full-horizon evaluation. Use `docs/PROOFS_FULL_HORIZON.md` and `paper/main.tex` for current scoped statements.

> NOTE (P3F): still authoritative; Thm 3 corrected per reviewer A6 (budget invariant vs zero-disclosure).
# P3E — submission-quality theorems, assumptions, and proofs (authoritative)

This is the single authoritative scientific specification. It supersedes the P3B spine (OBSOLETE)
and consolidates the P3D corrections with the P3E enforcement result. All statements are MODEL-LEVEL
and CONDITIONAL on closure soundness (A1); none claims byte-level cryptographic security.

## Model and assumptions

Discrete service ticks. Stream g; scopes sigma=(g,epoch); a scope is ACTIVE iff no higher epoch
exists. Records r bound to the active scope at production. Declared PUBLIC coalition family F.
- A1 (closure soundness, ASSUMED): a coalition holding >= threshold raw shares of a grant on sigma
  (to reached proxies) can compute sigma's key and open EVERY record under sigma. Authorization is
  range-limited; opened-minus-authorized = collateral.
- A2 (irreversibility): the disclosure ledger L(t) is monotone; no action removes an entry.
- A3 (information): the ONLINE CONTROLLER sees only the public view (reports at available_at >=
  occurred_at); the ENFORCEMENT BOUNDARY (co-located with production/commit) sees actual state.
- A4 (authority): grants/activations require the owner online or a valid preauthorization.
- A5 (independent fresh keys, ASSUMED): a freshly activated scope's key is independent (no retained
  share grants reconstructibility without a new grant).
Adversary/environment controls owner availability and, unless fenced, production timing/binding.

## Theorem 1 (restricted impossibility) [PROVEN, conditional; MODEL-CHECKED]
For a PRODUCTION-BLIND online controller restricted to the public log, if a reachable state has a
scope sigma reconstructible by a case in F, an unauthorized record may be produced under sigma with
report delay >= 1, and the budget B < w_min, then the controller cannot guarantee L(t) <= B.
Proof: the record is disclosed at production (A1), L jumps >= w_min > B (A2); the controller learns
only at report time and cannot repair (A2); before production the public view is uninformative (A3).
QED. Witness: p3d_counterexamples.CE-RETRO-style unfenced breach. NOT universal: controllers with
fencing (Thm 2), admission refusal (Cor 1(M2)), or sufficient budget (Cor 1(M3)) escape it.

## Corollary 1 (sufficiency; fencing NOT necessary) [PROVEN; MODEL-CHECKED]
L(t)<=B for all t holds under ANY of: (M1) ongoing fencing (Thm 2); (M2) admission refusal keeping
every scope non-reconstructible; (M3) B >= total producible unauthorized weight under reconstructible
scopes. Hence fencing is sufficient, not necessary. Witnesses: CE-REFUSE (M2), CE-NEC (M3).

## Theorem 2 (feasibility under the ONGOING invariant) [PROVEN, conditional; MODEL-CHECKED]
Define the ONGOING INVARIANT: for every record r under sigma and every tick t, if sigma is
reconstructible by a case in F at t, then r is authorized to that case at t. Equivalently:
(P-fence) no unauthorized record is bound to a scope reconstructible at production time, AND
(A-fence) no grant delivery makes a scope reconstructible while it carries records that delivery does
not authorize. If the invariant holds for all t (with A1, A5), then no record is ever opened-while-
unauthorized, so L(t)=0 for all t (or <= B_0 for pre-invariant records). For a POSITIVE budget B, the weaker
operative guarantee enforced in code is L(t) <= B for all t (budget invariant); the zero-disclosure
A-fence is the B=0 instance.
Proof: opening-while-unauthorized is the only source of ledger growth (A1, def. of collateral); the
two clauses forbid it at production and at every later delivery; by A2 L never grows. QED.
Witnesses: p3d_fencing_test (P-fence prevents the breach; offline REJECT), p3e_enforcement_test
(A-fence: the enforcement boundary refuses retroactively-disclosing deliveries across all paths).

## Theorem 3 (enforcement realizes A-fence) [MODEL-CHECKED; code invariant]
The simulator's enforcement boundary _enforce, evaluated on ACTUAL state at every capability-changing
commit (grant-metadata, raw-delivery, cfrag-delivery), refuses any commit that would raise actual
disclosed_weight above B, atomically with the candidate (no TOCTOU). Therefore every committed run
satisfies the BUDGET INVARIANT actual disclosed_weight <= B whole-run. The ZERO-DISCLOSURE A-fence
(L(t)=0) is the SPECIAL CASE B=0; for B>0 the implementation permits up to B weighted collateral and
maintains that bound -- it does NOT claim zero disclosure. (Correction per reviewer A6: enforcing
<=B is the budget invariant, not the zero-disclosure invariant; they coincide only at B=0.) This
holds EVEN WHEN the public gate cannot see the collateral (delayed reports), and is verified by
p3e_enforcement_test (RETRO, MULTI-CASE, BOUNDARY, FAILSAFE, RETAINED), not a cryptographic theorem.

## Proposition 4 (security/availability/cost trade-off) [EXPERIMENTALLY OBSERVED]
Over 30 seeds x 3 configs (p3e_workload_eval): the fully-safe policy (greedy_full) has zero budget
violations and zero actual disclosure but LOWER service than the unsafe baselines; production-only
fencing WITHOUT admission enforcement violates the budget like the unfenced baseline on admission-side
disclosure. This quantifies the cost of safety and the insufficiency of production-only fencing. It
is an experimental observation on the model, not a theorem.

## Greedy optimality [OBSERVED + COUNTEREXAMPLE; NOT a theorem]
Greedy == exact timed optimum on the tested feasible single/2-demand instances (timed_oracle_test,
p3e_multidemand_oracle_test MD-ORACLE). But greedy is NOT universally optimal: on an unservable demand
it wastes fragments while the oracle rejects (MD-GREEDY-CE: greedy 14 > oracle 10). No general
greedy-optimality is claimed; gap-to-optimum is reported only where the exact oracle optimum is
established (single and 2-demand instances); the independent reference remains single-demand.

## Status ledger
PROVEN (conditional on A1): Thm 1, Cor 1, Thm 2.
MODEL-CHECKED: all counterexamples; Thm 3 enforcement invariant across all paths; fence + oracle.
TESTED: full P3B/P3C/P3D/P3E regression incl. real HPKE and Umbral suites.
ASSUMED: A1 closure soundness; A5 independent fresh keys; abstract cfrag backend; process-local
receipts.
EXPERIMENTALLY OBSERVED: Prop 4 trade-off; greedy==optimum on tested instances.
OPEN: general multi-demand optimum/regime; a staggered-arrival/queue workload (current generator
releases demands at t=0, a documented simplification); real timed PRE backend + verified receipts;
submission-grade (machine-checked) proofs; full systematic TNSM ToC sweep; SDAC-BBPP full text.
