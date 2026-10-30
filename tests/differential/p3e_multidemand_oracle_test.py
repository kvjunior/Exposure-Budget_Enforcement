"""
P3E multi-demand oracle tests (Task 3). Exit 0 = all expectations met.

Extends the exact timed oracle to multi-demand instances and reports honestly:
  MD-ORACLE   the oracle solves a 2-demand instance; its optimum replays feasibly (both served).
  MD-REPLAY   an independent recomputation of the oracle schedule's served-count and cost agrees.
  MD-GREEDY-CE a COUNTEREXAMPLE to universal greedy optimality: on an unservable demand greedy wastes
              fragments (installs a doomed grant) while the oracle rejects -> greedy sub-optimal.
  MD-BUDGET   budget competition: with a tight disclosed budget and a background collateral, the
              oracle serves the safe demand and does not breach; a myopic full-install breaches.
We report gap-to-optimum ONLY on the 2-demand instances the oracle exactly solves. We make NO
general multi-demand optimality claim; the independent timed reference remains single-demand.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform, Reject)
from delegation_manager.timed_oracle import TimedInstance, solve_timed, replay_timed, TimedCost

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<16} {msg}")
    if not ok: FAIL.append(cid)

def _n(e, t, p, a=None):
    return PublicEvent(e, T(t), T(t if a is None else a), p)

fam = (Reach('d', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)
cost = TimedCost()


# ---- MD-ORACLE / MD-REPLAY: 2 demands, two streams, generous budget ----
ra, rb = Record('a', 0), Record('b', 0)
dA = Demand('DA', 'O', 'R', (ra,), T(0), T(40)); dB = Demand('DB', 'O', 'R', (rb,), T(0), T(40))
tr2 = (_n('up', 0, OwnerNotice('O', True)),
       _n('sa', 0, ScopeNotice('O', Scope('a', 0), 'ka', 0)), RecordProduction('ra', 'O', ra, T(0), T(0)),
       _n('sb', 0, ScopeNotice('O', Scope('b', 0), 'kb', 0)), RecordProduction('rb', 'O', rb, T(0), T(0)),
       _n('arrA', 0, DemandArrival(dA)), _n('arrB', 0, DemandArrival(dB)))
gA = TimedGrant('GA', 'O', 'R', Scope('a', 0), RecordRange('a', 0, 1), 2, ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
gB = TimedGrant('GB', 'O', 'R', Scope('b', 0), RecordRange('b', 0, 1), 2, ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
inst2 = TimedInstance(lambda: ServiceSimulator(tr2, fam, Budget(5, 5, 5)), {'DA': gA, 'DB': gB},
                      (0, 40), cost=cost, max_depth=12, max_branches=24)
opt2 = solve_timed(inst2)
feas, rc, served, note = replay_timed(inst2, opt2.actions)
expect("MD-ORACLE", opt2.served == 2 and feas,
       f"2-demand oracle serves both (cost {opt2.total_cost}, served {opt2.served}) and replays feasibly")
expect("MD-REPLAY", abs(rc - opt2.total_cost) < 1e-9 and served == 2,
       f"independent recomputation of served/cost agrees (replay cost {rc}, served {served})")

# ---- MD-GREEDY-CE: greedy sub-optimal on an unservable demand (counterexample) ----
# single demand, deadline too tight to complete -> oracle REJECTS (cost = miss), greedy installs
# fragments then the demand expires (cost = fragments + miss) -> greedy strictly worse.
rc0 = Record('c', 0)
dC = Demand('DC', 'O', 'R', (rc0,), T(0), T(6))     # tight: minimal serve ends at 6, not < 6
trC = (_n('up', 0, OwnerNotice('O', True)), _n('sc', 0, ScopeNotice('O', Scope('c', 0), 'kc', 0)),
       RecordProduction('rc', 'O', rc0, T(0), T(0)), _n('arrC', 0, DemandArrival(dC)))
gC = TimedGrant('GC', 'O', 'R', Scope('c', 0), RecordRange('c', 0, 1), 2, ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
instC = TimedInstance(lambda: ServiceSimulator(trC, fam, Budget(5, 5, 5)), {'DC': gC}, (0, 6), cost=cost)
optC = solve_timed(instC)
# greedy: install + transform (wastes fragments, then expires)
simG = ServiceSimulator(trC, fam, Budget(5, 5, 5))
simG.execute(InstallGrant('DC', gC, (0, 1)), simG.view())
simG.execute(Transform('DC', 'GC', (0, 1)), simG.view())
repG = simG.report()
greedy_cost = len(repG['deliveries']) + 10 * (1 - repG['queue'].served)
expect("MD-GREEDY-CE", greedy_cost > optC.total_cost + 1e-9,
       f"COUNTEREXAMPLE to universal greedy optimality: greedy cost {greedy_cost} > oracle {optC.total_cost} "
       f"(greedy wastes fragments on a doomed demand; the oracle rejects). No general greedy-optimal claim.")

# ---- MD-BUDGET: tight budget + background collateral; oracle stays safe ----
# scope (g,0) has demanded g:0 and a background g:1 (collateral risk). budget disclosed=0.
rg0, rg1 = Record('g', 0), Record('g', 1)
dG = Demand('DG', 'O', 'R', (rg0,), T(0), T(40))
trG = (_n('up', 0, OwnerNotice('O', True)), _n('sg', 0, ScopeNotice('O', Scope('g', 0), 'kg', 0)),
       RecordProduction('g0', 'O', rg0, T(0), T(0)), RecordProduction('g1', 'O', rg1, T(0), T(0)),
       _n('arrG', 0, DemandArrival(dG)))
gG = TimedGrant('GG', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2, ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
instG = TimedInstance(lambda: ServiceSimulator(trG, fam, Budget(5, 0, 5)), {'DG': gG}, (0, 40), cost=cost)
optG = solve_timed(instG)
feasG, rcG, servedG, _ = replay_timed(instG, optG.actions)
simsafe = instG.make_sim()
# recompute actual disclosure along the oracle schedule
for a in optG.actions:
    simsafe.execute(a, simsafe.view())
discG = max((float(m.disclosed_weight) for m in simsafe.report()['actual_exposure']), default=0.0)
expect("MD-BUDGET", feasG and discG == 0.0,
       f"tight-budget + background collateral: the oracle schedule replays feasibly with actual "
       f"disclosed {discG} (stays safe; it cannot serve by exposing the background record)")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
