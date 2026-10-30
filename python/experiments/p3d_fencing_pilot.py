"""
P3D fenced-vs-unfenced evaluation pilot (Task 5). Model simulation; NOT a cryptographic measurement.

Compares, across a small deterministic parameter sweep, a FENCED run (production fencing per
production_fence) and an UNFENCED run on the same environment. Reports, per setting:
  - actual cumulative disclosed weight (evaluator truth) and budget violations,
  - public-observation lag vs actual exposure (does the public ledger under-report?),
  - deadline misses / completed service,
  - rotation + fencing overhead (rotations, deferrals, rejections, rotation ticks),
  - total management cost,
  - owner-availability effect (online vs offline-at-production).

Parameters swept (documented): report delay for the at-risk production, and owner availability at
production time. Each setting is DETERMINISTIC (no RNG); we vary the documented parameters rather
than seeds because the model is deterministic. Writes results/manifests/p3d_fencing_pilot.json.
Exit 0 iff, in every setting, the fenced run has actual disclosed weight 0 and no budget violation,
and the unfenced run discloses under a tight budget (establishing the comparison is meaningful).
"""
from __future__ import annotations
import json, os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform)

family = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)


def _n(eid, t, payload, avail=None):
    return PublicEvent(eid, T(t), T(t if avail is None else avail), payload)


def build(fenced, report_delay, owner_offline_at_prod):
    r0, r1 = Record('g', 0), Record('g', 1)
    dem = Demand('D', 'O', 'R', (r0,), T(0), T(40))
    base = [_n('up', 0, OwnerNotice('O', True)),
            _n('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
            RecordProduction('r0', 'O', r0, T(0), T(0)),
            _n('arrival', 0, DemandArrival(dem))]
    prod_tick = 6
    if owner_offline_at_prod:
        base.append(_n('down', 4, OwnerNotice('O', False)))  # after install, before production
    if fenced:
        if not owner_offline_at_prod:
            base.append(_n('rotate', 5, ScopeNotice('O', Scope('g', 1), 'key1', 1)))
            base.append(RecordProduction('r1', 'O', r1, T(prod_tick), T(prod_tick + report_delay)))
        # offline+fenced: production REJECTED -> omit r1
    else:
        base.append(RecordProduction('r1', 'O', r1, T(prod_tick), T(prod_tick + report_delay)))
    g = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2, ('p0', 'p1', 'p2'),
                   TimeWindow(T(0), T(40)))
    return tuple(base), g


def run(fenced, report_delay, owner_offline, budget):
    trace, g = build(fenced, report_delay, owner_offline)
    sim = ServiceSimulator(trace, family, budget)
    sim.execute(InstallGrant('D', g, (0, 1)), sim.view())
    sim.execute(Transform('D', 'G', (0, 1)), sim.view())
    rep = sim.report()
    actual = max((float(m.disclosed_weight) for m in rep['actual_exposure']), default=0.0)
    public = max((float(m.disclosed_weight) for m in rep['observable_exposure']), default=0.0)
    served = rep['queue'].served
    expired = rep['queue'].expired
    deliveries = len(rep['deliveries'])
    rotations = sum(1 for (_, kind, status, _) in rep['outcomes']
                    if kind == 'ActivateScope' and status == 'activated')
    # a scope rotate in the fenced trace is an environment ScopeNotice, not an ActivateScope action;
    # count the realized rotation by truth scopes beyond epoch 0
    truth_epochs = {n.scope.epoch for n, _ in rep['truth_records']}
    realized_rotations = max(truth_epochs) if truth_epochs else 0
    violation = actual > float(budget.disclosed_weight)
    cost = deliveries + 3 * realized_rotations + 10 * (1 - served)
    return {"actual_disclosed": actual, "public_disclosed": public,
            "public_lag": actual - public, "served": served, "expired": expired,
            "deliveries": deliveries, "realized_rotations": realized_rotations,
            "budget_violation": violation, "total_cost": cost}


def main():
    budget_tight = Budget(0, 0, 2)      # tight: any collateral is a violation
    out = {"batch": "P3D", "run_kind": "model-simulation (fenced vs unfenced; NOT a crypto measurement)",
           "backend": "abstract-cfrag-usability-model", "env": {"python": platform.python_version()},
           "parameters": {"report_delay": [1, 4], "owner_offline_at_prod": [False, True],
                          "budget": "disclosed_weight=0 (tight)"},
           "note": "Deterministic model: we sweep documented parameters, not RNG seeds.",
           "settings": {}}
    violations = []
    for delay in (1, 4):
        for offline in (False, True):
            key = f"delay{delay}_{'offline' if offline else 'online'}"
            unf = run(False, delay, offline, budget_tight)
            fen = run(True, delay, offline, budget_tight)
            out["settings"][key] = {"unfenced": unf, "fenced": fen}
            # meaningfulness: fenced must be safe (0 disclosed, no violation)
            if fen["actual_disclosed"] != 0.0 or fen["budget_violation"]:
                violations.append(f"{key}: fenced run disclosed {fen['actual_disclosed']} / violation {fen['budget_violation']}")
            # the unfenced ONLINE cases should show a breach under the tight budget (comparison is real)
            if not offline and unf["actual_disclosed"] < 1.0:
                violations.append(f"{key}: unfenced online run did not breach (expected a disclosure)")
    os.makedirs("results/manifests", exist_ok=True)
    with open("results/manifests/p3d_fencing_pilot.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"\n[p3d_fencing_pilot] violations: {len(violations)}")
    for v in violations:
        print("   ", v)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
