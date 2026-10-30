"""Separate bounded choice/authority/cost reference for Slice 2.2.1.

Independent: subset/plan generation, per-step token matching, owner registry,
service accounting, costs, search. Shared explicitly: immutable input types,
validated transition folding, possible_exposure and coalition expansion. This
is not an independent cryptographic/temporal-knowledge implementation.
No production candidate/checker/plan/cost function is used by the search.
"""
from dataclasses import dataclass
from itertools import combinations
import math
from delegation_model.types import Scope
from delegation_model.events import (GrantIssued, KFragInstalled, ScopeActivated,
                                     StreamAuthorized, OwnerAvailability, RecordProduced)
from delegation_model.possible import possible_exposure, CoalitionSpec
from delegation_model.coverage import expand_family
from delegation_model.transitions import fold_state
from delegation_model.validation import validate_history


@dataclass
class ReferenceSchedule:
    plans: list
    total_cost: float
    served: int


def _owner(history, stream):
    registry = {}
    online = {}
    for event in history:
        if isinstance(event, StreamAuthorized):
            registry.setdefault(event.stream, event.owner)
            online.setdefault(event.owner, True)
        elif isinstance(event, OwnerAvailability):
            online[event.owner] = event.online
    owner = registry.get(stream)
    return owner, online.get(owner, False)


def _grant_token(token, grant, indices, now):
    if (token.owner, token.recipient, token.stream, token.epoch) != (
            grant.owner, grant.recipient, grant.scope.stream, grant.scope.epoch):
        return False
    if grant.rng.lo < token.lo:
        return False
    if token.hi is not None and (grant.rng.hi is None or grant.rng.hi > token.hi):
        return False
    if now < token.issue_from or (token.issue_to is not None and now > token.issue_to):
        return False
    if token.access_from is not None and grant.valid_from < token.access_from:
        return False
    if token.access_to is not None and (grant.valid_to is None or grant.valid_to > token.access_to):
        return False
    return set(indices).issubset(set(token.permitted_indices))


def _within(history, inst):
    if not inst.family or any(not isinstance(c, CoalitionSpec) for c in inst.family):
        return False
    if len({c.label for c in inst.family}) != len(inst.family):
        return False
    if any(not math.isfinite(w) or w < 0 for w in inst.weights.values()):
        return False
    for case in expand_family(list(inst.family)):
        x = possible_exposure(history, case, history[-1].t if history else -1, inst.weights)
        if len(x.future_scopes) > inst.budget.max_future_scopes or x.past > inst.budget.max_past_weight:
            return False
    return True


def _events(history, step):
    kind, payload = step
    t = (history[-1].t if history else -1) + 1
    if kind == "admit":
        grant, indices = payload
        return [GrantIssued(t, grant)] + [
            KFragInstalled(t + j + 1, grant.grant_id, grant.proxies[i], i)
            for j, i in enumerate(indices)]
    if kind == "activate":
        scope, key, seq = payload
        owner, _ = _owner(history, scope.stream)
        return [ScopeActivated(t, owner, scope, key, seq)]
    return []


def _advance(history, step, inst):
    """Check authority at THIS evolved prefix, then transitions and admission budget."""
    kind, payload = step
    now = history[-1].t if history else -1
    if kind == "admit":
        grant, indices = payload
        if (any(type(i) is not int or not 0 <= i < grant.shares for i in indices)
                or len(set(indices)) != len(indices) or tuple(indices) != tuple(sorted(indices))):
            return None
        owner, online = _owner(history, grant.scope.stream)
        if owner != grant.owner:
            return None
        if not any(isinstance(e, ScopeActivated) and e.scope == grant.scope for e in history):
            return None
        if any(isinstance(e, GrantIssued) and e.grant.grant_id == grant.grant_id for e in history):
            return None
        if not online and not any(_grant_token(t, grant, indices, now) for t in inst.preauth.grant_tokens):
            return None
    elif kind == "activate":
        scope, key, seq = payload
        owner, online = _owner(history, scope.stream)
        if owner is None or (not online and
                             (owner, scope.stream, scope.epoch) not in inst.preauth.scope_tokens):
            return None
    elif kind not in ("defer", "reject"):
        return None
    h2 = history + _events(history, step)
    try:
        fold_state(h2)
    except ValueError:
        return None
    if kind == "admit" and payload[1] and not _within(h2, inst):
        return None
    return h2


def _roll_payload(history, stream):
    epochs = [e.scope.epoch for e in history
              if isinstance(e, ScopeActivated) and e.scope.stream == stream]
    if not epochs:
        return None
    scope = Scope(stream, max(epochs) + 1)
    seq = sum(isinstance(e, RecordProduced) and e.record.stream == stream for e in history)
    return scope, f"{stream}.e{scope.epoch}.k0", seq


def _steps(history, req, inst):
    grant = req.grant
    if grant.shares >= inst.max_branches.bit_length():
        raise ValueError("reference delivery subsets exceed max_branches")
    steps = [("defer", None), ("reject", None)]
    for size in range(grant.shares + 1):
        for indices in combinations(range(grant.shares), size):
            steps.append(("admit", (grant, indices)))
    payload = _roll_payload(history, grant.scope.stream)
    if payload is not None:
        steps.append(("activate", payload))
    return steps


def _plans(history, req, inst):
    singles = _steps(history, req, inst)
    for step in singles:
        yield [step]
    if inst.max_plan_actions == 2:
        for step in singles:
            if step[0] != "activate":
                continue
            h2 = _advance(history, step, inst)
            if h2 is not None:
                for next_step in _steps(h2, req, inst):
                    if next_step[0] == "admit":
                        yield [step, next_step]


def _cost(step, weights):
    kind, payload = step
    if kind == "admit":
        grant, indices = payload
        return (len(indices) * weights.per_fragment_cost
                + (weights.miss_penalty if len(indices) < grant.threshold else 0))
    if kind == "activate":
        return weights.rollover_cost + weights.miss_penalty
    return weights.miss_penalty


def reference_evaluate_plan(inst, history, req, plan):
    """Separate plan validator; None denotes an invalid plan."""
    if not isinstance(plan, (list, tuple)) or not 1 <= len(plan) <= inst.max_plan_actions:
        return None
    if len(plan) == 2 and tuple(s[0] for s in plan) != ("activate", "admit"):
        return None
    h = list(history)
    cost = 0.0
    served = False
    for step in plan:
        if step[0] == "admit" and step[1][0] != req.grant:
            return None
        if step[0] == "activate" and step[1] != _roll_payload(h, req.grant.scope.stream):
            return None
        h2 = _advance(h, step, inst)
        if h2 is None:
            return None
        cost += _cost(step, inst.cost_weights)
        h = h2
        if step[0] == "admit":
            grant, indices = step[1]
            served = len(indices) >= grant.threshold
    return h, cost, served


def ref_solve(inst):
    if inst.max_plan_actions not in (1, 2) or inst.max_branches < 1:
        raise ValueError("reference requires K=1/2 and a positive branching bound")
    if len(inst.requests) > inst.max_steps:
        raise ValueError("reference request count exceeds max_steps")
    validate_history(inst.base_history)
    fold_state(inst.base_history)
    best = None

    def visit(history, i, chosen, cost, served):
        nonlocal best
        if best is not None and cost >= best.total_cost:
            return
        if i == len(inst.requests):
            best = ReferenceSchedule(list(chosen), cost, served)
            return
        for plan in _plans(history, inst.requests[i], inst):
            result = reference_evaluate_plan(inst, history, inst.requests[i], plan)
            if result is not None:
                h, dc, complete = result
                visit(h, i + 1, chosen + [plan], cost + dc, served + int(complete))
    visit(list(inst.base_history), 0, [], 0.0, 0)
    if best is None:
        raise ValueError("reference found no feasible schedule")
    return best


def ref_optimum(inst):
    return ref_solve(inst).total_cost


def reference_actions(schedule):
    """Output-only adapter for replay. Production actions are NOT used by reference search."""
    from delegation_manager.manager import Action, ActionKind
    plans = []
    for plan in schedule.plans:
        converted = []
        for kind, payload in plan:
            if kind == "admit":
                grant, indices = payload
                action = Action(ActionKind.ADMIT_GRANT, grant=grant, authorized_kfrag_indices=indices)
            elif kind == "activate":
                scope, key, seq = payload
                action = Action(ActionKind.ACTIVATE_SCOPE, scope=scope, new_scope_key_id=key, start_seq=seq)
            else:
                action = Action(ActionKind.DEFER if kind == "defer" else ActionKind.REJECT)
            converted.append(action)
        plans.append(converted)
    return plans
