"""Bounded canonical action choices for the current request sequence.

Enumerates defer/reject, every fragment-delivery subset of the offered grant
(including metadata, partial and above-threshold delivery), and the request
stream's next-epoch rollover. Delivery domain size is checked before subset
construction. Authority is checked now; exposure is checked by the gate.
The service-plan grammar is enforced separately in plan_contract.py.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from delegation_model.types import Grant, Scope
from .manager import Action, ActionKind, Observation, PreAuth
from .policies import Request


def _next_epoch_scope(obs: Observation, stream: str) -> Optional[Scope]:
    spans = obs.auth.scope_spans.get(stream, [])
    if not spans:
        return None
    max_epoch = max(s.scope.epoch for s in spans)
    return Scope(stream, max_epoch + 1)


def enumerate_actions(obs: Observation, req: Optional[Request],
                      preauth: Optional[PreAuth] = None,
                      max_delivery_choices: int = 20) -> List[Action]:
    preauth = preauth or PreAuth()
    actions: List[Action] = [Action(ActionKind.DEFER, reason="enumerated"),
                             Action(ActionKind.REJECT, reason="enumerated")]
    if req is not None:
        g = req.grant
        registered = obs.registry.owner_of(g.scope.stream)
        scope_active = any(s.scope == g.scope for s in obs.auth.scope_spans.get(g.scope.stream, []))
        # All delivery subsets are legal, including metadata-only and partial
        # admissions. They may change historical authorization despite being
        # unserved, so no subset is silently discarded as dominated.
        # For an
        # online admission, authority is the owner being online; for an offline admission, a grant
        # token must authorize the specific indices. A bounded limit refuses explicitly if the
        # branching is too large (rather than silently omitting legal actions).
        from itertools import combinations
        online = (registered == g.owner and obs.is_owner_online(registered))
        if type(max_delivery_choices) is not int or max_delivery_choices < 1:
            raise ValueError("max_delivery_choices must be a positive integer")
        # Compare bit lengths BEFORE constructing 2**shares or its subsets.
        # This refuses even very large share counts without a huge allocation.
        if g.shares >= max_delivery_choices.bit_length():
            raise ValueError(f"delivery-choice branching 2**{g.shares} exceeds "
                             f"max_delivery_choices {max_delivery_choices}; refuse rather than omit")
        all_delivery_choices = (idx for k in range(g.shares + 1)
                                for idx in combinations(range(g.shares), k))
        if scope_active:
            for idx in all_delivery_choices:
                idx = tuple(idx)
                token_ok = (registered == g.owner and not obs.is_owner_online(registered)
                            and preauth.permits_grant(g, idx, obs.cutoff))
                if online or token_ok:
                    actions.append(Action(ActionKind.ADMIT_GRANT, grant=g,
                                          authorized_kfrag_indices=idx,
                                          reason="enumerated admit" + (" (token)" if token_ok else "")
                                                 + f" indices={idx}"))
        # a fresh rollover of the request's stream (bounds future exposure of the old scope)
        sc_next = _next_epoch_scope(obs, g.scope.stream)
        if sc_next is not None and registered is not None:
            next_seq = obs.auth.produced.get(g.scope.stream, 0)
            key_id = f"{g.scope.stream}.e{sc_next.epoch}.k0"
            if obs.is_owner_online(registered) or preauth.permits_scope(registered, sc_next):
                actions.append(Action(ActionKind.ACTIVATE_SCOPE, scope=sc_next,
                                      new_scope_key_id=key_id, start_seq=next_seq,
                                      reason="enumerated rollover"))
    return actions
