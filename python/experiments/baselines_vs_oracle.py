"""
Deterministic P2 experiment (review step 4): run fixed-period / greedy-history / rolling-horizon
and the exact offline oracle on a small fixed set of instances, and emit machine-readable JSON
decision/run records. This is MODEL SIMULATION (not a deployed-service measurement); it is labelled
as such. No timings are reported; the objective is the declared cost model.

Run: python python/experiments/baselines_vs_oracle.py
Writes results/manifests/baselines_vs_oracle.json and prints a summary. Deterministic.
"""
from __future__ import annotations
import json, os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced
from delegation_model.possible import CoalitionSpec
from delegation_manager.manager import Action, ActionKind, PreAuth, project_observation, check_action
from delegation_manager.policies import Request
from delegation_manager.exposure_check import ExposureBudget
from delegation_manager.cost_model import CostWeights, action_cost
from delegation_manager.decision_log import DecisionRecord
from delegation_manager.baselines.fixed_period import fixed_period_policy, FixedPeriodState
from delegation_manager.baselines.greedy_history import greedy_history_policy
from delegation_manager.baselines.rolling_horizon import rolling_horizon_policy
from delegation_manager.offline_oracle import Instance, solve, replay_schedule, _apply_action_events


def make_instance(n_requests, budget_future, scope_active=True):
    sc = Scope("g", 0)
    base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.e0.k0", 0),
            RecordProduced(2, Record("g", 0))]
    reqs = [Request(3, Grant(f"G{i}", "O", f"R_G{i}", sc, RecordRange("g", 0, None), 2, 3,
                             ("p0", "p1", "p2"), 0, None)) for i in range(n_requests)]
    fam = [CoalitionSpec("C", proxies={"p0", "p1", "p2"},
                         recipients={f"R_G{i}" for i in range(n_requests)})]
    return Instance(base, reqs, ExposureBudget(budget_future, 100.0),
                    fam, {Record("g", 0): 1.0}, cost_weights=CostWeights(),
                    max_steps=6, max_branches=8)


def run_policy(name, inst):
    history = list(inst.base_history); total = 0.0; decisions = []
    fp = FixedPeriodState(period=1)
    for step, req in enumerate(inst.requests):
        cutoff = history[-1].t if history else -1
        obs = project_observation(history, cutoff)
        if name == "fixed_period":
            a = fixed_period_policy(obs, req, fp, inst.preauth)
        elif name == "greedy_history":
            a = greedy_history_policy(obs, req, inst.budget, inst.family, inst.weights,
                                      inst.preauth, inst.cost_weights)
        else:
            a = rolling_horizon_policy(obs, req, inst.budget, inst.family, inst.weights,
                                       forecast=inst.requests[step+1:], horizon=2,
                                       preauth=inst.preauth, cost_weights=inst.cost_weights)
        res = check_action(a, obs, inst.preauth, inst.budget, inst.family, inst.weights)
        if not res.ok:
            a = Action(ActionKind.DEFER, reason="infeasible->defer")
            res = check_action(a, obs, inst.preauth, inst.budget, inst.family, inst.weights)
        c = action_cost(a, inst.cost_weights, True)
        # Partial-completion misses are already included by action_cost.
        total += c
        decisions.append(DecisionRecord(
            cutoff=cutoff, policy=name, action_kind=a.kind.value, checker_ok=res.ok,
            reason=res.reason, exposure_reason=getattr(res, "exposure_reason", ""),
            future_witness=getattr(res, "future_witness", None),
            past_witness=getattr(res, "past_witness", None),
            state_version=len(history), cost=c).to_json())
        history = history + _apply_action_events(history, a, cutoff + 1)
    return total, decisions


def main():
    instances = {
        "feasible_2req_budget1": make_instance(2, 1),
        "infeasible_1req_budget0": make_instance(1, 0),
        "feasible_3req_budget1": make_instance(3, 1),
    }
    out = {"run_kind": "model-simulation (NOT a deployed-service measurement)",
           "objective": "declared cost model (operation/miss units); no timings",
           "env": {"python": platform.python_version(), "platform": platform.platform()},
           "instances": {}}
    for iname, inst in instances.items():
        opt = solve(inst)
        feasible, recost, reason = replay_schedule(inst, opt.actions)
        entry = {"n_requests": len(inst.requests),
                 "budget_future_scopes": inst.budget.max_future_scopes,
                 "oracle": {"cost": opt.total_cost, "actions": [a.kind.value for a in opt.actions],
                            "replay_feasible": feasible, "replay_cost": recost},
                 "policies": {}}
        for name in ["fixed_period", "greedy_history", "rolling_horizon"]:
            cost, decisions = run_policy(name, inst)
            entry["policies"][name] = {"cost": cost, "gap_to_optimum": cost - opt.total_cost,
                                       "n_decisions": len(decisions)}
        out["instances"][iname] = entry

    os.makedirs("results/manifests", exist_ok=True)
    path = "results/manifests/baselines_vs_oracle.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    # sanity: no online policy beats the optimum
    bad = [(i, p, d["gap_to_optimum"]) for i, e in out["instances"].items()
           for p, d in e["policies"].items() if d["gap_to_optimum"] < -1e-9]
    print(f"\n[baselines_vs_oracle] wrote {path}; negative-gap violations: {len(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
