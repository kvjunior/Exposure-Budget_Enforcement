"""
Conservative POSSIBLE-knowledge model (review R3/R4).

The online controller does not observe realized corruption. To reason about exposure it must
compute, from OBSERVABLE history plus a PUBLIC coalition specification, an upper bound on what a
coalition COULD have retained. This module does exactly that and nothing else: it never reads
Corrupt*/Disclose* events.

A coalition specification here is a declared set of proxies and recipients the coalition is
PERMITTED to corrupt (its reach). For each such coalition we form the WORST CASE: it retains
every kfrag ever installed to a proxy in its reach, every cfrag ever produced for a grant whose
recipient is in its reach, and the recipient keys in its reach. We then reuse the SAME
conservative closure and exposure functions as the evaluation channel -- the only difference is
the SOURCE of the knowledge (possible, from observations) vs realized (from ground truth).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from .types import Material, Held, Scope, Record, Grant, GrantId, ProxyId, RecipientId
from .events import (Event, GrantIssued, KFragInstalled, CFragProduced, is_observable)
from .authorization import AuthorizationState, fold_authorization
from .closure import CoalitionKnowledge, conservative_closure, exposure, _find_grant


@dataclass
class CoalitionSpec:
    """Public declaration of a coalition's REACH (whom it may corrupt). No realized corruption."""
    label: str
    proxies: Set[ProxyId] = field(default_factory=set)
    recipients: Set[RecipientId] = field(default_factory=set)


def possible_knowledge(events: List[Event], spec: CoalitionSpec,
                       now: Optional[int] = None,
                       auth: Optional[AuthorizationState] = None) -> CoalitionKnowledge:
    """Upper bound on what `spec` COULD retain, from OBSERVABLE events only."""
    if auth is None:
        auth = fold_authorization(events, now)
    K = CoalitionKnowledge(spec.label)
    K.corrupt_proxies = set(spec.proxies)          # "could be corrupt" treated as reach
    K.corrupt_recipients = set(spec.recipients)
    for rcpt in spec.recipients:
        K.held.add(Held(Material.RECIPIENT_SK, recipient=rcpt))
    for e in events:
        if not is_observable(e):
            continue                                # never read realized corruption/disclosure
        if now is not None and e.t > now:
            break
        if isinstance(e, KFragInstalled) and e.proxy in spec.proxies:
            g = _find_grant(events, e.grant_id)
            K.held.add(Held(Material.KFRAG, grant=e.grant_id,
                            scope=(g.scope if g else None), index=e.index))
        elif isinstance(e, CFragProduced):
            g = _find_grant(events, e.grant_id)
            if g is not None and g.recipient in spec.recipients:
                K.held.add(Held(Material.CFRAG, grant=e.grant_id,
                                scope=(g.scope if g else None), index=e.index, record=e.record))
        elif isinstance(e, GrantIssued) and e.grant.recipient in spec.recipients:
            K.authorized_grants.add(e.grant.grant_id)
    return K


def possible_exposure(events: List[Event], spec: CoalitionSpec, now: Optional[int],
                      weights: Dict[Record, float],
                      auth: Optional[AuthorizationState] = None):
    """Conservative exposure a coalition COULD reach, from observable history only."""
    if auth is None:
        auth = fold_authorization(events, now)
    K = possible_knowledge(events, spec, now, auth)
    return exposure(K, events, now, weights, auth)
