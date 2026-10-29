"""Shared bounded decision-index plans; this is not a timed service simulator.

One offered immutable grant gets one action, or ROTATE then ADMIT of that
same grant. Metadata/partial/full/superset fragment deliveries are permitted.
"""
from dataclasses import dataclass
from delegation_model.transitions import fold_state, TransitionError
from .manager import ActionKind, check_action, project_observation
from .cost_model import action_cost
from .executor import _planned_events_and_effects


@dataclass
class PlanEvaluation:
    feasible: bool
    history: list
    cost: float
    served: bool
    reason: str


def valid_plan_shape(plan, maximum):
    if maximum not in (1, 2):
        return False
    if not isinstance(plan, (list, tuple)) or not 1 <= len(plan) <= maximum:
        return False
    kinds = tuple(getattr(a, "kind", None) for a in plan)
    if len(kinds) == 1:
        return kinds[0] in (ActionKind.DEFER, ActionKind.REJECT,
                            ActionKind.ADMIT_GRANT, ActionKind.ACTIVATE_SCOPE)
    return kinds == (ActionKind.ACTIVATE_SCOPE, ActionKind.ADMIT_GRANT)


def action_events(history, action, t0):
    """Pure event construction using the executor's builder, not an authority gate."""
    state = fold_state(history)
    events, _ = _planned_events_and_effects(action, state, t0)
    return events


def evaluate_plan(inst, history, req, plan):
    if not valid_plan_shape(plan, inst.max_plan_actions):
        return PlanEvaluation(False, list(history), 0, False,
                              "plan violates one-action or rotation-then-admit grammar/bound")
    h = list(history)
    cost = 0.0
    admission = None
    for action in plan:
        if action.kind == ActionKind.ADMIT_GRANT and action.grant != req.grant:
            return PlanEvaluation(False, list(history), 0, False,
                                  "ADMIT does not fully bind the offered grant")
        cutoff = h[-1].t if h else -1
        obs = project_observation(h, cutoff)
        verdict = check_action(action, obs, inst.preauth, inst.budget, inst.family, inst.weights)
        if not verdict.ok:
            return PlanEvaluation(False, list(history), 0, False, verdict.reason)
        if action.kind == ActionKind.ADMIT_GRANT:
            if tuple(action.authorized_kfrag_indices) != tuple(sorted(action.authorized_kfrag_indices)):
                return PlanEvaluation(False, list(history), 0, False, "service plans use sorted delivery indices")
        if action.kind == ActionKind.ACTIVATE_SCOPE:
            from delegation_model.types import Scope
            stream = req.grant.scope.stream
            spans = obs.auth.scope_spans.get(stream, [])
            wanted = Scope(stream, max(s.scope.epoch for s in spans) + 1) if spans else None
            if (wanted is None or action.scope != wanted or
                    action.new_scope_key_id != f"{stream}.e{wanted.epoch}.k0" or
                    action.start_seq != obs.auth.produced.get(stream, 0)):
                return PlanEvaluation(False, list(history), 0, False,
                                      "rollover must be the request stream's canonical next epoch")
        try:
            h = h + action_events(h, action, cutoff + 1)
            state = fold_state(h)
        except (TransitionError, IndexError) as ex:
            return PlanEvaluation(False, list(history), 0, False, "transition refused: " + str(ex))
        cost += action_cost(action, inst.cost_weights, True)
        if action.kind == ActionKind.ADMIT_GRANT:
            admission = action.grant
    served = (admission is not None and
              len(state.installed.get(admission.grant_id, set())) >= admission.threshold)
    return PlanEvaluation(True, h, cost, served, "ok")
