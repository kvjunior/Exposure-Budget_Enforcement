# Authoritative model-level security statement — full-horizon corrected evaluation

This supersedes `docs/proofs_p3e.md` and all earlier spine/proof drafts when describing the current model.
The manuscript's Section V is the presentation form. These are **conditional model theorems**, NOT
cryptographic reductions or machine-checked proofs.

## State and trust conditions

- A record is produced under exactly one scope at its production time. Each owner-issued new epoch
  has a fresh, independent key (assumed; not derived from abstract identifiers).
- Potential opening is computed for each exact declared coalition recipient subset, with retained
  raw fragments, mixed cfrags, and available recipient credentials. Soundness as an abstraction of
  real threshold PRE is a separate assumption, not inferred from a simulator test.
- `authorized_ever` defines the historical authorization relation. This is NOT an instantaneous
  revocation confidentiality property. The cumulative ledger counts first events where a record
  becomes potentially openable outside that historical authorization; entries never disappear.
- The actual-state enforcement boundary is trusted to see all source productions and commits.
  Source production is either fenced into a fresh scope (if feasible) or dropped. Capabilities can
  only be introduced at checked install/delivery commits; no out-of-band key release is allowed.
- The simulator's atomic transition order is assumed. Production-check and commit cannot race.
  Distributed transactional correctness is not established by this artifact.

## Restricted impossibility

At a state with an already-reconstructible scope and insufficient remaining disclosure allowance,
if unauthorized production is allowed under that scope without a production barrier, and its
report is delayed, the public-log-only controller cannot *react to that report* before disclosure.
This is NOT an impossibility for policies that refuse the grant initially, use preemptive scope
rotation, control production, or have adequate remaining budget.

## Conditional whole-run preservation (inductive argument)

Base: actual per-coalition ledgers initially lie within B. For each environment event, either:
(i) it has no new opening capability, (ii) a source production is dropped/placed under a fresh
non-reconstructible scope by the fence, or (iii) a grant/capability event undergoes actual-state
candidate evaluation and is refused if any cumulative ledger would exceed B. With the complete-
mediation, freshness, and closure assumptions, no transition violates B. Historic entries remain.
A **positive** B can have nonzero disclosure; zero disclosure is only forced when B=0 and the
initial ledger is empty. Fencing is sufficient in this combined mechanism but NOT universally
necessary: refusing all potentially reconstructible grants and sufficiently large B are examples.

## Model and empirical boundaries

- No generalized theorem that greedy admission is optimal. The two-demand oracle has a counterexample.
- No claim that the combined mechanism maximizes service or always costs more or less.
- Tests check the model implementation and event accounting; they do not establish assumptions
  about actual cryptographic bytes or deployment trust boundaries.
- All 900 scenario/policy runs are from 90 distinct workload traces crossed with 2 budgets,
  5 policies; the 30 seeds are paired across policies. One owner, 4 streams, 2 recipients,
  3 proxies, threshold 2. Results are descriptive simulation observations.
