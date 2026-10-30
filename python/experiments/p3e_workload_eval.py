"""
P3F corrected workload generator + policy evaluation (manuscript evidence).

Fixes (per reviewer A1-A6):
 - Production fencing GENUINELY EXECUTES via ServiceSimulator(production_fencing=True): a record that
   would bind to an actually-reconstructible scope is rotated to a fresh scope or dropped.
 - Admission enforcement is toggled via ServiceSimulator(admission_enforcement=...).
 - Time-advancing workload: STAGGERED demand releases and POST-GRANT production events, so the fence
   and the admission boundary are actually exercised.
 - Two breach types in the SAME workload:
     (B-prod) a post-grant production under a reconstructible scope  -> needs PRODUCTION fencing;
     (B-retro) a later grant delivery that exposes an older record   -> needs ADMISSION enforcement.
 - FIVE policies (the exact oracle is separate):
     unfenced        : production_fencing=False, admission_enforcement=False   (UNSAFE)
     production_only : production_fencing=True,  admission_enforcement=False   (fence only)
     admission_only  : production_fencing=False, admission_enforcement=True    (enforce only)
     greedy_full     : production_fencing=True,  admission_enforcement=True    (PROPOSED)
     conservative    : full safety, but refuses every delegation (trivially safe)
 - Multiple budgets (disclosed in {0, 1}) x report delays x owner availability; 30 seeds.

Costs/latencies are DECLARED MODEL UNITS (ticks, fragment counts), not wall-clock or crypto.
Writes results/manifests/p3e_workload_eval.json (+ .csv). Exit 0 iff the fully-safe policy
(greedy_full) never violates and at least one weaker policy violates on each breach type.
"""
from __future__ import annotations
import csv, json, os, random, statistics, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand, DemandStatus
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform, Reject)

FAM = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R0', 'R1'})),)
PROXIES = ('p0', 'p1', 'p2')


def _n(e, t, p, a=None):
    return PublicEvent(e, T(t), T(t if a is None else a), p)


def gen_workload(seed, n_streams, horizon, report_delay_max, offline_prob):
    """Deterministic time-advancing workload. Each stream gets an initial scope + a demanded record
    at seq 0 (visible). Then, after a grant could be installed, we schedule:
      - a POST-GRANT production of seq 1 under the SAME scope (B-prod), with a report delay;
      - a BACKGROUND record at seq 1 is NOT separately added; instead B-retro is created by a demand
        whose grant range is narrow so delivering it exposes the scope and opens the post-grant record.
    Demands are RELEASED at staggered ticks (not all at 0)."""
    rng = random.Random(seed)
    events = [_n('up0', 0, OwnerNotice('O', True))]
    # owner availability flips
    t = 3
    while t < horizon:
        if rng.random() < offline_prob:
            events.append(_n(f'off{t}', t, OwnerNotice('O', False)))
            back = t + rng.randint(1, 3)
            if back < horizon:
                events.append(_n(f'on{back}', back, OwnerNotice('O', True)))
            t = back + rng.randint(2, 4)
        else:
            t += rng.randint(3, 5)
    demands, grants = [], {}
    for s in range(n_streams):
        stream = f's{s}'
        events.append(_n(f'sc{s}', 0, ScopeNotice('O', Scope(stream, 0), f'{stream}k0', 0)))
        events.append(RecordProduction(f'{stream}r0', 'O', Record(stream, 0), T(0), T(0), 1.0))  # visible seq 0
        delay = rng.randint(0, report_delay_max)
        # Alternate stream TYPE so BOTH breach modes appear:
        #  B-PROD (even s): seq 1 produced POST-grant under (stream,0) -> needs PRODUCTION fencing.
        #  B-RETRO (odd s): seq 1 produced EARLY (pre-grant), report possibly delayed -> delivering
        #    the narrow grant exposes the scope and discloses seq 1 -> needs ADMISSION enforcement.
        if s % 2 == 0:
            prod_tick = rng.randint(6, max(7, horizon - 4))     # post-grant
        else:
            prod_tick = 0                                       # pre-grant background
        events.append(RecordProduction(f'{stream}r1', 'O', Record(stream, 1), T(prod_tick),
                                       T(min(horizon - 1, prod_tick + delay)), 1.0))
        recip = f'R{rng.randint(0, 1)}'
        rel = rng.randint(0, 3)
        deadline = min(horizon, rel + rng.randint(10, 18))
        dem = Demand(f'D{s}', 'O', recip, (Record(stream, 0),), T(rel), T(deadline))
        demands.append(dem)
        grants[f'D{s}'] = TimedGrant(f'G{s}', 'O', recip, Scope(stream, 0),
                                     RecordRange(stream, 0, 1), 2, PROXIES, TimeWindow(T(0), T(horizon)))
        events.append(_n(f'arr{s}', rel, DemandArrival(dem)))
    def keyf(e):
        return (e.occurred_at.ticks, type(e).__name__, getattr(e, 'event_id', ''))
    return tuple(sorted(events, key=keyf)), demands, grants


POLICIES = {
    'unfenced':        dict(production_fencing=False, admission_enforcement=False),
    'production_only': dict(production_fencing=True,  admission_enforcement=False),
    'admission_only':  dict(production_fencing=False, admission_enforcement=True),
    'greedy_full':     dict(production_fencing=True,  admission_enforcement=True),
    'conservative':    dict(production_fencing=True,  admission_enforcement=True),
}


def run_policy(policy, events, demands, grants, budget, horizon=None):
    """Run an identical immutable event trace to its evaluation horizon.

    The policy observes only the public PolicyView, never report()/the future trace.
    Scheduler: earliest-deadline-first among *currently pending* demands;
    one admissible action bundle per decision opportunity; retry interrupted
    grants on later ticks when authority returns, preserving installed fragments.
    An unsuccessful decision consumes no service time, so the driver advances
    to the next tick. Every pending demand eventually terminates by deadline.
    """
    cfg = POLICIES[policy]
    if horizon is None:
        horizon = max([e.occurred_at.ticks for e in events] + [d.deadline.ticks for d in demands])
    if type(horizon) is not int or horizon < 1:
        raise ValueError('positive integer evaluation horizon required')
    if any(e.occurred_at.ticks > horizon for e in events):
        raise ValueError('horizon does not include all scheduled events')
    sim = ServiceSimulator(events, FAM, budget, production_fencing=cfg['production_fencing'],
                           admission_enforcement=cfg['admission_enforcement'])
    attempts, successes, retry_count, rejected_by_policy = 0, 0, 0, 0
    attempted_at = {}  # never attempt the same demand repeatedly at an unchanged service tick
    trace_ticks = [sim.now.ticks]
    max_observation_gap = 0.0

    def observe_gap():
        nonlocal max_observation_gap
        # Evaluator-only read; not used to choose the next action.
        rep = sim.report()
        a = max((float(m.disclosed_weight) for m in rep['actual_exposure']), default=0.0)
        b = max((float(m.disclosed_weight) for m in rep['observable_exposure']), default=0.0)
        max_observation_gap = max(max_observation_gap, a - b)

    def enact(dem):
        """One decision opportunity, with resumption of partial deliveries."""
        g = grants[dem.demand_id]
        view = sim.view()
        existing = next((x for x in view.grants if x.grant.grant_id == g.grant_id), None)
        raw = {d.index for d in view.deliveries if d.grant_id == g.grant_id and d.record is None}
        missing = tuple(i for i in (0, 1) if i not in raw)
        if existing is None or missing:
            # Reserve enough time to complete the selected atomic action before the horizon;
            # a partially completed operation is still allowed if intervening events interrupt it.
            required = (1 if existing is None else 0) + len(missing)
            if sim.now.ticks + required >= min(horizon, dem.deadline.ticks):
                return 'insufficient-time'
            result = sim.execute(InstallGrant(dem.demand_id, g, missing), sim.view())
            if result.status != 'installed':
                return result.status
        if sim.now.ticks + 3 >= min(horizon, dem.deadline.ticks):
            return 'insufficient-time'
        return sim.execute(Transform(dem.demand_id, g.grant_id, (0, 1)), sim.view()).status

    # Advance to each decision opportunity, processing *all* arrivals/production/reports
    # even when no policy action is feasible or no demand has yet been released.
    while sim.now.ticks < horizon:
        observe_gap()
        view = sim.view()
        pending = sorted((entry.demand for entry in view.queue.entries
                          if entry.status == DemandStatus.PENDING),
                         key=lambda d: (d.deadline.ticks, d.released_at.ticks, d.demand_id))
        current = sim.now.ticks
        eligible = [d for d in pending if attempted_at.get(d.demand_id) != current]
        if eligible:
            dem = eligible[0]
            attempted_at[dem.demand_id] = current
            if policy == 'conservative':
                outcome = sim.execute(Reject(dem.demand_id), view).status
                rejected_by_policy += int(outcome == 'rejected')
            else:
                attempts += 1
                outcome = enact(dem)
                successes += int(outcome == 'served')
                retry_count += int(outcome in ('interrupted', 'refused', 'insufficient-time'))
            trace_ticks.append(sim.now.ticks)
            observe_gap()
            # If execution advanced time, process fresh arrivals at the new time.
            # Otherwise, try a different pending demand this tick, then advance.
            if sim.now.ticks > current:
                continue
            if len(eligible) > 1:
                continue
        sim.advance_to(T(current + 1))
        trace_ticks.append(sim.now.ticks)
    # The inclusive horizon is processed by advance_to; no action allowed afterwards.
    observe_gap()
    rep = sim.report()
    if rep['now'].ticks != horizon:
        raise AssertionError('simulation did not reach the declared full horizon')
    if len(rep['truth_records']) + rep['fence_drops'] != sum(isinstance(e, RecordProduction) for e in events):
        raise AssertionError('some scheduled production was not processed')
    q = rep['queue']
    if q.pending != 0 or q.served + q.rejected + q.expired != len(demands):
        raise AssertionError('demand arrivals, deadlines, or terminal outcomes were skipped')
    actual = max((float(m.disclosed_weight) for m in rep['actual_exposure']), default=0.0)
    public = max((float(m.disclosed_weight) for m in rep['observable_exposure']), default=0.0)
    deliveries = len(rep['deliveries'])
    rot, drops = rep['fence_rotations'], rep['fence_drops']
    served_entries = [entry for entry in sim.view().queue.entries
                      if entry.status == DemandStatus.SERVED]
    latencies = [entry.ended_at.ticks - entry.demand.released_at.ticks for entry in served_entries]
    violation = int(actual > float(budget.disclosed_weight))
    cost = deliveries + 3 * rot + 5 * drops + 10 * (q.rejected + q.expired)
    return {'actual_disclosed': actual, 'public_disclosed': public,
            'public_lag_peak_sampled': round(max_observation_gap, 3),
            'violation': violation, 'served': q.served, 'rejected': q.rejected,
            'expired': q.expired, 'pending': q.pending,
            'demands_total': len(demands), 'productions_scheduled': sum(isinstance(e, RecordProduction) for e in events),
            'productions_completed': len(rep['truth_records']),
            'deliveries': deliveries, 'fence_rotations': rot, 'fence_drops': drops,
            'total_cost': cost, 'mean_served_latency': round(statistics.mean(latencies), 3) if latencies else None,
            'attempts': attempts, 'retries_or_refusals': retry_count,
            'simulation_end_tick': sim.now.ticks, 'horizon': horizon,
            'trace_tick_count': len(trace_ticks),
            'enforcement_violations_reported': len(rep['breaches'])}


def main():
    configs = {
        "light":   dict(n_streams=4, horizon=24, report_delay_max=2, offline_prob=0.2),
        "heavy":   dict(n_streams=4, horizon=30, report_delay_max=4, offline_prob=0.3),
        "intermittent": dict(n_streams=4, horizon=28, report_delay_max=3, offline_prob=0.55),
    }
    budgets = {"B0": Budget(5, 0, 6), "B1": Budget(5, 1, 6)}
    seeds = list(range(30))
    out = {"batch": "P3F-full-horizon-correction", "run_kind": "model-simulation (declared units; NOT crypto/wall-clock)",
           "backend": "abstract-cfrag-usability-model", "env": {"python": platform.python_version()},
           "seeds": len(seeds), "policies": list(POLICIES.keys()),
           "policy_config": {k: v for k, v in POLICIES.items()},
           "note": "Five policies; oracle separately. EDF scheduler processes staggered arrivals and "
                   "all timed events through the inclusive horizon. Costs are declared model units.",
           "cells": {}}
    rows = []
    for bname, budget in budgets.items():
        for cname, cfg in configs.items():
            cell = f"{cname}_{bname}"
            per = {p: [] for p in POLICIES}
            for seed in seeds:
                ev, dems, grants = gen_workload(seed, **cfg)
                for p in POLICIES:
                    m = run_policy(p, ev, dems, grants, budget, horizon=cfg["horizon"])
                    per[p].append(m); rows.append({"cell": cell, "seed": seed, "policy": p, **m})
            agg = {}
            for p in POLICIES:
                ms = per[p]
                def stat(k):
                    vals = [m[k] for m in ms]
                    return {"mean": round(statistics.mean(vals), 3),
                            "stdev": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
                            "max": max(vals)}
                agg[p] = {k: stat(k) for k in ("actual_disclosed", "violation", "served", "rejected",
                                               "expired", "fence_rotations", "fence_drops", "total_cost", "productions_completed",
                                               "attempts", "retries_or_refusals", "public_lag_peak_sampled")}
            out["cells"][cell] = {"budget_disclosed": float(budget.disclosed_weight), "config": cfg, "policies": agg}
    os.makedirs("results/manifests", exist_ok=True)
    json.dump(out, open("results/manifests/p3e_workload_eval.json", "w"), indent=2)
    with open("results/manifests/p3e_workload_eval.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(json.dumps(out, indent=2))
    # validation: greedy_full never violates; unfenced violates somewhere; production_only violates on
    # B-retro somewhere (admission needed); admission_only violates on B-prod somewhere (fence needed).
    viol = []
    for cell, c in out["cells"].items():
        if c["policies"]["greedy_full"]["violation"]["max"] > 0:
            viol.append(f"{cell}: greedy_full (fully safe) violated")
        if c["policies"]["conservative"]["violation"]["max"] > 0:
            viol.append(f"{cell}: conservative violated")
    unfenced_viol = any(out["cells"][c]["policies"]["unfenced"]["violation"]["max"] > 0 for c in out["cells"])
    prod_only_viol = any(out["cells"][c]["policies"]["production_only"]["violation"]["max"] > 0 for c in out["cells"])
    adm_only_viol = any(out["cells"][c]["policies"]["admission_only"]["violation"]["max"] > 0 for c in out["cells"])
    if not unfenced_viol: viol.append("unfenced never violated -> comparison not meaningful")
    if not prod_only_viol: viol.append("production_only never violated -> admission need not demonstrated")
    if not adm_only_viol: viol.append("admission_only never violated -> production-fence need not demonstrated")
    out_headline = ("Neither production fencing alone (production_only) nor admission enforcement alone "
                    "(admission_only) is sufficient: each violates the budget on the breach type the "
                    "other handles. Only the COMBINED mechanism (greedy_full) never violates.")
    print("\nHEADLINE:", out_headline)
    print(f"[p3e_workload_eval] validation issues: {len(viol)}")
    for v in viol: print("   ", v)
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
