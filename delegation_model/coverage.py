"""
Coalition coverage contract (S2-01 repair).

The review's counterexample: for a history H and coalitions C1 subset C2 that differ only by adding
a recipient, collateral exposure D(H,C) = Openable(H,C) \\ HistoricallyAuthorized(H,C) is NOT monotone
in C, because the larger recipient set also enlarges the authorization exemption. So
"every actual coalition is contained in some declared reach" does NOT upper-bound collateral.

Correct contract (per FAMILY_BOUND_REPAIR.md): to bound every permitted actual endpoint coalition
(R_actual, P_actual), require, for each, a CHECKED case with R_exact = R_actual and
P_actual subset P_upper. I.e. the recipient set must be fixed EXACTLY; only proxy reach may be
over-approximated. The conditional fixed-recipient monotonicity lemma (docs) justifies
over-approximating proxies once the recipient set is fixed.

This module expands a declared family (whose CoalitionSpec may name a recipient SET that the
adversary could realize as any subset) into the set of exact-recipient cases that must be checked.
For each declared spec with recipient set R, we generate one case PER NON-EMPTY SUBSET of R, each
keeping the spec's full proxy reach as the proxy upper bound. Taking coordinate-wise maxima over
these exact-recipient cases bounds every permitted actual endpoint coalition the family describes.

Caveat (documented, not hidden): enumerating all non-empty recipient subsets is exponential in |R|.
For the small instances here |R| is tiny. A reach specification that means "exactly this recipient
set, not its subsets" can set `recipients_are_exact=True` to skip expansion; the default expands,
which is the sound choice for "the adversary may corrupt ANY subset of these recipients".
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import List, Set
from .possible import CoalitionSpec


def exact_recipient_cases(spec: CoalitionSpec, recipients_are_exact: bool = False
                          ) -> List[CoalitionSpec]:
    """Expand one declared spec into the exact-recipient cases that must be checked.

    If recipients_are_exact: the spec already names the exact recipient coalition -> return [spec].
    Else: the spec's recipient set is the set the adversary MAY corrupt; return one case per
    non-empty subset, each with R fixed exactly and the spec's full proxy reach as P_upper.
    Also include the empty-recipient case (proxies only, no recipient key) because a coalition may
    hold fragments without any recipient secret (it opens nothing via R2 but this keeps coverage
    explicit)."""
    if recipients_are_exact:
        return [spec]
    rs = sorted(spec.recipients)
    cases: List[CoalitionSpec] = []
    # empty recipient set (fragments only)
    cases.append(CoalitionSpec(f"{spec.label}|R=∅", proxies=set(spec.proxies), recipients=set()))
    for k in range(1, len(rs) + 1):
        for combo in combinations(rs, k):
            label = f"{spec.label}|R={{{','.join(combo)}}}"
            cases.append(CoalitionSpec(label, proxies=set(spec.proxies), recipients=set(combo)))
    return cases


def expand_family(family: List[CoalitionSpec], recipients_are_exact: bool = False
                  ) -> List[CoalitionSpec]:
    """Expand a whole declared family into the exact-recipient cases to check (deduplicated by
    (recipients, proxies))."""
    out: List[CoalitionSpec] = []
    seen: Set = set()
    for spec in family:
        for c in exact_recipient_cases(spec, recipients_are_exact):
            key = (frozenset(c.recipients), frozenset(c.proxies))
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out
