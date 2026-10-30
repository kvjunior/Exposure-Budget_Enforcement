"""
Operational comparison (slice 2.2): every method shares ONE plan/demand contract (F04).

Each method returns a PLAN (a list of up to 2 actions) per request. ALL methods and the exact
offline oracle are replayed through the SAME replay_plan, with the SAME usable-completion/service
and single-charge miss accounting. Each method's actual plan trace, service count and cost are
returned and replayed. An independent reference (independent_reference.ref_optimum) that does NOT
share the action generator provides a second optimum.

Methods: greedy, rolling_horizon (perfect-information forecast, labeled), fixed_period,
immediate_rotation (roll-then-admit plan), risk_rotation_heuristic (our heuristic; SACMAT
conclusions withdrawn). EARP is retired. No controller is proposed.

Model simulation (declared cost units), NOT a deployed measurement. Deterministic.
"""
from __future__ import annotations
import json, os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tests", "differential"))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced, OwnerAvailability
from delegation_model.possible import CoalitionSpec
from delegation_model.transitions import fold_state
from delegation_manager.manager import Action, ActionKind, PreAuth, project_observation, check_action
from delegation_manager.policies import Request
from delegation_manager.exposure_check import ExposureBudget
from delegation_manager.cost_model import CostWeights, action_cost
from delegation_manager.baselines.fixed_period import fixed_period_policy, FixedPeriodState
from delegation_manager.baselines.greedy_history import greedy_history_policy
from delegation_manager.baselines.rolling_horizon import rolling_horizon_policy
from delegation_manager.baselines.risk_rotation_heuristic import risk_rotation_heuristic_policy
from delegation_manager.candidate_actions import enumerate_actions, _next_epoch_scope
from delegation_manager.offline_oracle import Instance, solve, replay_plan, _apply_action_events
from independent_reference import ref_solve, reference_actions
from delegation_manager.plan_contract import evaluate_plan
from dataclasses import asdict


def make_instance(n, budget_future, threshold=1):
    sc = Scope("g", 0)
    base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.e0.k0", 0),
            RecordProduced(2, Record("g", 0)), OwnerAvailability(3, "O", True)]
    reqs = [Request(4, Grant(f"G{i}", "O", f"R{i}", sc, RecordRange("g", 0, None), threshold, 3,
                             ("p0", "p1", "p2"), 0, None)) for i in range(n)]
    fam = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={f"R{i}" for i in range(n)})]
    return Instance(base, reqs, ExposureBudget(budget_future, 100.0), fam,
                    {Record("g", 0): 1.0}, cost_weights=CostWeights(), max_steps=6, max_branches=20)


def _single_admit_or_defer(obs, req, inst):
    """Choose a costed admission (including unserved ones) or defer; no rollover."""
    candidates = [(inst.cost_weights.miss_penalty, 1,
                   Action(ActionKind.DEFER, reason="no cheaper feasible admit"))]
    for a in enumerate_actions(obs, req, inst.preauth, max_delivery_choices=inst.max_branches):
        if a.kind == ActionKind.ADMIT_GRANT and \
                check_action(a, obs, inst.preauth, inst.budget, inst.family, inst.weights).ok:
            candidates.append((action_cost(a, inst.cost_weights, True), 0, a))
    return [min(candidates, key=lambda x: x[:2])[2]]


def method_plan(name, obs, req, history, inst, fp, forecast=()):
    """Return a PLAN (list of actions) for one request under method `name`. Common contract (F04)."""
    sc_next = _next_epoch_scope(obs, req.grant.scope.stream)
    registered = obs.registry.owner_of(req.grant.scope.stream)
    next_seq = obs.auth.produced.get(req.grant.scope.stream, 0)
    def roll_action():
        if sc_next is None or registered is None:
            return None
        if not (obs.is_owner_online(registered) or inst.preauth.permits_scope(registered, sc_next)):
            return None
        r = Action(ActionKind.ACTIVATE_SCOPE, scope=sc_next,
                   new_scope_key_id=f"{sc_next.stream}.e{sc_next.epoch}.k0", start_seq=next_seq)
        return r if check_action(r, obs, inst.preauth).ok else None

    if name == "greedy_history":
        return [greedy_history_policy(obs, req, inst.budget, inst.family, inst.weights,
                                      inst.preauth, inst.cost_weights,
                                      max_delivery_choices=inst.max_branches)]
    if name == "rolling_horizon":
        a = rolling_horizon_policy(obs, req, inst.budget, inst.family, inst.weights,
                                   forecast=list(forecast), horizon=3,
                                   preauth=inst.preauth, cost_weights=inst.cost_weights,
                                   history=history, forecast_kind="perfect_information",
                                   max_delivery_choices=inst.max_branches)
        if a.kind == ActionKind.ACTIVATE_SCOPE:
            # rolling horizon chose to roll: complete the plan by admitting on the closed scope
            h2 = history + _apply_action_events(history, a, (history[-1].t if history else -1) + 1)
            obs2 = project_observation(h2, h2[-1].t)
            admit = _single_admit_or_defer(obs2, req, inst)
            return [a] + (admit if admit[0].kind == ActionKind.ADMIT_GRANT else [])
        return [a] if a.kind == ActionKind.ADMIT_GRANT else _single_admit_or_defer(obs, req, inst)
    if name == "fixed_period":
        a = fixed_period_policy(obs, req, fp, inst.preauth)
        if a.kind == ActionKind.ACTIVATE_SCOPE:
            h2 = history + _apply_action_events(history, a, (history[-1].t if history else -1) + 1)
            obs2 = project_observation(h2, h2[-1].t)
            admit = _single_admit_or_defer(obs2, req, inst)
            return [a] + (admit if admit[0].kind == ActionKind.ADMIT_GRANT else [])
        return [a] if a.kind == ActionKind.ADMIT_GRANT else _single_admit_or_defer(obs, req, inst)
    if name == "immediate_rotation":
        # always roll then admit on the closed scope (one plan)
        r = roll_action()
        if r is not None:
            h2 = history + _apply_action_events(history, r, (history[-1].t if history else -1) + 1)
            obs2 = project_observation(h2, h2[-1].t)
            admit = _single_admit_or_defer(obs2, req, inst)
            if admit[0].kind == ActionKind.ADMIT_GRANT:
                return [r, admit[0]]
        return _single_admit_or_defer(obs, req, inst)
    if name == "risk_rotation_heuristic":
        a = risk_rotation_heuristic_policy(obs, req, inst.budget, inst.family, inst.weights, inst.preauth)
        if a.kind == ActionKind.ACTIVATE_SCOPE:
            h2 = history + _apply_action_events(history, a, (history[-1].t if history else -1) + 1)
            obs2 = project_observation(h2, h2[-1].t)
            admit = _single_admit_or_defer(obs2, req, inst)
            return [a] + (admit if admit[0].kind == ActionKind.ADMIT_GRANT else [])
        return [a] if a.kind == ActionKind.ADMIT_GRANT else _single_admit_or_defer(obs, req, inst)
    raise ValueError(name)


METHODS = ["fixed_period", "immediate_rotation", "greedy_history", "rolling_horizon",
           "risk_rotation_heuristic"]


def run_method(name, inst):
    """Build this method's PLAN-per-request trace, then replay it through the common replay_plan."""
    history = list(inst.base_history)
    plans = []
    served = 0
    fp = FixedPeriodState(period=2)
    for step, req in enumerate(inst.requests):
        cutoff = history[-1].t if history else -1
        obs = project_observation(history, cutoff)
        plan = method_plan(name, obs, req, history, inst, fp, forecast=inst.requests[step+1:])
        if inst.max_plan_actions == 1 and len(plan) == 2:
            plan = plan[:1]
        result = evaluate_plan(inst, history, req, plan)
        if not result.feasible:
            plan = [Action(ActionKind.DEFER, reason="fallback")]
            result = evaluate_plan(inst, history, req, plan)
        plans.append(plan)
        history = result.history
        served += int(result.served)
    feasible, cost, reason = replay_plan(inst, plans)
    full = [[dict(asdict(a), kind=a.kind.value) for a in p] for p in plans]
    return {"plans": [[a.kind.value for a in p] for p in plans], "action_plans": full,
            "cost": cost, "feasible": feasible, "service": reason,
            "service_counts": {"served": served, "unserved": len(inst.requests)-served}}


def main():
    instances = {"whole_key_2req_budget1": make_instance(2, 1, 1),
                 "threshold2_2req_budget1": make_instance(2, 1, 2),
                 "lenient_2req_budget2": make_instance(2, 2, 1)}
    out = {"run_kind": "model-simulation (declared cost units; NOT a deployed measurement)",
           "env": {"python": platform.python_version()},
           "notes": ["EARP retired; no controller proposed.",
                     "risk_rotation_heuristic is OUR heuristic; SACMAT conclusions withdrawn.",
                     "ALL methods share ONE plan contract (F04): up to 2 actions/request, replayed "
                     "through replay_plan with usable-completion and single-charge miss accounting.",
                     "rolling_horizon forecast is perfect-information (diagnostic), labeled.",
                     "independent reference does NOT share enumerate_actions (F02/F06)."],
           "instances": {}}
    violations = []
    for iname, inst in instances.items():
        opt = solve(inst); ofeas, orc, _ = replay_plan(inst, opt.plans)
        ref_schedule = ref_solve(inst)
        ref = ref_schedule.total_cost
        ref_plans = reference_actions(ref_schedule)
        ref_ok, ref_cost, ref_service = replay_plan(inst, ref_plans)
        entry = {"n_requests": len(inst.requests), "budget": inst.budget.max_future_scopes,
                 "oracle": {"cost": opt.total_cost, "replay_feasible": ofeas, "replay_cost": orc,
                            "plans": [[a.kind.value for a in p] for p in opt.plans]},
                 "independent_reference_optimum": ref,
                 "reference_replay": {"feasible": ref_ok, "cost": ref_cost,
                                      "service": ref_service, "served": ref_schedule.served,
                                      "plans": [[dict(asdict(a), kind=a.kind.value) for a in p]
                                                for p in ref_plans]}, "methods": {}}
        if not ref_ok or ref_cost != ref:
            violations.append(f"{iname}: reference plan replay mismatch")
        if not ofeas or abs(orc - opt.total_cost) > 1e-9:
            violations.append(f"{iname}: oracle replay mismatch")
        if abs(ref - opt.total_cost) > 1e-9:
            violations.append(f"{iname}: independent reference {ref} != oracle {opt.total_cost}")
        for m in METHODS:
            r = run_method(m, inst)
            r["gap_to_optimum"] = r["cost"] - opt.total_cost
            r["matches_optimum"] = abs(r["gap_to_optimum"]) < 1e-9
            if not r["feasible"]:
                violations.append(f"{iname}/{m}: method trace not feasible under common replay")
            if r["gap_to_optimum"] < -1e-9:
                violations.append(f"{iname}/{m}: beats optimum ({r['gap_to_optimum']})")
            entry["methods"][m] = r
        out["instances"][iname] = entry

    os.makedirs("results/manifests", exist_ok=True)
    with open("results/manifests/controller_comparison.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"\n[controller_comparison] violations: {len(violations)}")
    for v in violations:
        print("   ", v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
