"""
Fixed-period rollover baseline (P2).

Exposure-BLIND scheduler: it rolls a fresh scope every `period` admitted grants (or every
`period` steps), and otherwise admits a pending request when authority permits, else defers. It
never consults the exposure budget to decide. This is the control representing "ordinary rotation"
that the research guide asks us to test as a possible sufficient method.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_manager.manager import Action, ActionKind, Observation, PreAuth, check_action
from delegation_manager.policies import Request
from delegation_manager.candidate_actions import enumerate_actions, _next_epoch_scope


@dataclass
class FixedPeriodState:
    period: int
    admits_since_roll: int = 0


def fixed_period_policy(obs: Observation, req: Optional[Request], state: FixedPeriodState,
                        preauth: Optional[PreAuth] = None) -> Action:
    preauth = preauth or PreAuth()
    # time to roll?
    if req is not None and state.admits_since_roll >= state.period:
        sc_next = _next_epoch_scope(obs, req.grant.scope.stream)
        registered = obs.registry.owner_of(req.grant.scope.stream)
        if sc_next is not None and registered is not None and (
                obs.is_owner_online(registered) or preauth.permits_scope(registered, sc_next)):
            next_seq = obs.auth.produced.get(req.grant.scope.stream, 0)
            state.admits_since_roll = 0
            return Action(ActionKind.ACTIVATE_SCOPE, scope=sc_next,
                          new_scope_key_id=f"{sc_next.stream}.e{sc_next.epoch}.k0",
                          start_seq=next_seq, reason="fixed-period rollover")
    if req is None:
        return Action(ActionKind.DEFER, reason="no request")
    g = req.grant
    registered = obs.registry.owner_of(g.scope.stream)
    scope_active = any(s.scope == g.scope for s in obs.auth.scope_spans.get(g.scope.stream, []))
    if registered == g.owner and obs.is_owner_online(registered) and scope_active:
        state.admits_since_roll += 1
        return Action(ActionKind.ADMIT_GRANT, grant=g,
                      authorized_kfrag_indices=tuple(range(g.threshold)),
                      reason="fixed-period admit")
    return Action(ActionKind.DEFER, reason="authority not available")
