"""Legacy proposal interface.

fixed_epoch_policy issues grant METADATA only; despite its historical name it
does not schedule periods or deliver a usable threshold. It is not one of the
five current service-plan comparison methods. proposed_policy is unsupported.
Request.t is descriptive in the decision-index harness, not a release clock.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .manager import Action, ActionKind, Observation
from delegation_model.types import Grant, Scope


@dataclass
class Request:
    """A pending delegation request offered to the controller at time `t`."""
    t: int
    grant: Grant


def fixed_epoch_policy(obs: Observation, req: Optional[Request]) -> Action:
    if req is None:
        return Action(ActionKind.DEFER, reason="no pending request")
    g = req.grant
    if not obs.is_owner_online(g.owner):
        return Action(ActionKind.DEFER, reason="owner offline; defer grant")
    spans = obs.auth.scope_spans.get(g.scope.stream, [])
    if not any(s.scope == g.scope for s in spans):
        return Action(ActionKind.REJECT, reason="requested scope not active")
    return Action(ActionKind.ADMIT_GRANT, grant=g, reason="fixed-epoch admit")


def proposed_policy(obs: Observation, req: Optional[Request]) -> Action:
    # Intentionally not implemented. Do NOT alias a baseline here.
    return Action(ActionKind.UNSUPPORTED,
                  reason="proposed exposure-aware controller not yet implemented")
