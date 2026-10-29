"""Declared nonnegative management costs, not measured performance.

For a pending request: defer/reject=M, rollover=M+R, admission=k*C plus M
when k<threshold. A legal plan has at most one fresh-grant admission, so this
centralizes the preexisting partial-completion miss without double charging.
Rollover's opportunity cost persists even if a later admission serves the
request; service counts and total cost are therefore reported separately.
"""
from __future__ import annotations
from dataclasses import dataclass
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from .manager import Action, ActionKind


@dataclass(frozen=True)
class CostWeights:
    miss_penalty: float = 10.0        # cost of not serving a legitimate request this step
    rollover_cost: float = 3.0        # cost of a fresh scope activation (keygen + redistribute)
    per_fragment_cost: float = 1.0    # cost per kfrag installed

    def __post_init__(self):
        import math
        if any(not math.isfinite(v) or v < 0 for v in
               (self.miss_penalty, self.rollover_cost, self.per_fragment_cost)):
            raise ValueError("cost weights must be finite and nonnegative")


def action_cost(action: Action, w: CostWeights = CostWeights(),
                request_present: bool = True) -> float:
    """Per-step cost of an action given whether a legitimate request is pending."""
    if action.kind == ActionKind.ADMIT_GRANT:
        # Each legal plan contains at most one fresh-grant admission. Moving
        # the existing partial-completion miss here gives policy scoring,
        # oracle and replay identical arithmetic without double charging.
        indices = set(action.authorized_kfrag_indices)
        partial = action.grant is not None and len(indices) < action.grant.threshold
        return (w.per_fragment_cost * len(action.authorized_kfrag_indices)
                + (w.miss_penalty if request_present and partial else 0.0))
    if action.kind == ActionKind.ACTIVATE_SCOPE:
        # a rollover does not itself serve the request; if a request was pending it is still a miss
        return w.rollover_cost + (w.miss_penalty if request_present else 0.0)
    if action.kind in (ActionKind.DEFER, ActionKind.REJECT, ActionKind.UNSUPPORTED):
        return w.miss_penalty if request_present else 0.0
    return 0.0
