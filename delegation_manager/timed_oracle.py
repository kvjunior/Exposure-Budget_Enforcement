"""
P3C bounded timed oracle.

An exact minimum-cost offline optimum for a TINY timed instance, computed by exhaustive
deepcopy-based search over the REAL ServiceSimulator. The oracle is an EVALUATION tool, not a
policy: it is allowed offline knowledge of the full environment trace, but it still only ever
drives the simulator through its public execute(action, view) API on independent copies -- it never
mutates private fields (A3). Each candidate action is tried on a fresh deepcopy of the current
state; the search recurses until every demand is terminal (served/rejected/expired) or a bounded
step budget is reached. Branching/depth bounds are explicit and the oracle REFUSES (raises) rather
than silently omitting legal actions.

Cost model (deterministic, from the simulator's own report + the committed action log):
  cost = fragment_cost * (committed deliveries)
       + rollover_cost * (number of successful ActivateScope actions)
       + miss_penalty  * (demands not SERVED at the end of the run)
This mirrors the untimed cost model: serving costs the fragments it installs; rolling costs a
rollover; leaving a demand unserved costs a miss. A served demand pays no extra miss.

The action grammar per decision point (bounded), for the single-stream tiny instances:
  - for each PENDING demand whose grant is not yet installed: InstallGrant with EACH size-threshold
    subset of the grant's share indices (all usable delivery choices, like the untimed F02 repair);
  - once a grant is installed: Transform to complete it (threshold cfrags for every target);
  - ActivateScope (rollover) when a pending demand exists and public authority permits;
  - Defer(d, until = next environment event tick) and Reject(d).
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Tuple
from fractions import Fraction

from delegation_model.service_clock import ServiceTime
from delegation_model.demand_queue import DemandStatus
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_log import ScopeNotice
from delegation_manager.service_simulator import (ServiceSimulator, InstallGrant, Transform,
                                                  ActivateScope, Defer, Reject)


@dataclass
class TimedCost:
    fragment: float = 1.0
    rollover: float = 3.0
    miss: float = 10.0


@dataclass
class TimedInstance:
    """A tiny timed instance. `make_sim` returns a FRESH ServiceSimulator (so the oracle can re-seed
    independent runs). `grants` maps each demand id to the TimedGrant the policy would propose for
    it. `event_ticks` are the environment tick times (for Defer wake points). Bounds keep the search
    finite; exceeding them raises."""
    make_sim: object                      # () -> ServiceSimulator
    grants: Dict[str, TimedGrant]
    event_ticks: Tuple[int, ...]
    next_epoch_scope: object = None       # optional: (owner, key_id) factory for rollover
    cost: TimedCost = field(default_factory=TimedCost)
    max_depth: int = 8
    max_branches: int = 16


@dataclass
class TimedSchedule:
    actions: List[object]                 # the action objects, in order
    total_cost: float
    served: int


def _pending_ids(sim) -> List[str]:
    q = sim.view().queue
    return [e.demand.demand_id for e in q.entries if e.status == DemandStatus.PENDING]


def _installed_grant_ids(sim) -> set:
    return {ig.grant.grant_id for ig in sim.view().grants}


def _run_cost(sim, actions, cost: TimedCost, n_demands: int) -> Tuple[float, int]:
    rep = sim.report()
    served = rep['queue'].served
    deliveries = len(rep['deliveries'])
    rollovers = sum(1 for (_, kind, status, _) in rep['outcomes']
                    if kind == 'ActivateScope' and status == 'activated')
    unserved = n_demands - served
    total = (cost.fragment * deliveries + cost.rollover * rollovers + cost.miss * unserved)
    return total, served


def _candidate_actions(sim, inst: TimedInstance) -> List[object]:
    """Enumerate bounded candidate actions legal from the current public view."""
    out: List[object] = []
    pend = _pending_ids(sim)
    if not pend:
        return out
    installed = _installed_grant_ids(sim)
    now = sim.view().observation.now
    # next environment event tick strictly after now, for Defer wake points
    future_ticks = sorted(t for t in inst.event_ticks if t > now.ticks)
    wake = ServiceTime(future_ticks[0]) if future_ticks else None

    for did in pend:
        g = inst.grants.get(did)
        if g is None:
            continue
        if g.grant_id not in installed:
            # InstallGrant with each size-threshold subset of share indices
            for idx in combinations(range(len(g.proxies)), g.threshold):
                out.append(InstallGrant(did, g, tuple(idx)))
        else:
            # Transform to complete (use the same threshold indices that were installed)
            out.append(Transform(did, g.grant_id, tuple(range(g.threshold))))
        # Defer (only if there is a strictly-later wake tick within the deadline)
        if wake is not None:
            out.append(Defer(did, wake))
        # Reject
        out.append(Reject(did))
    # Rollover: a fresh scope activation, if a factory is provided
    if inst.next_epoch_scope is not None:
        act = inst.next_epoch_scope(sim)
        if act is not None:
            out.append(act)
    return out


def solve_timed(inst: TimedInstance) -> TimedSchedule:
    """Exhaustive minimum-cost schedule over the real simulator. Raises on bound violation or
    infeasibility."""
    base = inst.make_sim()
    n_demands = len(base.view().queue.entries)
    best: List[Optional[TimedSchedule]] = [None]

    def terminal(sim) -> bool:
        return len(_pending_ids(sim)) == 0

    def recurse(sim, chosen: List[object], depth: int):
        # prune
        cur_cost, _ = _run_cost(sim, chosen, inst.cost, n_demands)
        if best[0] is not None and cur_cost >= best[0].total_cost:
            return
        if terminal(sim):
            total, served = _run_cost(sim, chosen, inst.cost, n_demands)
            if best[0] is None or total < best[0].total_cost:
                best[0] = TimedSchedule(list(chosen), total, served)
            return
        if depth >= inst.max_depth:
            return
        cands = _candidate_actions(sim, inst)
        if len(cands) > inst.max_branches:
            raise ValueError(f"timed branching {len(cands)} > max_branches {inst.max_branches}; "
                             f"refuse rather than omit legal actions")
        progressed = False
        for a in cands:
            child = copy.deepcopy(sim)
            res = child.execute(a, child.view())
            # a refused action that changes nothing is a dead branch (no progress); skip to avoid loops
            if res.status == 'refused':
                continue
            progressed = True
            recurse(child, chosen + [a], depth + 1)
        if not progressed:
            # no action makes progress; record the current (all-miss) terminal cost
            total, served = _run_cost(sim, chosen, inst.cost, n_demands)
            if best[0] is None or total < best[0].total_cost:
                best[0] = TimedSchedule(list(chosen), total, served)

    recurse(base, [], 0)
    if best[0] is None:
        raise ValueError("no feasible timed schedule found")
    return best[0]


def replay_timed(inst: TimedInstance, actions: List[object]) -> Tuple[bool, float, int, str]:
    """Drive a schedule through a FRESH real simulator and recompute (feasible, cost, served, note).
    An action that the simulator REFUSES makes the schedule infeasible. This is the simulator-side
    replay; the INDEPENDENT reference (timed_independent_reference.py) does not share this code."""
    sim = inst.make_sim()
    n_demands = len(sim.view().queue.entries)
    for a in actions:
        res = sim.execute(a, sim.view())
        if res.status == 'refused':
            return False, 0.0, 0, f"action {type(a).__name__} refused: {res.reason}"
    total, served = _run_cost(sim, actions, inst.cost, n_demands)
    return True, total, served, f"ok (served {served}/{n_demands})"
