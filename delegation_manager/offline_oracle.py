"""Exact bounded oracle over the explicit decision-index service-plan domain.

All fragment subsets, including unserved metadata/partial operations, are
considered. The scope choice is the next epoch and canonical fresh key ID.
Plans have one action or ROTATE then ADMIT of the offered immutable grant.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from delegation_model.events import Event
from delegation_model.transitions import fold_state
from delegation_model.validation import validate_history
from .manager import Action, ActionKind, PreAuth, project_observation
from .policies import Request
from .candidate_actions import enumerate_actions
from .cost_model import CostWeights
from .plan_contract import action_events, evaluate_plan


@dataclass
class Instance:
    base_history: List[Event]
    requests: List[Request]
    budget: object
    family: list
    weights: Dict[object, float]
    preauth: PreAuth = field(default_factory=PreAuth)
    cost_weights: CostWeights = field(default_factory=CostWeights)
    max_branches: int = 20  # maximum delivery-subset count per request
    max_steps: int = 6
    max_plan_actions: int = 2

    def __post_init__(self):
        if type(self.max_plan_actions) is not int or self.max_plan_actions not in (1, 2):
            raise ValueError("max_plan_actions must be 1 or 2 in this bounded model")
        if type(self.max_branches) is not int or self.max_branches < 1:
            raise ValueError("max_branches must be a positive integer")
        if type(self.max_steps) is not int or self.max_steps < 0:
            raise ValueError("max_steps must be a nonnegative integer")
        if not isinstance(self.cost_weights, CostWeights):
            raise TypeError("cost_weights must be a validated CostWeights instance")


@dataclass
class Schedule:
    actions: List[Action]
    total_cost: float
    plans: Optional[list] = None


def _apply_action_events(history, action, t0):
    """Compatibility pure event builder; does not commit or authorize an action."""
    return action_events(history, action, t0)


def _enumerate_plans(inst, history, req):
    obs = project_observation(history, history[-1].t if history else -1)
    singles = enumerate_actions(obs, req, inst.preauth, max_delivery_choices=inst.max_branches)
    plans = [[a] for a in singles]
    if inst.max_plan_actions == 2:
        for action in singles:
            if action.kind != ActionKind.ACTIVATE_SCOPE:
                continue
            first = evaluate_plan(inst, history, req, [action])
            if not first.feasible:
                continue
            h2 = first.history
            o2 = project_observation(h2, h2[-1].t if h2 else -1)
            for admission in enumerate_actions(o2, req, inst.preauth,
                                                max_delivery_choices=inst.max_branches):
                if admission.kind == ActionKind.ADMIT_GRANT:
                    plans.append([action, admission])
    if len(plans) > inst.max_branches * (inst.max_plan_actions + 1) + 3:
        raise ValueError("plan branching exceeds the declared bound")
    return plans


def solve(inst):
    """Return the complete optimum in the declared bounded domain, or refuse."""
    validate_history(inst.base_history)
    fold_state(inst.base_history)
    if len(inst.requests) > inst.max_steps:
        raise ValueError("request count exceeds max_steps")
    best = None

    def visit(history, step, chosen, cost):
        nonlocal best
        if best is not None and cost >= best.total_cost:
            return
        if step == len(inst.requests):
            best = Schedule([a for p in chosen for a in p], cost, list(chosen))
            return
        req = inst.requests[step]
        for plan in _enumerate_plans(inst, history, req):
            result = evaluate_plan(inst, history, req, plan)
            if result.feasible:
                visit(result.history, step + 1, chosen + [plan], cost + result.cost)

    visit(list(inst.base_history), 0, [], 0.0)
    if best is None:
        raise ValueError("no feasible schedule in the declared bounded domain")
    return best


def replay_plan(inst, plans) -> Tuple[bool, float, str]:
    """Validate grammar, full demand, per-action authority/budget, service and cost."""
    if len(plans) != len(inst.requests):
        return False, 0.0, "one plan is required per request"
    try:
        validate_history(inst.base_history)
        fold_state(inst.base_history)
    except ValueError as ex:
        return False, 0.0, "invalid initial history: " + str(ex)
    history = list(inst.base_history)
    total = 0.0
    served = 0
    for step, (req, plan) in enumerate(zip(inst.requests, plans)):
        result = evaluate_plan(inst, history, req, plan)
        if not result.feasible:
            return False, total, f"step {step}: {result.reason}"
        history = result.history
        total += result.cost
        served += int(result.served)
    return True, total, f"ok (served {served}, unserved {len(inst.requests) - served})"


def replay_schedule(inst, schedule):
    return replay_plan(inst, [[action] for action in schedule])
