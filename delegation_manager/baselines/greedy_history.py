"""Causal minimum-single-action-cost baseline over observable history.

Includes metadata/partial operations at their actual miss-inclusive costs.
It sees public coalition reach and authentic-assumed authority, never realized
corruption or future demand. No novel controller or optimality claim is made.
"""
from __future__ import annotations
from typing import List, Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_manager.manager import Action, ActionKind, Observation, PreAuth, check_action
from delegation_manager.policies import Request
from delegation_manager.candidate_actions import enumerate_actions
from delegation_manager.cost_model import action_cost, CostWeights

# deterministic tie-break preference (lower = preferred)
_PREF = {ActionKind.ADMIT_GRANT: 0, ActionKind.ACTIVATE_SCOPE: 1,
         ActionKind.DEFER: 2, ActionKind.REJECT: 3}


def greedy_history_policy(obs: Observation, req: Optional[Request], budget, family,
                          weights, preauth: Optional[PreAuth] = None,
                          cost_weights: CostWeights = CostWeights(),
                          max_delivery_choices: int = 20) -> Action:
    preauth = preauth or PreAuth()
    candidates = enumerate_actions(obs, req, preauth, max_delivery_choices=max_delivery_choices)
    feasible = []
    for a in candidates:
        res = check_action(a, obs, preauth, budget, family, weights)
        if res.ok:
            feasible.append((action_cost(a, cost_weights, req is not None),
                             _PREF.get(a.kind, 9), a))
    if not feasible:
        # nothing feasible within budget -> defer (never violate the budget)
        return Action(ActionKind.DEFER, reason="no budget-feasible action")
    feasible.sort(key=lambda x: (x[0], x[1]))
    return feasible[0][2]
