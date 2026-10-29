# PO2 — conditional admission-endpoint statement, Slice 2.2.1

This is a model argument, not a new cryptographic theorem or a whole-run guarantee.

Let H be a valid observable prefix at logical cutoff u. Define I(H) as the two
budget bounds over every checked exact-recipient case: endpoint collateral
weight and the count of recovered ACTIVE scopes. These are different from the
irreversible first-disclosure ledger, which is an evaluation quantity.

## Assumptions

1. Closure soundness (PO1) is assumed. Real Umbral witnesses support capability
   rules but do not provide a written reduction or proof for the entire model.
2. Every permitted actual endpoint coalition has an evaluated case with exactly
   its recipient set and a superset of its proxy reach. Owner-root compromise
   and arbitrary direct key/plaintext disclosures are outside this small bound.
3. Inputs and authority/preauthorization are authentic-assumed; only observable
   prefix events are used. No signature service is implemented here.
4. H is valid and I(H) initially holds. Weights are finite and nonnegative.
5. Execution commits exactly the checked event plan at u+1 onward, using the
   same log, cutoff, action and authority/exposure context.

## Fixed-recipient coverage

Collateral is not monotone when adding recipients, because their authorization
exemption grows. The checker therefore expands recipient subsets, including
the empty set. For a fixed recipient set R and proxy sets P1 subset P2, possible
material only increases. The model's positive closure rules preserve inclusion;
the historical authorization exemption is identical for the two cases. Set
subtraction and nonnegative weights preserve the collateral inequality. Recovered
scope keys are also included, and intersecting with a fixed H's active scopes
preserves future-count inclusion. This justifies the proxy upper bound, given
sound closure. It does not prove that a real adversary fits the chosen family.
Expansion costs 2^|R| per declared entry; no scalable representation is claimed.

## Conditional statement and argument

For an ADMIT with nonempty delivery indices, if the checker returns ok and the
matching checked plan is committed under assumption 5, its resulting endpoint
satisfies I. The checker evaluates H plus precisely GrantIssued and the proposed
KFragInstalled events, at the canonical timestamps. It takes coordinate-wise
maxima over all expanded cases and returns ok only within both limits. Committing
that same post-history gives the same endpoint values; coverage and closure
soundness extend the bound to each covered actual endpoint coalition.

A metadata-only admission delivers no fragment, changes neither records nor
active scope, and can only add historical authorization. Under the valid initial
invariant and historical-authorization semantics it cannot increase these
endpoint dimensions. It still changes later feasible decisions and is not
discarded by the oracle as irrelevant.

## Implementation evidence for assumption 5

approve() reconstructs the observable prefix, requires event start u+1 and runs
the checker. The receipt binds the prefix digest/version, cutoff, complete
action, preauth-inclusive config and exact events/effects. execute() rejects a
changed binding, rebuilds current observation, reruns the checker and compares
the canonical plan before applying it. Refused/stale commits deliver nothing.
The reviewed 100/101 override is rejected, and an idle logical cutoff 10 produces
events 11/12 rather than using an old last-event time. See the contract tests.
This is a process-local reference property; durable concurrent outbox release
requires a future service protocol and a separate argument.

## Non-extensions

This only states an ADMIT endpoint property. It does not bound intermediate or
irreversible disclosure, unchecked record production, adaptive coalition histories,
or whole-run service feasibility. A later legitimate grant can reduce endpoint
collateral while the irreversible ledger retains earlier disclosure. Unmediated
production under an exposed active scope can breach a finite past budget. Timed
outages, queues, deadlines and production mediation are not implemented by this
decision-index release. No optimizer can repair already disclosed plaintext.
