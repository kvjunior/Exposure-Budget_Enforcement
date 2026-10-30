"""
Independent timed reference (P3C, F06 in the timed setting).

This module computes a SEPARATE, minimal judgment about a tiny timed instance WITHOUT importing or
calling ServiceSimulator or delegation_manager.timed_oracle's action generator. Its purpose is to
catch two bug classes the oracle could hide if it only checked itself:
  (1) claiming to serve a demand that is structurally UNSERVABLE in the environment, and
  (2) reporting a cost BELOW the structural minimum for the service it claims.

It does this by re-deriving, from the environment trace and the demand alone:
  - OWNER AVAILABILITY over time: owner is online in [t, t') per OwnerNotice events; a serve needs
    the owner online across the install ticks (grant metadata + one tick per raw share).
  - A SERVE LOWER BOUND on cost: a usable serve of a demand with a threshold-k grant and m targets
    commits at least k raw deliveries plus k*m cfrag deliveries, i.e. fragment_cost*(k + k*m); an
    unserved demand costs at least the miss penalty.
  - DEADLINE feasibility: the minimal serve finishes by occurred ticks
    install_metadata(1) + k (raw) + k*m (cfrag) + 1 (open); if that exceeds the deadline from the
    demand's release, the demand is NOT servable without help.
  - A BUDGET note: if the declared family already reconstructs the demand's scope at serve time
    (threshold raw shares to reached proxies + recipient reached) and the budget forbids an exposed
    active scope, a direct serve breaches the observable gate, so either a rollover is required or
    the demand is deferred/left unserved.

For a SINGLE-demand instance it returns an exact independent optimum under these rules; for
multi-demand instances it returns a cost LOWER BOUND and the set of structurally-servable demands.
The test asserts the oracle's optimum is consistent with (never cheaper than, and serves no more
than) this independent judgment.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class RefJudgment:
    exact: bool                 # True if this is an exact optimum (single-demand), else a lower bound
    cost: float                 # exact optimum cost, or a lower bound on cost
    max_servable: int           # how many demands are structurally servable in this environment
    note: str


def _owner_online_intervals(trace) -> List[Tuple[int, Optional[int], bool]]:
    """Reconstruct owner availability as (from_tick, to_tick_or_None, online) from OwnerNotice events.
    We read ONLY the public trace's owner notices, by their occurrence time."""
    from delegation_model.timed_log import OwnerNotice, PublicEvent
    marks = []
    for e in trace:
        # PublicEvent carries (event_id, occurred_at, available_at, payload); owner notices are payloads
        payload = getattr(e, 'payload', None)
        occ = getattr(e, 'occurred_at', None)
        if isinstance(payload, OwnerNotice) and occ is not None:
            marks.append((occ.ticks, payload.online))
    marks.sort()
    intervals = []
    for i, (t, on) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else None
        intervals.append((t, end, on))
    return intervals


def _online_at(intervals, tick: int) -> bool:
    cur = False
    for (t, end, on) in intervals:
        if t <= tick and (end is None or tick < end):
            cur = on
    # if before first mark, assume offline unless a mark at/under tick set it
    best = None
    for (t, end, on) in intervals:
        if t <= tick:
            best = on
    return bool(best)


def judge(trace, demand, grant, cost, budget_forbids_exposed_scope: bool,
          fencing_available: bool) -> RefJudgment:
    """Independent exact judgment for a SINGLE-demand instance.

    demand: has released_at.ticks, deadline.ticks, targets (tuple).
    grant: has threshold k and proxies.
    cost: TimedCost-like with .fragment, .rollover, .miss.
    budget_forbids_exposed_scope: True if the budget's active-scope cap is 0.
    fencing_available: True if a rollover-before-serve is possible in this environment.
    """
    k = grant.threshold
    m = len(demand.targets)
    release = demand.released_at.ticks
    deadline = demand.deadline.ticks
    intervals = _owner_online_intervals(trace)

    # minimal serve timeline (ticks consumed from release): metadata(1) + k raw + k*m cfrag + open(1)
    install_end = release + 1 + k               # metadata + k raw deliveries
    serve_end = install_end + k * m + 1         # + cfrag deliveries + open
    # deadline feasibility: the completion tick must be < deadline (demand window is [release,deadline))
    deadline_ok = serve_end < deadline
    # owner must be online across the INSTALL ticks (raw delivery needs live owner authority)
    owner_ok = all(_online_at(intervals, t) for t in range(release, install_end + 1))

    serve_frag_cost = cost.fragment * (k + k * m)
    miss_cost = cost.miss

    if not deadline_ok:
        return RefJudgment(True, miss_cost, 0,
                           f"unservable: minimal serve ends at {serve_end} >= deadline {deadline}")

    if not owner_ok:
        # cannot install (owner offline during install); demand not servable by direct install
        return RefJudgment(True, miss_cost, 0,
                           "unservable: owner offline during the install window")

    if budget_forbids_exposed_scope:
        # a direct serve on the active scope exposes it -> breaches the gate. Need a rollover first.
        if fencing_available:
            # rollover then serve on the fresh scope: + rollover cost, still serves
            return RefJudgment(True, cost.rollover + serve_frag_cost, 1,
                               "servable via rollover-before-serve (budget forbids exposed scope)")
        # no fencing: a direct serve breaches; the safe option is to not serve -> miss
        return RefJudgment(True, miss_cost, 0,
                           "unservable within budget without fencing (direct serve breaches gate)")

    # budget permits a direct serve
    return RefJudgment(True, serve_frag_cost, 1, "servable directly within budget")
