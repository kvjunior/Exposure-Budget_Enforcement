"""
Rolling-horizon baseline (S2-04 repair).

Receding-horizon planning with CANDIDATE-CONDITIONED lookahead. For each immediate candidate action
`a`, we FORK the history, EXECUTE `a` against the fork, then advance the fork by greedily deciding
each forecast request against the UPDATED observation. The plan cost is a's immediate cost plus the
rollout cost on the fork. We pick the first action of the lowest-cost feasible plan. The slice-2 bug
(the rollout called greedy on the ORIGINAL unchanged obs, so forecast cost was a constant added to
every candidate) is fixed: the fork is really advanced.

Forecast labeling (S2-04): `forecast_kind` names the information model:
  - "known_calendar": the forecast requests are a schedule the owner actually published (causal);
  - "estimate": an estimated arrival forecast (causal, possibly wrong);
  - "perfect_information": a diagnostic that feeds the true remaining requests (NOT causal; label
    makes the information advantage explicit so it is not mistaken for a deployable result).
The experiment that supplies the true remaining request list MUST pass forecast_kind="perfect_
information" or "known_calendar" and say so.
"""
from __future__ import annotations
from typing import List, Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_manager.manager import Action, ActionKind, Observation, PreAuth, check_action, project_observation
from delegation_manager.policies import Request
from delegation_manager.candidate_actions import enumerate_actions
from delegation_manager.cost_model import action_cost, CostWeights
from delegation_manager.baselines.greedy_history import greedy_history_policy
from delegation_manager.offline_oracle import _apply_action_events


def _advance(history, action, cutoff):
    return history + _apply_action_events(history, action, cutoff + 1)


def rolling_horizon_policy(obs: Observation, req: Optional[Request], budget, family, weights,
                           forecast: Optional[List[Request]] = None, horizon: int = 2,
                           preauth: Optional[PreAuth] = None,
                           cost_weights: CostWeights = CostWeights(),
                           history: Optional[list] = None,
                           forecast_kind: str = "known_calendar",
                           max_delivery_choices: int = 20) -> Action:
    preauth = preauth or PreAuth()
    if not forecast:
        return greedy_history_policy(obs, req, budget, family, weights, preauth, cost_weights,
                                     max_delivery_choices=max_delivery_choices)
    # history is needed to fork and advance; if not supplied, fall back to obs.events (observable).
    base_hist = list(history) if history is not None else list(obs.events)
    candidates = enumerate_actions(obs, req, preauth, max_delivery_choices=max_delivery_choices)
    best = None
    for a in candidates:
        res = check_action(a, obs, preauth, budget, family, weights)
        if not res.ok:
            continue
        c = action_cost(a, cost_weights, req is not None)
        # FORK: execute a against the fork, then roll the forecast forward on the UPDATED state.
        fork = _advance(base_hist, a, base_hist[-1].t if base_hist else -1)
        rollout = 0.0
        for fr in forecast[:horizon]:
            cutoff = fork[-1].t if fork else -1
            fobs = project_observation(fork, cutoff)
            fa = greedy_history_policy(fobs, fr, budget, family, weights, preauth, cost_weights,
                                       max_delivery_choices=max_delivery_choices)
            if not check_action(fa, fobs, preauth, budget, family, weights).ok:
                fa = Action(ActionKind.DEFER, reason="forecast infeasible->defer")
            rollout += action_cost(fa, cost_weights, True)
            fork = _advance(fork, fa, cutoff)
        total = c + rollout
        # deterministic tie-break: prefer serving the current request (admit) at equal total
        pref = {ActionKind.ADMIT_GRANT: 0, ActionKind.ACTIVATE_SCOPE: 1,
                ActionKind.DEFER: 2, ActionKind.REJECT: 3}.get(a.kind, 9)
        key = (total, pref)
        if best is None or key < best[0]:
            best = (key, a)
    return best[1] if best else Action(ActionKind.DEFER, reason="no budget-feasible action")
