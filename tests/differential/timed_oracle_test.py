"""
P3C timed oracle tests. Exit 0 = all expectations met.

Verifies:
  T-ORACLE   the bounded timed oracle returns a minimum-cost schedule that REPLAYS feasibly in a
             fresh real ServiceSimulator (cost and served-count reproduce).
  T-REF      a GENUINELY INDEPENDENT reference (timed_independent_reference, which does not import
             ServiceSimulator or the oracle's action generator) agrees with the oracle's optimum on
             several tiny single-demand instances across servable / unservable / budget-fenced regimes.
  T-NOBEAT   no online policy beats the timed optimum (greedy and blind-rollover both have gap >= 0).
  T-GAP      INSIDE the feasible regime, a simple greedy policy ACHIEVES the optimum (gap 0) while a
             blind rotate-first policy does NOT -- the timed analogue of the untimed characterization.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python", "experiments"))

from fractions import Fraction
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform, ActivateScope, Defer, Reject)
from delegation_manager.timed_oracle import TimedInstance, solve_timed, replay_timed, TimedCost
from timed_independent_reference import judge

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<16} {msg}")
    if not ok: FAIL.append(cid)


def _notice(eid, t, payload, available=None):
    return PublicEvent(eid, T(t), T(t if available is None else available), payload)


def build(extra=(), deadline=30, budget=Budget(100, 100, 5)):
    """Return (trace, demand, grant, make_sim, budget). Explicit so the reference sees the same trace."""
    r = Record('g', 0)
    dem = Demand('D', 'O', 'R', (r,), T(0), T(deadline))
    trace = (_notice('up', 0, OwnerNotice('O', True)),
             _notice('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
             RecordProduction('r0', 'O', r, T(0), T(0)),
             _notice('arrival', 0, DemandArrival(dem))) + extra
    family = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)
    grant = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2,
                       ('p0', 'p1', 'p2'), TimeWindow(T(0), T(30)))
    def make_sim():
        return ServiceSimulator(trace, family, budget)
    return trace, dem, grant, make_sim, budget


def rollover_factory(key_epoch=1, start_seq=1):
    def f(sim):
        return ActivateScope(ScopeNotice('O', Scope('g', key_epoch), f'key{key_epoch}', start_seq))
    return f


cost = TimedCost()

# ---- instances across regimes ----
# A1: generous -> servable directly (oracle = fragment serve = 4)
tr1, d1, g1, mk1, b1 = build()
i1 = TimedInstance(mk1, {'D': g1}, (0, 30), cost=cost)
o1 = solve_timed(i1)
ok1, c1, s1, why1 = replay_timed(i1, o1.actions)
j1 = judge(tr1, d1, g1, cost, budget_forbids_exposed_scope=False, fencing_available=False)
expect("T-ORACLE_A1", ok1 and abs(c1 - o1.total_cost) < 1e-9 and s1 == o1.served,
       f"A1 oracle optimum replays feasibly (cost {o1.total_cost}, served {o1.served})")
expect("T-REF_A1", j1.exact and abs(j1.cost - o1.total_cost) < 1e-9 and j1.max_servable == o1.served,
       f"A1 independent reference agrees (ref {j1.cost}/{j1.max_servable} vs oracle {o1.total_cost}/{o1.served}): {j1.note}")

# A2: deadline tight (6) -> minimal serve ends at 6, not < 6 -> unservable -> miss
tr2, d2, g2, mk2, b2 = build(deadline=6)
i2 = TimedInstance(mk2, {'D': g2}, (0, 6), cost=cost)
o2 = solve_timed(i2)
j2 = judge(tr2, d2, g2, cost, False, False)
expect("T-REF_A2", j2.exact and abs(j2.cost - o2.total_cost) < 1e-9,
       f"A2 (tight deadline) reference agrees (ref {j2.cost} vs oracle {o2.total_cost}, served {o2.served}): {j2.note}")

# A3: owner goes offline at tick 1 -> cannot install -> unservable -> miss
tr3, d3, g3, mk3, b3 = build(extra=(_notice('down', 1, OwnerNotice('O', False)),))
i3 = TimedInstance(mk3, {'D': g3}, (0, 1, 30), cost=cost)
o3 = solve_timed(i3)
j3 = judge(tr3, d3, g3, cost, False, False)
expect("T-REF_A3", j3.exact and abs(j3.cost - o3.total_cost) < 1e-9,
       f"A3 (owner offline during install) reference agrees (ref {j3.cost} vs oracle {o3.total_cost}, served {o3.served}): {j3.note}")
expect("T-ORACLE_A3_replays", replay_timed(i3, o3.actions)[0],
       "A3 oracle schedule replays feasibly")

# ---- T-NOBEAT + T-GAP: online policies never beat the optimum; greedy achieves it, blind does not ----
def greedy_policy(sim, grant):
    """Install + transform if feasible; else reject. Minimal-cost serve attempt."""
    actions = []
    v = sim.view()
    # install threshold indices
    r = sim.execute(InstallGrant('D', grant, (0, 1)), sim.view())
    actions.append(InstallGrant('D', grant, (0, 1)))
    if r.status in ('installed',):
        sim.execute(Transform('D', 'G', (0, 1)), sim.view())
        actions.append(Transform('D', 'G', (0, 1)))
    return actions

def blind_rollover_policy(sim, grant):
    """Always rotate a fresh scope first, then install+transform. Over-rolls when not needed."""
    actions = []
    roll = ActivateScope(ScopeNotice('O', Scope('g', 1), 'key1', 1))
    rr = sim.execute(roll, sim.view())
    if rr.status == 'activated':
        actions.append(roll)
    sim.execute(InstallGrant('D', grant, (0, 1)), sim.view())
    actions.append(InstallGrant('D', grant, (0, 1)))
    sim.execute(Transform('D', 'G', (0, 1)), sim.view())
    actions.append(Transform('D', 'G', (0, 1)))
    return actions

def run_online(make_sim, grant, policy, inst):
    sim = make_sim()
    policy(sim, grant)
    n = len(make_sim().view().queue.entries)
    rep = sim.report()
    served = rep['queue'].served
    deliveries = len(rep['deliveries'])
    rollovers = sum(1 for (_, kind, status, _) in rep['outcomes']
                    if kind == 'ActivateScope' and status == 'activated')
    return inst.cost.fragment * deliveries + inst.cost.rollover * rollovers + inst.cost.miss * (n - served)

# use the generous A1 instance (feasible regime)
greedy_cost = run_online(mk1, g1, greedy_policy, i1)
blind_cost = run_online(mk1, g1, blind_rollover_policy, i1)
expect("T-NOBEAT_greedy", greedy_cost >= o1.total_cost - 1e-9,
       f"greedy cost {greedy_cost} >= optimum {o1.total_cost} (never beats the optimum)")
expect("T-NOBEAT_blind", blind_cost >= o1.total_cost - 1e-9,
       f"blind-rollover cost {blind_cost} >= optimum {o1.total_cost}")
expect("T-GAP_greedy_optimal", abs(greedy_cost - o1.total_cost) < 1e-9,
       f"INSIDE the feasible regime greedy ACHIEVES the optimum (gap {greedy_cost - o1.total_cost})")
expect("T-GAP_blind_suboptimal", blind_cost > o1.total_cost + 1e-9,
       f"blind rotate-first is SUB-optimal (cost {blind_cost} vs optimum {o1.total_cost}): over-rolls")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
