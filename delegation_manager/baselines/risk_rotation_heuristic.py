"""
risk_rotation_heuristic (RENAMED from the former 'sacmat_rotation' adaptation; S2 review obs).

WITHDRAWAL: the previous name implied this faithfully reproduces SACMAT 2025's rotation rule. It does
NOT. SACMAT's Section 6 rotation checks are conditioned on LACK OF CURRENT PERMISSION and CACHED-KEY
ACCESS after a revocation/policy change; this heuristic drops those conditions and rotates whenever
the active scope is reconstructible by the declared coalition, even without any revocation. Its extra
rotations are therefore properties of OUR heuristic, not of the published method. All conclusions
about the published SACMAT method are withdrawn. A faithful common-domain SACMAT comparison is left as
future work. This is kept only as one more baseline ("rotate on reconstructibility"), honestly named.
"""
from __future__ import annotations
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.possible import CoalitionSpec, possible_exposure
from delegation_manager.manager import (Action, ActionKind, Observation, PreAuth, check_action)
from delegation_manager.policies import Request
from delegation_manager.candidate_actions import _next_epoch_scope


def _active_scope_reconstructible(obs: Observation, req: Request, family, weights) -> bool:
    """canUserBeCache-analogue: could the declared coalition reconstruct the request's active scope
    key from retained fragments observable so far? (whole-key/threshold via possible_exposure)."""
    sc = req.grant.scope
    for spec in family:
        x = possible_exposure(obs.events, spec, obs.cutoff, weights)
        if any(s == sc for s in x.future_scopes):
            return True
    return False


def risk_rotation_heuristic_policy(obs: Observation, req: Optional[Request], budget, family, weights,
                           preauth: Optional[PreAuth] = None) -> Action:
    """Our reconstructibility-triggered rotation rule plus admission. Rotates when the active scope is
    reconstructible (cached-key-analogue), else admits if authority+budget permit, else defers."""
    preauth = preauth or PreAuth()
    if req is None:
        return Action(ActionKind.DEFER, reason="no request")
    # Heuristic decision: is rotation needed (cached-key-analogue)?
    if _active_scope_reconstructible(obs, req, family, weights):
        sc_next = _next_epoch_scope(obs, req.grant.scope.stream)
        registered = obs.registry.owner_of(req.grant.scope.stream)
        if sc_next is not None and registered is not None and (
                obs.is_owner_online(registered) or preauth.permits_scope(registered, sc_next)):
            next_seq = obs.auth.produced.get(req.grant.scope.stream, 0)
            roll = Action(ActionKind.ACTIVATE_SCOPE, scope=sc_next,
                          new_scope_key_id=f"{sc_next.stream}.e{sc_next.epoch}.k0",
                          start_seq=next_seq, reason="reconstructibility-triggered rotation")
            if check_action(roll, obs, preauth).ok:
                return roll
    # admission (the part SACMAT does not model): admit if authority+budget permit
    g = req.grant
    admit = Action(ActionKind.ADMIT_GRANT, grant=g,
                   authorized_kfrag_indices=tuple(range(g.threshold)),
                   reason="risk-rotation heuristic admit")
    if check_action(admit, obs, preauth, budget, family, weights).ok:
        return admit
    return Action(ActionKind.DEFER, reason="risk-rotation heuristic: admission infeasible")
