"""
Exposure-constraint admission check: the first concrete bridge from the closure model to a
management decision. This is a SOUNDNESS tool for the action checker, not the controller.

Given an action and the declared admissible coalition family, it computes the WORST-CASE
future exposure the action could create if that coalition later retained the material the
action enables, and rejects the action if it would breach the exposure budget.

Key honesty points (brief sec 4.2):
  - The controller/checker does NOT observe realized corruption. It reasons over the DECLARED
    coalition family (here: concrete candidate coalitions passed in), taking the max exposure
    across them -- a conservative representation, not an oracle.
  - Owner-root compromise is excluded: if a candidate coalition holds the owner root (modeled
    as holding every scope key already), we do NOT claim a small bound; such a coalition is
    flagged and the caller decides policy separately.
  - Exposure counts FUTURE collateral records under an exposed ACTIVE scope. Admitting a grant
    on an already-active scope to a recipient who may be in a coalition increases the future
    exposure of that scope; activating a FRESH scope first bounds it.

This check does not decide WHICH action to take; it only vetoes actions that would breach the
budget. The proposed controller (not implemented) will choose among budget-satisfying actions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from delegation_model.events import Event, GrantIssued
from delegation_model.authorization import fold_authorization, AuthorizationState
from delegation_model.closure import accumulate, exposure, CoalitionKnowledge
from delegation_model.types import Record, Scope, Grant
from .manager import Action, ActionKind


@dataclass
class ExposureBudget:
    max_future_scopes: int          # cap on number of simultaneously-exposed active scopes
    max_past_weight: float          # cap on cumulative past collateral weight

    def __post_init__(self):
        import math
        if type(self.max_future_scopes) is not int or self.max_future_scopes < 0:
            raise ValueError("max_future_scopes must be a nonnegative integer")
        if not math.isfinite(self.max_past_weight) or self.max_past_weight < 0:
            raise ValueError("max_past_weight must be finite and nonnegative")


@dataclass
class ExposureVerdict:
    ok: bool
    worst_coalition: Optional[str]
    worst_future_scopes: int
    worst_past: float
    owner_root_coalitions: List[str]
    reason: str
    future_witness: Optional[str] = None   # coalition witnessing the worst future exposure
    past_witness: Optional[str] = None     # coalition witnessing the worst past exposure


def evaluate_exposure(events: List[Event], cutoff: int,
                      coalition_labels: List[str],
                      budget: ExposureBudget,
                      weights: Dict[Record, float],
                      owner_root_labels: Optional[List[str]] = None) -> ExposureVerdict:
    """Evaluate current exposure across the declared coalition family at `cutoff`.

    `events` MUST include the ground-truth compromise events for the coalitions being modeled
    (this is an evaluation/soundness tool, not a controller input). The controller's own policy
    never sees these; see docs/decisions/0003_controller_information.md.
    """
    owner_root_labels = owner_root_labels or []
    auth = fold_authorization(events, cutoff)
    # review R2: take COORDINATE-WISE maxima; each dimension may have a DIFFERENT witness
    # coalition. We must check every dimension for every coalition, not pick one coalition
    # lexicographically and test both constraints on it.
    worst_future = 0
    worst_future_label = None
    worst_past = 0.0
    worst_past_label = None
    root_hits = []
    for label in coalition_labels:
        if label in owner_root_labels:
            root_hits.append(label)       # excluded from small-bound claims
            continue
        K = accumulate(events, label, cutoff, auth)
        x = exposure(K, events, cutoff, weights, auth)
        if len(x.future_scopes) > worst_future:
            worst_future = len(x.future_scopes); worst_future_label = label
        if x.past > worst_past:
            worst_past = x.past; worst_past_label = label
    future_ok = worst_future <= budget.max_future_scopes
    past_ok = worst_past <= budget.max_past_weight
    ok = future_ok and past_ok
    breaches = []
    if not future_ok:
        breaches.append(f"future_scopes={worst_future}>{budget.max_future_scopes} "
                        f"(witness {worst_future_label})")
    if not past_ok:
        breaches.append(f"past={worst_past}>{budget.max_past_weight} "
                        f"(witness {worst_past_label})")
    reason = ("within budget" if ok else "exposure breach: " + "; ".join(breaches))
    if root_hits:
        reason += f"; owner-root coalitions excluded from bound: {root_hits}"
    # worst_coalition kept for back-compat: the future-dimension witness if any, else past.
    worst_label = worst_future_label or worst_past_label
    return ExposureVerdict(ok=ok, worst_coalition=worst_label,
                           worst_future_scopes=worst_future, worst_past=worst_past,
                           owner_root_coalitions=root_hits, reason=reason,
                           future_witness=worst_future_label, past_witness=worst_past_label)
