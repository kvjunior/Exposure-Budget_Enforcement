"""
P3C timed gap-to-optimum pilot (model simulation; NOT a deployed/performance measurement).

Produces, for several tiny timed instances across regimes, the exact timed optimum (timed_oracle),
an independent-reference cross-check (timed_independent_reference), and the cost of two online
policies (greedy serve; blind rotate-first). Emits JSON with per-instance gap-to-optimum. This is
the timed analogue of baselines_vs_oracle, and it is the evidence behind the paper's claim that
INSIDE the feasible regime a simple greedy policy attains the optimum while blind rotation does not.

Deterministic. Writes results/manifests/p3c_timed_oracle.json. Exit 0 iff no online policy beats
the optimum and every oracle optimum replays feasibly and matches the independent reference.
"""
from __future__ import annotations
import json, os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tests", "differential"))

from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform, ActivateScope)
from delegation_manager.timed_oracle import TimedInstance, solve_timed, replay_timed, TimedCost
from timed_independent_reference import judge


def _notice(eid, t, payload, available=None):
    return PublicEvent(eid, T(t), T(t if available is None else available), payload)


def build(extra=(), deadline=30, budget=Budget(100, 100, 5)):
    r = Record('g', 0)
    dem = Demand('D', 'O', 'R', (r,), T(0), T(deadline))
    trace = (_notice('up', 0, OwnerNotice('O', True)),
             _notice('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
             RecordProduction('r0', 'O', r, T(0), T(0)),
             _notice('arrival', 0, DemandArrival(dem))) + extra
    family = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)
    grant = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2,
                       ('p0', 'p1', 'p2'), TimeWindow(T(0), T(30)))
    return trace, dem, grant, (lambda: ServiceSimulator(trace, family, budget)), budget


cost = TimedCost()


def greedy(sim, grant):
    r = sim.execute(InstallGrant('D', grant, (0, 1)), sim.view())
    if r.status == 'installed':
        sim.execute(Transform('D', 'G', (0, 1)), sim.view())


def blind_rollover(sim, grant):
    rr = sim.execute(ActivateScope(ScopeNotice('O', Scope('g', 1), 'key1', 1)), sim.view())
    sim.execute(InstallGrant('D', grant, (0, 1)), sim.view())
    sim.execute(Transform('D', 'G', (0, 1)), sim.view())


def online_cost(make_sim, grant, policy):
    sim = make_sim(); n = len(make_sim().view().queue.entries)
    policy(sim, grant); rep = sim.report()
    served = rep['queue'].served; deliveries = len(rep['deliveries'])
    rollovers = sum(1 for (_, kind, status, _) in rep['outcomes']
                    if kind == 'ActivateScope' and status == 'activated')
    return cost.fragment * deliveries + cost.rollover * rollovers + cost.miss * (n - served)


def main():
    instances = {
        "generous_servable": build(),
        "tight_deadline_unservable": build(deadline=6),
        "owner_offline_during_install": build(extra=(_notice('down', 1, OwnerNotice('O', False)),)),
    }
    out = {"batch": "P3C",
           "run_kind": "model-simulation (timed; declared cost units; NOT a performance measurement)",
           "backend": "abstract-cfrag-usability-model",
           "env": {"python": platform.python_version()},
           "cost_model": {"fragment": cost.fragment, "rollover": cost.rollover, "miss": cost.miss},
           "notes": ["Timed oracle = exhaustive deepcopy search over the REAL ServiceSimulator.",
                     "Independent reference does NOT import ServiceSimulator or the oracle generator.",
                     "Gap-to-optimum INSIDE the feasible regime: greedy = optimum, blind-rollover > optimum."],
           "instances": {}}
    violations = []
    for name, (trace, dem, grant, make_sim, budget) in instances.items():
        ticks = {e.occurred_at.ticks for e in trace if hasattr(e, 'occurred_at')}
        ticks.add(dem.deadline.ticks)
        ev_ticks = tuple(sorted(ticks))
        inst = TimedInstance(make_sim, {'D': grant}, ev_ticks, cost=cost)
        opt = solve_timed(inst)
        feas, rc, served, note = replay_timed(inst, opt.actions)
        forbids = (budget.active_scopes == 0)
        ref = judge(trace, dem, grant, cost, budget_forbids_exposed_scope=forbids, fencing_available=False)
        g_cost = online_cost(make_sim, grant, greedy)
        b_cost = online_cost(make_sim, grant, blind_rollover)
        entry = {"oracle_cost": opt.total_cost, "oracle_served": opt.served,
                 "oracle_actions": [type(a).__name__ for a in opt.actions],
                 "oracle_replays_feasibly": feas, "oracle_replay_cost": rc,
                 "independent_reference_cost": ref.cost, "independent_reference_servable": ref.max_servable,
                 "independent_reference_note": ref.note,
                 "greedy_cost": g_cost, "greedy_gap": g_cost - opt.total_cost,
                 "blind_rollover_cost": b_cost, "blind_rollover_gap": b_cost - opt.total_cost}
        out["instances"][name] = entry
        if not feas or abs(rc - opt.total_cost) > 1e-9:
            violations.append(f"{name}: oracle replay mismatch")
        if ref.exact and abs(ref.cost - opt.total_cost) > 1e-9:
            violations.append(f"{name}: independent reference {ref.cost} != oracle {opt.total_cost}")
        if g_cost < opt.total_cost - 1e-9 or b_cost < opt.total_cost - 1e-9:
            violations.append(f"{name}: an online policy beats the optimum")

    os.makedirs("results/manifests", exist_ok=True)
    with open("results/manifests/p3c_timed_oracle.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"\n[p3c_timed_oracle] violations: {len(violations)}")
    for v in violations:
        print("   ", v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
